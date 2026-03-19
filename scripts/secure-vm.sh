#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

init_directories

SERVICE="${1}"
require_service "${SERVICE}"

load_config "${SERVICE}"
get_terraform_outputs "${SERVICE}"

echo "=== Securing VM ==="
echo "Service: ${SERVICE}"
echo "VM Name: ${VM_NAME}"
echo "VM IP:   ${VM_IP}"
echo ""

run_ansible_playbook "${SERVICE}" "${ANSIBLE_DIR}/playbooks/90-security.yml"
