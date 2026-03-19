#!/bin/bash
# Config and argument helpers for lab-provisioning scripts

# Get project root directory
init_directories() {
    if [[ -z "${PROJECT_ROOT}" ]]; then
        local script_dir
        script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        PROJECT_ROOT="$(cd "${script_dir}/../../" && pwd)"
        CONFIG_DIR="${PROJECT_ROOT}/config"
        TERRAFORM_DIR="${PROJECT_ROOT}/terraform"
        ANSIBLE_DIR="${PROJECT_ROOT}/ansible"
        SCRIPTS_DIR="${PROJECT_ROOT}/scripts"
    fi
    export PROJECT_ROOT CONFIG_DIR TERRAFORM_DIR ANSIBLE_DIR SCRIPTS_DIR
}

# Load configuration files with per-service layering.
#   1. Ansible config     (config/defaults/local.env)
#   2. Terraform/Proxmox  (config/defaults/terraform/infrastructure.env)
#   3. Service overrides (config/services/<service>/<service>.infrastructure.env)
load_config() {
    local service="${1}"

    source "${CONFIG_DIR}/defaults/local.env"
    source "${CONFIG_DIR}/defaults/terraform/infrastructure.env"

    local service_env="${CONFIG_DIR}/services/${service}/${service}.infrastructure.env"
    if [[ -f "${service_env}" ]]; then
        source "${service_env}"
    else
        echo "Warning: No service config found at ${service_env}" >&2
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

