#!/bin/bash
# Terraform operation helpers for lab-provisioning scripts

# Name of the symlink in each service terraform root → shared proxmox-vm module.
PROXMOX_VM_MODULE_LINK_NAME="proxmox-vm-module"

# Point ./${PROXMOX_VM_MODULE_LINK_NAME} at this checkout's module so services work
# from any SERVICES_DIR (external trees, symlinks, etc.) without fragile ../ paths.
ensure_proxmox_vm_module_symlink() {
    local terraform_dir="${1}"
    local module_src="${TERRAFORM_DIR}/modules/proxmox-vm"
    local link="${terraform_dir}/${PROXMOX_VM_MODULE_LINK_NAME}"

    if [[ ! -d "${module_src}" ]]; then
        echo "Error: Proxmox VM module not found at ${module_src}" >&2
        return 1
    fi
    ln -sfn "${module_src}" "${link}"
}

# Get terraform outputs for a service and export VM_NAME / VM_IP
get_terraform_outputs() {
    local service="${1}"
    local terraform_dir
    terraform_dir="$(get_service_terraform_dir "${service}")"

    if [[ ! -d "${terraform_dir}" ]]; then
        echo "Error: No Terraform root for service '${service}'" >&2
        echo "Expected: ${terraform_dir}/" >&2
        exit 1
    fi

    ensure_proxmox_vm_module_symlink "${terraform_dir}" || exit 1

    cd "${terraform_dir}" || {
        echo "Error: Cannot access terraform directory: ${terraform_dir}" >&2
        exit 1
    }

    VM_NAME=$(terraform output -raw vm_name 2>/dev/null) || {
        echo "Error: Cannot read Terraform outputs for '${service}'. Run 'make-debian.sh ${service}' first." >&2
        exit 1
    }
    VM_ID=$(terraform output -raw vm_id 2>/dev/null) || true
    VM_IP=$(terraform output -raw vm_ip 2>/dev/null) || true

    if [[ "${VM_IP}" == "waiting for IP..." ]] || [[ -z "${VM_IP}" ]]; then
        echo "Error: VM IP not available yet for service '${service}'" >&2
        exit 1
    fi

    export VM_NAME VM_ID VM_IP
}

# Get terraform outputs for decommission (VM_ID, VM_NAME only; skips IP check).
# Use when the VM may be down or unreachable.
get_terraform_outputs_for_destroy() {
    local service="${1}"
    local terraform_dir
    terraform_dir="$(get_service_terraform_dir "${service}")"

    if [[ ! -d "${terraform_dir}" ]]; then
        echo "Error: No Terraform root for service '${service}'" >&2
        echo "Expected: ${terraform_dir}/" >&2
        exit 1
    fi

    ensure_proxmox_vm_module_symlink "${terraform_dir}" || exit 1

    cd "${terraform_dir}" || {
        echo "Error: Cannot access terraform directory: ${terraform_dir}" >&2
        exit 1
    }

    VM_NAME=$(terraform output -raw vm_name 2>/dev/null) || {
        echo "Error: Cannot read Terraform outputs for '${service}'. Has the service been provisioned?" >&2
        exit 1
    }
    VM_ID=$(terraform output -raw vm_id 2>/dev/null) || true

    if [[ -z "${VM_ID}" ]]; then
        echo "Error: VM_ID not available for service '${service}'" >&2
        exit 1
    fi

    export VM_NAME VM_ID
}

