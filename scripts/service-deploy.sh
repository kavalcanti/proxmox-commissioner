#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

print_help() {
    cat <<EOF
Usage: $(basename "$0") <service> [options]

Deploy a service VM, running only the phases it still needs.

The host is probed over SSH to decide whether initial hardening
(00-initial.yml, 10-base-security.yml) has already run. Playbook lists come
from the service's deploy.conf.

Arguments:
  service               Service name under the services directory

Options:
  --commission          Provision the VM and generate its inventory first
  --refresh-inventory   Regenerate the inventory before running playbooks
  --bootstrap           Treat the host as fresh instead of probing it
  --converge            Skip hardening instead of probing the host
  --post-deploy         Also run POSTDEPLOY_PLAYBOOKS
  --only <playbook>     Run just this playbook; repeatable
  --dry-run             Show the resolved phase and playbook order, run nothing
  -h, --help            Show this help message and exit

Examples:
  $(basename "$0") mediastack
  $(basename "$0") mediastack --commission --post-deploy
  $(basename "$0") mediastack --only 25-file-push.yml
EOF
}

# ------------------------------------------------------------------------------
# Arguments
# ------------------------------------------------------------------------------
SERVICE=""
DO_COMMISSION=false
DO_REFRESH_INVENTORY=false
FORCE_BOOTSTRAP=false
FORCE_CONVERGE=false
RUN_POST_DEPLOY=false
DRY_RUN=false
ONLY_PLAYBOOKS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --commission)
            DO_COMMISSION=true
            shift
            ;;
        --refresh-inventory)
            DO_REFRESH_INVENTORY=true
            shift
            ;;
        --bootstrap)
            FORCE_BOOTSTRAP=true
            shift
            ;;
        --converge)
            FORCE_CONVERGE=true
            shift
            ;;
        --post-deploy)
            RUN_POST_DEPLOY=true
            shift
            ;;
        --only)
            if [[ -z "${2:-}" ]]; then
                echo "Error: --only requires a playbook name." >&2
                print_help >&2
                exit 1
            fi
            ONLY_PLAYBOOKS+=("$2")
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            print_help
            exit 0
            ;;
        -*)
            echo "Error: Unknown option '$1'" >&2
            print_help >&2
            exit 1
            ;;
        *)
            if [[ -n "${SERVICE}" ]]; then
                echo "Error: Unexpected argument '$1'" >&2
                print_help >&2
                exit 1
            fi
            SERVICE="$1"
            shift
            ;;
    esac
done

require_service "${SERVICE}"

if [[ "${FORCE_BOOTSTRAP}" == true && "${FORCE_CONVERGE}" == true ]]; then
    echo "Error: Use either --bootstrap or --converge, not both." >&2
    exit 1
fi

if (( ${#ONLY_PLAYBOOKS[@]} > 0 )) && [[ "${FORCE_BOOTSTRAP}" == true || "${FORCE_CONVERGE}" == true ]]; then
    echo "Error: --only runs a fixed list, so it cannot be combined with --bootstrap or --converge." >&2
    exit 1
fi

source_config "${SERVICE}"

# ------------------------------------------------------------------------------
# Optional provisioning steps
# ------------------------------------------------------------------------------
# inventory-generate.sh rewrites the inventory from scratch, dropping
# hand-edited host vars, so both stay opt-in.
if [[ "${DO_COMMISSION}" == true ]]; then
    if [[ "${DRY_RUN}" == true ]]; then
        echo "[dry-run] would commission '${SERVICE}' and generate its inventory"
    else
        bash "${SCRIPTS_DIR}/service-commission.sh" "${SERVICE}"
        bash "${SCRIPTS_DIR}/inventory-generate.sh" "${SERVICE}"
    fi
elif [[ "${DO_REFRESH_INVENTORY}" == true ]]; then
    if [[ "${DRY_RUN}" == true ]]; then
        echo "[dry-run] would regenerate the inventory for '${SERVICE}'"
    else
        bash "${SCRIPTS_DIR}/inventory-generate.sh" "${SERVICE}"
    fi
fi

# ------------------------------------------------------------------------------
# Resolve the playbook order
# ------------------------------------------------------------------------------
# get_terraform_outputs leaves the process in the service's Terraform root, so
# everything below uses absolute paths.
get_terraform_outputs "${SERVICE}"

PLAYBOOKS=()

if (( ${#ONLY_PLAYBOOKS[@]} > 0 )); then
    validate_playbooks "${ONLY_PLAYBOOKS[@]}"
    DEPLOY_PHASE="explicit"
    PLAYBOOKS=("${ONLY_PLAYBOOKS[@]}")
else
    load_deploy_conf "${SERVICE}"

    if [[ "${FORCE_BOOTSTRAP}" == true ]]; then
        DEPLOY_PHASE="fresh"
        PHASE_SOURCE="--bootstrap"
    elif [[ "${FORCE_CONVERGE}" == true ]]; then
        DEPLOY_PHASE="hardened"
        PHASE_SOURCE="--converge"
    else
        detect_deploy_phase
        PHASE_SOURCE="ssh probe"
    fi

    if [[ "${DEPLOY_PHASE}" == "unreachable" ]]; then
        echo "Error: Cannot reach VM '${VM_NAME}' at ${VM_IP}." >&2
        echo "Tried the devops key on ports $(ansible_base_var prod_ssh_port) and $(ansible_base_var ssh_port)," >&2
        echo "then a plain TCP connect on port $(ansible_base_var ssh_port)." >&2
        echo "Check that the VM is running, then rerun. Use --bootstrap to skip probing." >&2
        exit 1
    fi

    while IFS= read -r playbook; do
        [[ -n "${playbook}" ]] && PLAYBOOKS+=("${playbook}")
    done < <(bootstrap_playbooks_for_phase "${DEPLOY_PHASE}")

    if (( ${#CONVERGE_PLAYBOOKS[@]} > 0 )); then
        PLAYBOOKS+=("${CONVERGE_PLAYBOOKS[@]}")
    fi

    if [[ "${RUN_POST_DEPLOY}" == true ]] && (( ${#POSTDEPLOY_PLAYBOOKS[@]} > 0 )); then
        PLAYBOOKS+=("${POSTDEPLOY_PLAYBOOKS[@]}")
    fi
fi

# ------------------------------------------------------------------------------
# Report
# ------------------------------------------------------------------------------
echo "=== Deploying service '${SERVICE}' ==="
echo "VM Name: ${VM_NAME}"
echo "VM IP:   ${VM_IP}"
if [[ "${DEPLOY_PHASE}" == "explicit" ]]; then
    echo "Phase:   explicit playbook list (--only)"
else
    echo "Phase:   ${DEPLOY_PHASE} (${PHASE_SOURCE})"
    case "${DEPLOY_PHASE}" in
        hardened)
            echo "         host is already hardened, skipping initial hardening"
            ;;
        initialized)
            echo "         initial setup done but SSH not yet moved, resuming hardening"
            ;;
        fresh)
            echo "         host needs full hardening before converging"
            ;;
    esac
fi

if (( ${#PLAYBOOKS[@]} == 0 )); then
    echo ""
    echo "Nothing to run. Add playbooks to ${SERVICES_DIR}/${SERVICE}/deploy.conf."
    exit 0
fi

echo ""
echo "Playbooks:"
for playbook in "${PLAYBOOKS[@]}"; do
    echo "  ${playbook}"
done
echo ""

if [[ "${DRY_RUN}" == true ]]; then
    echo "Dry run, nothing executed."
    exit 0
fi

# ------------------------------------------------------------------------------
# Run
# ------------------------------------------------------------------------------
for index in "${!PLAYBOOKS[@]}"; do
    playbook="${PLAYBOOKS[index]}"

    if bash "${SCRIPTS_DIR}/run-playbook.sh" "${SERVICE}" "${playbook}"; then
        continue
    fi

    echo "" >&2
    echo "Error: Playbook '${playbook}' failed for service '${SERVICE}'." >&2
    echo "Fix the cause, then resume with:" >&2
    resume=("--only" "${playbook}")
    for remaining in "${PLAYBOOKS[@]:index+1}"; do
        resume+=("--only" "${remaining}")
    done
    echo "  bash ./scripts/service-deploy.sh ${SERVICE} ${resume[*]}" >&2
    exit 1
done

echo "=== Service '${SERVICE}' deployed ==="
