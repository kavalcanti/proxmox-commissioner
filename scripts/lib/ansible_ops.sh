#!/bin/bash
# Ansible operation helpers for lab-provisioning scripts

# Run ansible playbook with common flags, optionally limited to a single host
# Passes base.yml and vault.yml as extra vars so inventory can resolve {{ vault_* }} etc.
run_ansible_playbook() {
    local service="${1}"
    local playbook_path="${2}"
    local limit="${3:-}"

    source "${CONFIG_DIR}/defaults/local.env"
    local base_vars="${CONFIG_DIR}/defaults/ansible/base.yml"
    local vault_vars="${CONFIG_DIR}/defaults/ansible/vault.yml"
    local inventory="${CONFIG_DIR}/services/${service}/ansible/${service}.inventory.yml"

    local cmd=(ansible-playbook "${playbook_path}"
        -e "@${base_vars}"
        -e "@${vault_vars}"
        -i "${inventory}")
        
    # If a vault password file is configured, don't prompt
    if [[ -n "${ANSIBLE_VAULT_PASSWORD_FILE:-}" ]]; then
        cmd+=(--vault-password-file "${ANSIBLE_VAULT_PASSWORD_FILE}")
    else
        cmd+=(--ask-vault-pass)
    fi

    echo "Running Ansible playbook: ${cmd[*]}"
    "${cmd[@]}"
}
