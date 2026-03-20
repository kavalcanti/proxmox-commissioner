#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"

print_help() {
    cat <<EOF
Usage: $(basename "$0") <service>

Generate or refresh the Ansible inventory for one service.

Arguments:
  service    Service name under config/services/

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

SERVICE="${1}"
require_service "${SERVICE}"
source_config "${SERVICE}"

get_terraform_outputs "${SERVICE}"
echo "Updating Ansible inventory for ${SERVICE}..."

inventory_file="${SERVICES_DIR}/${SERVICE}/ansible/${SERVICE}.inventory.yml"
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
                services_dir: "${SERVICES_DIR}"
                service_name: "${SERVICE}"
                docker_users:
                    - "{{ user_devops }}"
                # Uncomment and fill in the sites to enable on the remote host(s).
                # nginx_sites_enabled_configs:
                #     - "site-a-config.conf"
                #     - "site-b-config.conf"
                #     - "site-c-config.conf"
                # Uncomment and fill in the following variables to configure NFS mounts on the remote host(s).
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
