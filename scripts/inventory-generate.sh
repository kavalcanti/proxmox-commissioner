#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

init_directories

SERVICE="${1}"
require_service "${SERVICE}"
load_config "${SERVICE}"

get_terraform_outputs "${SERVICE}"
echo "Updating Ansible inventory for ${SERVICE}..."

inventory_file="${CONFIG_DIR}/services/${SERVICE}/ansible/${SERVICE}.inventory.yml"
if [[ -f "${inventory_file}" ]]; then
    cp "${inventory_file}" "${inventory_file}.backup"
fi
cat > "${inventory_file}" << EOF
---
# Ansible Inventory - Auto-generated from Terraform
# Generated: $(date '+%Y-%m-%d %H:%M:%S')

all:
    hosts:
        localhost:
            ansible_connection: local
    children:
        servers:
            hosts:
                ${VM_NAME}:
                    ansible_host: "${VM_IP}"
                    ansible_user: "{{ user_root }}"
                    ansible_port: "{{ ssh_port }}"
                    ansible_password: "{{ vault_root_password }}"
                    ansible_become_password: "{{ vault_devops_password }}"
                    sys_hostname: "${VM_NAME}"
            vars:
                service_name: "${SERVICE}"
                docker_users:
                    - "{{ user_devops }}"
                # nfs_mountpoints:
                #     # List of NFS mounts to configure on the remote host(s)
                #     - name: ""
                #       server: ""
                #       # NFS export path (e.g. "/exports/media")
                #       export: ""
                #       # Local mount path on the target VM (e.g. "/mnt/media")
                #       mount_point: ""
                #       fstype: "nfs"
                #       # Mount options (examples)
                #       options:
                #         - "vers=4"
                #         - "proto=tcp"
                #         - "noatime"
                #       # If you later add NFSv4 Kerberos or similar auth, wire it via Ansible vars/vault
                #       # user: ""
                #       # password: ""
EOF
echo "Inventory updated for ${SERVICE}."
