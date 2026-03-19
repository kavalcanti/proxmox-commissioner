#!/bin/bash
# Terraform operation helpers for lab-provisioning scripts

# Get terraform outputs for a service and export VM_NAME / VM_IP
get_terraform_outputs() {
    local service="${1}"
    local terraform_dir="${CONFIG_DIR}/services/${service}/terraform"

    if [[ ! -d "${terraform_dir}" ]]; then
        echo "Error: No Terraform root for service '${service}'" >&2
        echo "Expected: ${terraform_dir}/" >&2
        exit 1
    fi

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
    local terraform_dir="${CONFIG_DIR}/services/${service}/terraform"

    if [[ ! -d "${terraform_dir}" ]]; then
        echo "Error: No Terraform root for service '${service}'" >&2
        echo "Expected: ${terraform_dir}/" >&2
        exit 1
    fi

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

