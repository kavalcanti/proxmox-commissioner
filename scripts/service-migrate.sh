#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

if [[ -z "${1:-}" || -z "${2:-}" ]]; then
    echo "Usage: $(basename "$0") <service> <destination-node> [destination-node-ip]" >&2
    exit 1
fi

SERVICE="${1}"
DEST_NODE="${2}"
DEST_NODE_IP="${3:-}"

require_service "${SERVICE}"
source_config "${SERVICE}"

TERRAFORM_SERVICE_DIR="${PROJECT_ROOT}/config/services/${SERVICE}/terraform"
if [[ ! -d "${TERRAFORM_SERVICE_DIR}" ]]; then
    echo "Error: No Terraform root for service '${SERVICE}'" >&2
    echo "Expected: ${TERRAFORM_SERVICE_DIR}/" >&2
    exit 1
fi

cd "${TERRAFORM_SERVICE_DIR}" || exit 1

echo "=== Preparing Terraform state for '${SERVICE}' ==="
terraform init -input=false
echo ""

get_terraform_outputs_for_destroy "${SERVICE}"
echo "=== VM Information ==="
echo "Service: ${SERVICE}"
echo "VM Name: ${VM_NAME}"
echo "VM ID:   ${VM_ID}"
echo ""

eval $(ssh-agent)
if [[ -n "${PROXMOX_SSH_KEY:-}" ]]; then
    ssh-add "${PROXMOX_SSH_KEY}"
else
    echo "Connecting to Proxmox requires ssh key."
    read -e -p "Proxmox ssh key location: " ssh_key_location
    ssh-add "${ssh_key_location}"
fi

echo "=== Migrating VM to '${DEST_NODE}' ==="
migrate_vm \
    "${VM_ID}" \
    "${TF_VAR_proxmox_node}" \
    "${TF_VAR_proxmox_node_ip}" \
    "${DEST_NODE}" \
    "${DEST_NODE_IP}" \
    "${TF_VAR_proxmox_ssh_user:-root}"
echo ""
