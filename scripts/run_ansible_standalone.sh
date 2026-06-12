#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

STANDALONE_DIR="${PROJECT_ROOT}/config/ansible-standalone"
INVENTORY_TEMPLATE="${STANDALONE_DIR}/inventory.yml"
BASE_VARS="${STANDALONE_DIR}/base.yml"
VAULT_VARS="${STANDALONE_DIR}/vault.yml"
ANSIBLE_CFG="${PROJECT_ROOT}/ansible/ansible.cfg"

print_help() {
    cat <<EOF
Usage: $(basename "$0") --ip <vm_ip> [--playbook <playbook>|--role <role>]

Run one Ansible playbook or role against a single VM IP using config/ansible-standalone.

Required:
  --ip        Target VM IP address

One of:
  --playbook  Playbook file name in ansible/playbooks/ (or absolute/relative path)
  --role      Role name in ansible/playbooks/roles/

Optional:
  -h, --help  Show this help message and exit

Examples:
  $(basename "$0") --ip 192.168.1.50 --playbook 23-node-exporter.yml
  $(basename "$0") --ip 192.168.1.50 --role install-node-exporter
EOF
}

VM_IP=""
PLAYBOOK=""
ROLE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ip)
            VM_IP="${2:-}"
            shift 2
            ;;
        --playbook)
            PLAYBOOK="${2:-}"
            shift 2
            ;;
        --role)
            ROLE="${2:-}"
            shift 2
            ;;
        -h|--help)
            print_help
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$1'" >&2
            print_help >&2
            exit 1
            ;;
    esac
done

if [[ -z "${VM_IP}" ]]; then
    echo "Error: --ip is required." >&2
    print_help >&2
    exit 1
fi

if [[ -n "${PLAYBOOK}" && -n "${ROLE}" ]]; then
    echo "Error: Use either --playbook or --role, not both." >&2
    print_help >&2
    exit 1
fi

if [[ -z "${PLAYBOOK}" && -z "${ROLE}" ]]; then
    echo "Error: You must provide --playbook or --role." >&2
    print_help >&2
    exit 1
fi

for required_file in "${INVENTORY_TEMPLATE}" "${BASE_VARS}"; do
    if [[ ! -f "${required_file}" ]]; then
        echo "Error: Missing required file '${required_file}'." >&2
        exit 1
    fi
done

if [[ ! -f "${VAULT_VARS}" ]]; then
    echo "Error: Missing '${VAULT_VARS}'." >&2
    echo "Create it from '${STANDALONE_DIR}/vault.yml.example' and encrypt it with ansible-vault." >&2
    exit 1
fi

if [[ ! -f "${ANSIBLE_CFG}" ]]; then
    echo "Error: Missing Ansible config at '${ANSIBLE_CFG}'." >&2
    exit 1
fi

RUN_DIR="$(mktemp -d)"
trap 'rm -rf "${RUN_DIR}"' EXIT

RUNTIME_INVENTORY="${RUN_DIR}/inventory.yml"
if ! sed "s/__VM_IP__/${VM_IP}/g" "${INVENTORY_TEMPLATE}" > "${RUNTIME_INVENTORY}"; then
    echo "Error: Could not build runtime inventory from '${INVENTORY_TEMPLATE}'." >&2
    exit 1
fi

PLAYBOOK_PATH=""
if [[ -n "${PLAYBOOK}" ]]; then
    if [[ -f "${PLAYBOOK}" ]]; then
        PLAYBOOK_PATH="${PLAYBOOK}"
    elif [[ -f "${PROJECT_ROOT}/ansible/playbooks/${PLAYBOOK}" ]]; then
        PLAYBOOK_PATH="${PROJECT_ROOT}/ansible/playbooks/${PLAYBOOK}"
    else
        echo "Error: Playbook not found: '${PLAYBOOK}'." >&2
        echo "Expected at '${PROJECT_ROOT}/ansible/playbooks/${PLAYBOOK}' or as a direct path." >&2
        exit 1
    fi
fi

if [[ -n "${ROLE}" ]]; then
    if [[ ! -d "${PROJECT_ROOT}/ansible/playbooks/roles/${ROLE}" ]]; then
        echo "Error: Role not found: '${ROLE}' in ansible/playbooks/roles/." >&2
        exit 1
    fi

    PLAYBOOK_PATH="${RUN_DIR}/run-role.yml"
    cat > "${PLAYBOOK_PATH}" <<EOF
---
- name: Run role ${ROLE} on single VM
  hosts: servers
  become: true
  roles:
    - role: ${ROLE}
EOF
fi

export ANSIBLE_CONFIG="${ANSIBLE_CFG}"

CMD=(ansible-playbook "${PLAYBOOK_PATH}"
    -i "${RUNTIME_INVENTORY}"
    -e "@${BASE_VARS}"
    -e "@${VAULT_VARS}")

if [[ -n "${ANSIBLE_VAULT_PASSWORD_FILE:-}" ]]; then
    CMD+=(--vault-password-file "${ANSIBLE_VAULT_PASSWORD_FILE}")
else
    CMD+=(--ask-vault-pass)
fi

echo "=== Standalone Ansible run ==="
echo "Target IP: ${VM_IP}"
if [[ -n "${ROLE}" ]]; then
    echo "Mode: role (${ROLE})"
else
    echo "Mode: playbook ($(basename "${PLAYBOOK_PATH}"))"
fi
echo "Inventory template: ${INVENTORY_TEMPLATE}"
echo ""
echo "Running: ${CMD[*]}"
"${CMD[@]}"
