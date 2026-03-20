#!/bin/bash
# Config and argument helpers for lab-provisioning scripts

# Computes and exports project paths
init_project_paths() {
    PROJECT_ROOT="${1}"
    CONFIG_DIR="${PROJECT_ROOT}/config"
    TERRAFORM_DIR="${PROJECT_ROOT}/terraform"
    ANSIBLE_DIR="${PROJECT_ROOT}/ansible"
    SCRIPTS_DIR="${PROJECT_ROOT}/scripts"

    export CONFIG_DIR TERRAFORM_DIR ANSIBLE_DIR SCRIPTS_DIR
}

# Exports PROJECT_ROOT & SERVICES_DIR
source_local_paths() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    export PROJECT_ROOT="$(cd "${script_dir}/../../" && pwd)"
    source "${PROJECT_ROOT}/config/defaults/local.env"
    if [[ -z "${SERVICES_DIR}" ]]; then
        export SERVICES_DIR="${CONFIG_DIR}/services"
    fi
    init_project_paths "${PROJECT_ROOT}"
}
# Load configuration files with per-service layering.
#   1. Ansible config     (config/defaults/local.env)
#   2. Terraform/Proxmox  (config/defaults/terraform/infrastructure.env)
#   3. Service overrides (config/services/<service>/<service>.infrastructure.env)
load_config() {
    local service="${1}"

    source "${CONFIG_DIR}/defaults/local.env"
    source "${CONFIG_DIR}/defaults/terraform/infrastructure.env"

    local service_env="${SERVICES_DIR}/${service}/${service}.infrastructure.env"
    if [[ -f "${service_env}" ]]; then
        source "${service_env}"
    else
        echo "Warning: No service config found at ${service_env}." >&2
    fi
}

# Print usage hint and exit
require_service() {
    if [[ -z "${1:-}" ]]; then
        echo "Usage: $(basename "$0") <service>" >&2
        echo "" >&2
        echo "Available services:" >&2
        for dir in "${PROJECT_ROOT}/config/services"/*/; do
            [[ -d "${dir}" ]] && echo "  $(basename "${dir}")" >&2
        done
        exit 1
    fi
}

