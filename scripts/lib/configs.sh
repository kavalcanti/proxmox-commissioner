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

# Returns the terraform working directory for a service.
# Uses TERRAFORM_DIR basename so the leaf folder is env-derived.
get_service_terraform_dir() {
    local service="${1}"
    local terraform_leaf
    terraform_leaf="$(basename "${TERRAFORM_DIR}")"
    echo "${SERVICES_DIR}/${service}/${terraform_leaf}"
}

# Exports PROJECT_ROOT & SERVICES_DIR
# Order: init paths (local.env needs CONFIG_DIR / ANSIBLE_DIR), default SERVICES_DIR,
# then source local.env so explicit exports in local.env always win. init_project_paths
# never reads SERVICES_DIR — only local.env and the default below set it.
source_local_paths() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    export PROJECT_ROOT="$(cd "${script_dir}/../../" && pwd)"
    init_project_paths "${PROJECT_ROOT}"
    export SERVICES_DIR="${CONFIG_DIR}/services"
    source "${PROJECT_ROOT}/config/defaults/local.env"
    if [[ -z "${SERVICES_DIR}" ]]; then
        export SERVICES_DIR="${CONFIG_DIR}/services"
    fi
}
# Explicity sources configuration files with per-service layering.
#   1. Ansible config     (config/defaults/local.env)
#   2. Terraform/Proxmox  (config/defaults/terraform/infrastructure.env)
#   3. Service overrides (${SERVICES_DIR}/<service>/<service>.infrastructure.env)
source_config() {
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
        for dir in "${SERVICES_DIR}"/*/; do
            [[ -d "${dir}" ]] && echo "  $(basename "${dir}")" >&2
        done
        exit 1
    fi
}

