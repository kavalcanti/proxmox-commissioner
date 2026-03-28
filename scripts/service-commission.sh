#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

print_help() {
    cat <<EOF
Usage: $(basename "$0") <service>

Provision a service VM with Terraform and optionally migrate it.

Arguments:
  service    Service name under services directory

Options:
  -h, --help Show this help message and exit

Example:
  $(basename "$0") template-service
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
source_config "${SERVICE}"

TERRAFORM_SERVICE_DIR="$(get_service_terraform_dir "${SERVICE}")"

if [[ ! -d "${TERRAFORM_SERVICE_DIR}" ]]; then
    echo "Error: No Terraform root for service '${SERVICE}'" >&2
    echo "Expected: ${TERRAFORM_SERVICE_DIR}/" >&2
    exit 1
fi

cd "${TERRAFORM_SERVICE_DIR}" || exit 1
ensure_proxmox_vm_module_symlink "${TERRAFORM_SERVICE_DIR}" || exit 1

eval $(ssh-agent)
trap 'ssh-agent -k > /dev/null 2>&1' EXIT

if [[ -n "${PROXMOX_SSH_KEY:-}" ]]; then
    ssh-add "${PROXMOX_SSH_KEY}"
else
    echo "Connecting to Proxmox requires ssh key."
    read -e -p "Proxmox ssh key location: " ssh_key_location
    ssh-add "${ssh_key_location}"
fi

echo "=== Running Terraform for service '${SERVICE}' ==="
terraform init
echo ""

terraform plan
echo ""

terraform apply
echo ""

echo "=== VM Information ==="
get_terraform_outputs "${SERVICE}"
echo "VM Name: ${VM_NAME}"
echo "VM ID:   ${VM_ID}"
echo "VM IP:   ${VM_IP}"
echo ""

if [[ -n "${TF_VAR_proxmox_destination_node:-}" && "${TF_VAR_proxmox_destination_node}" != "${TF_VAR_proxmox_node}" ]]; then
    echo "=== Migrating VM to '${TF_VAR_proxmox_destination_node}' ==="
    migrate_vm \
        "${VM_ID}" \
        "${TF_VAR_proxmox_node}" \
        "${TF_VAR_proxmox_node_ip}" \
        "${TF_VAR_proxmox_destination_node}" \
        "${TF_VAR_proxmox_destination_node_ip}" \
        "${TF_VAR_proxmox_ssh_user:-root}"
    echo ""
fi
echo ""
