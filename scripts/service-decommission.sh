#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

source_local_paths
require_service "${1:-}"

SERVICE="${1}"
load_config "${SERVICE}"

TERRAFORM_SERVICE_DIR="${CONFIG_DIR}/services/${SERVICE}/terraform"

if [[ ! -d "${TERRAFORM_SERVICE_DIR}" ]]; then
    echo "Error: No Terraform root for service '${SERVICE}'" >&2
    echo "Expected: ${TERRAFORM_SERVICE_DIR}/" >&2
    exit 1
fi

cd "${TERRAFORM_SERVICE_DIR}" || exit 1

# Ensure we have terraform state (service was provisioned)
if ! terraform output vm_id &>/dev/null; then
    echo "Error: No Terraform state for service '${SERVICE}'. Nothing to decommission." >&2
    exit 1
fi

get_terraform_outputs_for_destroy "${SERVICE}"
echo "VM Name: ${VM_NAME}"
echo "VM ID:   ${VM_ID}"
echo ""

# Revert migration so Terraform finds the VM on the expected node before destroy
eval $(ssh-agent)
if [[ -n "${PROXMOX_SSH_KEY:-}" ]]; then
    ssh-add "${PROXMOX_SSH_KEY}"
else
    echo "Connecting to Proxmox requires ssh key."
    read -e -p "Proxmox ssh key location: " ssh_key_location
    ssh-add "${ssh_key_location}"
fi

if ! revert_vm_migration; then
    echo "Warning: Revert migration failed (VM may already be on source node). Continuing with destroy anyway." >&2
fi
echo ""

echo "=== Running Terraform destroy for service '${SERVICE}' ==="
terraform init
echo ""

terraform plan
echo ""

terraform destroy
echo ""
echo "Decommission complete: service '${SERVICE}' has been destroyed."
