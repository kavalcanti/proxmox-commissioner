#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

source_local_paths

SERVICE="${1}"
PLAYBOOK="${2}"

if [[ -z "${PLAYBOOK}" ]]; then
    echo "Usage: $(basename "$0") <service> <playbook>" >&2
    echo "" >&2
    echo "Example: $(basename "$0") template-service 15-web-server.yml" >&2
    exit 1
fi

require_service "${SERVICE}"

load_config "${SERVICE}"
get_terraform_outputs "${SERVICE}"

echo "=== Running playbook ${PLAYBOOK} ==="
echo "Service: ${SERVICE}"
echo "VM Name: ${VM_NAME}"
echo "VM IP:   ${VM_IP}"
echo ""

run_ansible_playbook "${SERVICE}" "${ANSIBLE_DIR}/playbooks/${PLAYBOOK}"
