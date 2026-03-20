#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

print_help() {
    cat <<EOF
Usage: $(basename "$0") <service> <playbook>

Run an Ansible playbook for a provisioned service VM.

Arguments:
  service     Service name under config/services/
  playbook    Playbook file name in ansible/playbooks/

Options:
  -h, --help Show this help message and exit

Example:
  $(basename "$0") template-service 15-web-server.yml
EOF
}

case "${1:-}" in
    -h|--help)
        print_help
        exit 0
        ;;
    -*)
        echo "Error: Unknown option '${1}'" >&2
        print_help >&2
        exit 1
        ;;
esac

require_service "${1:-}"

SERVICE="${1}"
PLAYBOOK="${2}"

if [[ -z "${PLAYBOOK}" ]]; then
    print_help >&2
    exit 1
fi

require_service "${SERVICE}"

source_config "${SERVICE}"
get_terraform_outputs "${SERVICE}"

echo "=== Running playbook ${PLAYBOOK} ==="
echo "Service: ${SERVICE}"
echo "VM Name: ${VM_NAME}"
echo "VM IP:   ${VM_IP}"
echo ""

run_ansible_playbook "${SERVICE}" "${ANSIBLE_DIR}/playbooks/${PLAYBOOK}"
