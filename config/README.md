# Configuration

This directory contains all configuration variables for lab provisioning.

## Config Layering

Scripts source config in this order (later files override earlier ones):

1. **`defaults/local.env`** -- Ansible configuration (vault password file,
   `ansible.cfg`, inventory path). **Gitignored** -- create from
   `config/defaults/local.env.example`.
2. **`defaults/terraform/infrastructure.env`** -- Shared Terraform + Proxmox
   defaults (template, storage, network, VM clone settings, and paths).
   **Gitignored** -- create from `config/defaults/terraform/infrastructure.env.example`.
3. **`services/<service>/<service>.infrastructure.env`** -- Per-service VM specs
   (name, id, cores, memory, disk) and any overrides for shared defaults (e.g.
   different network bridge or Proxmox node). **Gitignored**.

## Files
### `local.env`

Ansible configuration.

Path: `config/defaults/local.env`. **Gitignored** -- create it by copying
`config/defaults/local.env.example`.

It mainly configures `ANSIBLE_VAULT_PASSWORD_FILE`, `ANSIBLE_CONFIG`, and
`ANSIBLE_INVENTORY` for the scripts.

### `infrastructure.env`

Shared Terraform + Proxmox defaults.

Path: `config/defaults/terraform/infrastructure.env`. **Gitignored** -- create it
by copying `config/defaults/terraform/infrastructure.env.example`.

These values apply unless a service overrides them (e.g. different bridge or
Proxmox node).


### `<service>/<service>.infrastructure.env`

Per-service overrides.

Path: `config/services/<service>/<service>.infrastructure.env`. **Gitignored**.
At minimum, set `TF_VAR_vm_name` and `TF_VAR_vm_id`.

Only include values that differ from the shared defaults.

Service directories can also hold app config that Ansible or scripts deploy to the VM:
- `docker-compose.yml`
- `etc/fstab` (NFS mounts, etc.)
- `cron/` (crontab fragments)
- `nginx/` (site configs)

## VM Placement and Migration

By default VMs are **cloned on the node that holds the template** 
(`TF_VAR_proxmox_node`, defaulted from `config/defaults/terraform/infrastructure.env`).
To run the VM on a different node, set the destination
variables in the service config:

- `TF_VAR_proxmox_destination_node` -- target node name (e.g. `pve2`).
- `TF_VAR_proxmox_destination_node_ip` -- target node IP (for reference).

When `TF_VAR_proxmox_destination_node` is set and differs from `TF_VAR_proxmox_node`,
`scripts/service-commission-migrade.sh` will automatically run `qm migrate` after `terraform apply`
to move the VM to the destination node.

If `TF_VAR_proxmox_destination_node` is empty or matches `TF_VAR_proxmox_node`, migration is
skipped.

### Requirements

- The template must exist on `proxmox_node` (the clone source).
- SSH access from the machine running the script to `proxmox_node_ip` with
  `PROXMOX_SSH_KEY` must be configured.
- Both nodes must share storage or have compatible storage backends for
  migration to succeed.
