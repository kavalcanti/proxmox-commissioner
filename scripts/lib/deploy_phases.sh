#!/bin/bash
# Provisioning phase detection for lab-provisioning scripts
#
# A service VM moves through three connection profiles (see
# agents/design-patterns.md): root on ssh_port with a password, devops on
# ssh_port with a key, then devops on prod_ssh_port with a key. Playbooks
# hardcode one profile per play, so re-running an earlier stage against an
# already-hardened host cannot connect. These helpers probe the host to find
# out which stage it is actually in.

# Bootstrap sequence used when a service declares no BOOTSTRAP_PLAYBOOKS.
DEFAULT_BOOTSTRAP_PLAYBOOKS=(
    00-initial.yml
    10-base-security.yml
)

# Bootstrap playbooks that authenticate as root with a password. Skipped once
# the devops key works, so a failed harden run resumes instead of restarting.
DEPLOY_ROOT_PHASE_PLAYBOOKS=(
    00-initial.yml
)

# Read a top-level scalar from config/defaults/ansible/base.yml.
# Values like ssh_port / prod_ssh_port exist only as Ansible vars, but the
# orchestrator needs them to probe SSH before any playbook runs.
ansible_base_var() {
    local key="${1}"
    local base_vars="${CONFIG_DIR}/defaults/ansible/base.yml"
    local value

    if [[ ! -f "${base_vars}" ]]; then
        echo "Error: Ansible base vars not found at ${base_vars}" >&2
        return 1
    fi

    value="$(sed -n "s/^${key}:[[:space:]]*\(.*\)$/\1/p" "${base_vars}" | head -n 1)"
    value="${value%%#*}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"

    if [[ -z "${value}" ]]; then
        echo "Error: Could not read '${key}' from ${base_vars}" >&2
        return 1
    fi

    printf '%s' "${value}"
}

# base.yml stores ssh_key_dir with a literal '~', which Ansible expands but
# Bash does not when the value comes from a variable.
expand_home_path() {
    local path="${1}"

    if [[ "${path}" == "~" || "${path}" == "~/"* ]]; then
        path="${HOME}${path#\~}"
    fi

    printf '%s' "${path}"
}

# Path to the per-VM key that devops-user generates on the control node.
service_ssh_key_path() {
    local vm_name="${1}"
    local ssh_key_dir

    ssh_key_dir="$(expand_home_path "$(ansible_base_var ssh_key_dir)")" || return 1
    printf '%s/%s' "${ssh_key_dir}" "${vm_name}"
}

# True when we can log in with the given key. IdentitiesOnly keeps a loaded
# ssh-agent from producing a false positive.
probe_ssh_key() {
    local host="${1}"
    local port="${2}"
    local user="${3}"
    local keyfile="${4}"

    if [[ ! -f "${keyfile}" ]]; then
        return 1
    fi

    ssh -o BatchMode=yes \
        -o IdentitiesOnly=yes \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o LogLevel=ERROR \
        -o ConnectTimeout=5 \
        -i "${keyfile}" \
        -p "${port}" \
        "${user}@${host}" true >/dev/null 2>&1
}

# True when the port accepts a TCP connection.
probe_tcp() {
    local host="${1}"
    local port="${2}"

    timeout 5 bash -c "cat < /dev/null > /dev/tcp/${host}/${port}" 2>/dev/null
}

# Exports DEPLOY_PHASE as hardened / initialized / fresh / unreachable.
# Requires VM_NAME and VM_IP (see get_terraform_outputs).
detect_deploy_phase() {
    local ssh_port prod_ssh_port user_devops key

    ssh_port="$(ansible_base_var ssh_port)" || return 1
    prod_ssh_port="$(ansible_base_var prod_ssh_port)" || return 1
    user_devops="$(ansible_base_var user_devops)" || return 1
    key="$(service_ssh_key_path "${VM_NAME}")" || return 1

    if probe_ssh_key "${VM_IP}" "${prod_ssh_port}" "${user_devops}" "${key}"; then
        export DEPLOY_PHASE="hardened"
    elif probe_ssh_key "${VM_IP}" "${ssh_port}" "${user_devops}" "${key}"; then
        export DEPLOY_PHASE="initialized"
    elif probe_tcp "${VM_IP}" "${ssh_port}"; then
        # Root logs in with a password, which BatchMode cannot probe. An open
        # port with no working devops key means bootstrap has not run.
        export DEPLOY_PHASE="fresh"
    else
        export DEPLOY_PHASE="unreachable"
    fi
}

# Fails if any named playbook is missing, so a long recipe cannot die halfway.
validate_playbooks() {
    local playbook
    local missing=0

    for playbook in "$@"; do
        if [[ ! -f "${ANSIBLE_DIR}/playbooks/${playbook}" ]]; then
            echo "Error: Playbook not found: ${ANSIBLE_DIR}/playbooks/${playbook}" >&2
            missing=1
        fi
    done

    return "${missing}"
}

# Sources <service>/deploy.conf and exports the declared playbook lists.
load_deploy_conf() {
    local service="${1}"
    local conf="${SERVICES_DIR}/${service}/deploy.conf"

    BOOTSTRAP_PLAYBOOKS=("${DEFAULT_BOOTSTRAP_PLAYBOOKS[@]}")
    CONVERGE_PLAYBOOKS=()
    POSTDEPLOY_PLAYBOOKS=()

    if [[ ! -f "${conf}" ]]; then
        echo "Error: No deploy.conf for service '${service}'" >&2
        echo "Expected: ${conf}" >&2
        echo "Copy it from ${CONFIG_DIR}/defaults/services/service-template/deploy.conf" >&2
        return 1
    fi

    source "${conf}"

    validate_playbooks \
        "${BOOTSTRAP_PLAYBOOKS[@]}" \
        "${CONVERGE_PLAYBOOKS[@]}" \
        "${POSTDEPLOY_PLAYBOOKS[@]}" || return 1
}

# True when the playbook needs root password auth (see
# DEPLOY_ROOT_PHASE_PLAYBOOKS).
is_root_phase_playbook() {
    local playbook="${1}"
    local candidate

    if (( ${#DEPLOY_ROOT_PHASE_PLAYBOOKS[@]} == 0 )); then
        return 1
    fi

    for candidate in "${DEPLOY_ROOT_PHASE_PLAYBOOKS[@]}"; do
        if [[ "${playbook}" == "${candidate}" ]]; then
            return 0
        fi
    done

    return 1
}

# Echoes the bootstrap playbooks still applicable in the given phase.
bootstrap_playbooks_for_phase() {
    local phase="${1}"
    local playbook

    if [[ "${phase}" != "fresh" && "${phase}" != "initialized" ]]; then
        return 0
    fi

    if (( ${#BOOTSTRAP_PLAYBOOKS[@]} == 0 )); then
        return 0
    fi

    for playbook in "${BOOTSTRAP_PLAYBOOKS[@]}"; do
        if [[ "${phase}" == "initialized" ]] && is_root_phase_playbook "${playbook}"; then
            continue
        fi
        printf '%s\n' "${playbook}"
    done
}
