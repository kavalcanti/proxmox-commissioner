#!/bin/bash
# VM operation helpers for lab-provisioning scripts

# Migrate a VM from the clone source node to a destination node via qm migrate.
#
# Args (optional; fall back to TF_VAR_* / VM_ID when omitted):
#   1) vm_id
#   2) source_node
#   3) source_ip
#   4) dest_node
#   5) dest_ip
#   6) ssh_user
#
# Skips migration if destination is unset or matches the source node.
migrate_vm() {
    local vm_id="${1:-${VM_ID}}"
    local source_node="${2:-${TF_VAR_proxmox_node:-}}"
    local source_ip="${3:-${TF_VAR_proxmox_node_ip:-}}"
    local dest_node="${4:-${TF_VAR_proxmox_destination_node:-}}"
    local dest_ip="${5:-${TF_VAR_proxmox_destination_node_ip:-}}"
    local ssh_user="${6:-${TF_VAR_proxmox_ssh_user:-root}}"

    if [[ -z "${dest_node}" ]] || [[ "${dest_node}" == "${source_node}" ]]; then
        echo "No migration needed (destination node is same as source or unset)."
        return 0
    fi

    if [[ -z "${vm_id}" ]]; then
        echo "Error: VM_ID is empty, cannot migrate." >&2
        return 1
    fi

    echo "=== Migrating VM ${vm_id} from '${source_node}' to '${dest_node}' ==="
    ssh -o StrictHostKeyChecking=no "${ssh_user}@${source_ip}" \
        "qm migrate ${vm_id} ${dest_node} --online --with-local-disks" || {
        echo "Error: Migration of VM ${vm_id} to '${dest_node}' failed." >&2
        return 1
    }
    echo "Migration complete: VM ${vm_id} is now on '${dest_node}'."

    # Copy the snippet file so subsequent reboots work on the new node.
    sync_cloudinit_snippet_to_destination "${source_ip}" "${dest_ip}" "${ssh_user}" || true
}


# Revert VM migration: move VM from destination node back to original (source) node.
# Required before terraform destroy so Terraform finds the VM on the expected node.
# Skips if no migration was done (destination unset or same as source).
# Requires: VM_ID, TF_VAR_proxmox_node, TF_VAR_proxmox_destination_node,
#           TF_VAR_proxmox_destination_node_ip, TF_VAR_proxmox_ssh_user
revert_vm_migration() {
    local vm_id="${VM_ID}"
    local source_node="${TF_VAR_proxmox_node:-}"
    local source_ip="${TF_VAR_proxmox_node_ip:-}"
    local dest_node="${TF_VAR_proxmox_destination_node:-}"
    local dest_ip="${TF_VAR_proxmox_destination_node_ip:-}"
    local ssh_user="${TF_VAR_proxmox_ssh_user:-root}"

    if [[ -z "${dest_node}" ]] || [[ "${dest_node}" == "${source_node}" ]]; then
        echo "No migration to revert (destination node is same as source or unset)."
        return 0
    fi

    if [[ -z "${vm_id}" ]]; then
        echo "Error: VM_ID is empty, cannot revert migration." >&2
        return 1
    fi

    if [[ -z "${dest_ip}" ]]; then
        echo "Error: TF_VAR_proxmox_destination_node_ip is required to revert migration." >&2
        return 1
    fi

    echo "=== Reverting migration: VM ${vm_id} from '${dest_node}' back to '${source_node}' ==="
    ssh -o StrictHostKeyChecking=no "${ssh_user}@${dest_ip}" \
        "qm migrate ${vm_id} ${source_node} --online --with-local-disks" || {
        echo "Error: Revert migration of VM ${vm_id} to '${source_node}' failed." >&2
        return 1
    }
    echo "Revert complete: VM ${vm_id} is now on '${source_node}'."

    # Keep cloud-init snippet storage consistent when migrating back.
    sync_cloudinit_snippet_to_destination "${dest_ip}" "${source_ip}" "${ssh_user}" || true
}

# Copy the generated cloud-init snippet file to the destination node.
#
# This is needed when `datastore_snippets` is backed by node-local storage
# (e.g. Proxmox `local`), so the snippet file doesn't exist on the destination.
sync_cloudinit_snippet_to_destination() {
    local source_ip="$1"
    local dest_ip="$2"
    local ssh_user="$3"

    local snippets_storage="${TF_VAR_datastore_snippets:-}"
    local filename="cloud-init-${VM_NAME}.yaml"
    local relpath="snippets/${filename}"

    if [[ -z "${snippets_storage}" ]]; then
        echo "Warning: TF_VAR_datastore_snippets is empty; skipping cloud-init snippet sync." >&2
        return 0
    fi
    if [[ -z "${dest_ip}" ]]; then
        echo "Warning: TF_VAR_proxmox_destination_node_ip is empty; skipping cloud-init snippet sync." >&2
        return 0
    fi

    local src_path dest_path
    src_path="$(ssh -o StrictHostKeyChecking=no "${ssh_user}@${source_ip}" \
        "pvesm path ${snippets_storage}:${relpath}" 2>/dev/null || true)"
    dest_path="$(ssh -o StrictHostKeyChecking=no "${ssh_user}@${dest_ip}" \
        "pvesm path ${snippets_storage}:${relpath}" 2>/dev/null || true)"

    if [[ -z "${src_path}" ]] || [[ -z "${dest_path}" ]]; then
        echo "Warning: Could not resolve snippet paths via pvesm on source/dest; skipping sync." >&2
        return 0
    fi

    if ! ssh -o StrictHostKeyChecking=no "${ssh_user}@${source_ip}" \
        "test -f '${src_path}'" >/dev/null 2>&1; then
        echo "Warning: cloud-init snippet '${filename}' not found on source (${source_ip}); skipping sync." >&2
        return 0
    fi

    echo "Syncing cloud-init snippet to destination (${dest_ip}): ${relpath}"
    ssh -o StrictHostKeyChecking=no "${ssh_user}@${dest_ip}" \
        "mkdir -p '$(dirname "${dest_path}")'"

    local tmp_file
    tmp_file="$(mktemp)"
    scp -o StrictHostKeyChecking=no "${ssh_user}@${source_ip}:${src_path}" "${tmp_file}"
    scp -o StrictHostKeyChecking=no "${tmp_file}" "${ssh_user}@${dest_ip}:${dest_path}"
    rm -f "${tmp_file}"
}
