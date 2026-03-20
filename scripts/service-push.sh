#!/bin/bash
set -e
DOCKER_DEPLOY="${2:-false}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

source_local_paths

SERVICE="${1}"
require_service "${SERVICE}"

load_config "${SERVICE}"
get_terraform_outputs "${SERVICE}"

echo "=== Deploying Service Files ==="
echo "Service: ${SERVICE}"
echo "VM Name: ${VM_NAME}"
echo "VM IP:   ${VM_IP}"
echo ""

run_ansible_playbook "${SERVICE}" "${ANSIBLE_DIR}/playbooks/25-file-push.yml"

echo ""

if [[ "${DOCKER_DEPLOY}" == "true" ]]; then
    echo "=== Deploying Docker Compose Stack ==="
    run_ansible_playbook "${SERVICE}" "${ANSIBLE_DIR}/playbooks/26-docker-deploy.yml"
fi
