# User guide

This file provides user instructions and documents workflows for reference.
`chmod +x` script files if you want to avoid invoking bash.

## Services

Services are the main abstraction for Proxmox Commissioner.
They are tied to a single VM.

Here is their base structure:

```
  services/
    <service>/
      <service>.infrastructure.env    # Per-service VM specs & overrides
      deploy.conf                     # Which playbooks this service runs, by phase
      deploy-service.sh               # Deploy entrypoint for this service
      terraform/                      # Per-service Terraform root (state + outputs)
      filetree/                       # Service files payload deployed to the VM
      ansible/
        <service>.inventory.yml       # Auto-generated inventory for this VM
```

Services will allow the scripts to run, maintain terraform state and configuration for each VM.
While multi VM services are not supported, I have been using `service-role` pattern to group them.

Files in the `service/filetree` should replicate desired absolute paths and will be pushed to the VM.
Content in `/home/*` dirs is handled different to maintain user permission. Other locations are copied with `root` ownership.

### Setting up a service

Services are generated from the template in `config/defaults/service/service-template`. Use the helper script:

```bash
bash scripts/new-service-from-template.sh your-service-name
```

This will add boilerplate filetree, `deploy.conf`, and deploy script, as well as `your-service-name.infrastructure.env` and required Terraform files.

Configure the infrastructure file with desired hardware configuration, list the playbooks you want in `deploy.conf`, then run the deploy script and your VM will be ready shortly.

```bash
bash config/services/your-service-name/deploy-service.sh --commission
```

### Full workflow

Use `scripts/new-service-from-template.sh <service>` to create `config/services/<service>/` from `config/defaults/services/service-template/`, then customize the per-service env.

```bash
# 1. Create the service directory from the template
bash scripts/new-service-from-template.sh myservice

# 2. Edit the per-service infra env (VM specs + overrides)
nano config/services/myservice/myservice.infrastructure.env

# 3. Pick the playbooks this service should run
nano config/services/myservice/deploy.conf

# 4. Provision the VM and configure it end to end
bash scripts/service-deploy.sh myservice --commission

# 5. Re-run any time to reconverge (hardening is skipped automatically)
bash scripts/service-deploy.sh myservice

# 6. Delete the VM
bash scripts/service-decommission.sh myservice
```

### Deploying and redeploying

`service-deploy.sh` is the normal way to run a service. It probes the VM over SSH first, so it knows whether initial hardening has already happened and never tries to re-run a stage that can no longer connect:

| What the probe finds | What runs |
|----------------------|-----------|
| `devops` reachable on the hardened SSH port | Converge playbooks only |
| `devops` reachable on port 22 | Hardening is finished, then converge |
| Port 22 open but no `devops` key yet | Full bootstrap, then converge |
| Nothing answers | Nothing; it tells you the VM is unreachable |

That means re-running the same command is safe, and there is no need to comment stages out by hand.

Playbook lists come from the service's `deploy.conf`:

```bash
# Run once on a fresh VM. Auto-skipped when the host is already hardened.
BOOTSTRAP_PLAYBOOKS=(
    00-initial.yml
    10-base-security.yml
)

# Idempotent, run on every deploy.
CONVERGE_PLAYBOOKS=(
    25-file-push.yml
    20-docker.yml
    26-docker-deploy.yml
)

# Imperative or non-idempotent. Only runs with --post-deploy.
POSTDEPLOY_PLAYBOOKS=(
    27-post-deploy.yml
)
```

Useful flags:

```bash
# See what would run, without running it
bash scripts/service-deploy.sh myservice --dry-run

# Provision the VM and generate its inventory first
bash scripts/service-deploy.sh myservice --commission

# Also run post-deploy.sh on the VM
bash scripts/service-deploy.sh myservice --post-deploy

# Run one playbook and stop
bash scripts/service-deploy.sh myservice --only 23-node-exporter.yml

# Override the probe when you already know the state
bash scripts/service-deploy.sh myservice --bootstrap
bash scripts/service-deploy.sh myservice --converge
```

Inventory regeneration is opt-in via `--refresh-inventory` (or implied by `--commission`), because `inventory-generate.sh` rewrites the file from scratch and drops hand-edited host vars such as `nfs_mountpoints`.

If a playbook fails, the run stops and prints the exact command to resume from that point.

## Configuration

All configuration is managed through environment variables in `config/`.
Configuration has layered load order, values from the last file substitute values from the first file.

1. `local.env` - Ansible and other environment config
2. `terraform/infrastructure.env` - Terraform/Proxmox defaults
3. `config/services/<service>/<service>.infrastructure.env` - service overrides

### Overview

#### Defaults level

- **`config/defaults/terraform/infrastructure.env`** 
  - Shared Terraform + Proxmox authentication defaults 
  - (gitignored; create from `config/defaults/terraform/infrastructure.env.example`)

- **`config/defaults/local.env`** 
  - Ansible and other additional environment configuration
  - (gitignored; create from `config/defaults/local.env.example`)
  
#### Service level
  
- **`config/services/<service>/<service>.infrastructure.env`** 
  - Per-service VM specs and terraform overrides
  - **Change VM specs (vCPU, RAM, HDD) here!**
  - (gitignored; generated from `config/defaults/services/service-template/`)

## Utility scripts

Utility scripts located in `scripts/` allow direct access to functionality and can be called from service deployment scripts. Every script takes a **service name** as its first argument.

Current functionality:

- Create a new service scaffold from template.
```bash
bash scripts/new-service-from-template.sh service-name
```

- Deploy a service, running only the phases it still needs.
```bash
bash scripts/service-deploy.sh service-name
bash scripts/service-deploy.sh service-name --help
```

- Create a new VM for a service.
```bash
bash scripts/service-commission.sh service-name
```

- Decommission (destroy) a service VM.
```bash
bash scripts/service-decommission.sh service-name
```

- Migrate a VM to another Proxmox node.
```bash
bash scripts/service-migrate.sh service-name destination-node destination-node-ip
```

- Push the service `filetree` payload to the VM.
```bash
bash scripts/run-playbook.sh service-name 25-file-push.yml
```

- Deploy the service's Docker Compose stack.
```bash
bash scripts/run-playbook.sh service-name 26-docker-deploy.yml
```

- Generate or refresh a service inventory from Terraform outputs.
```bash
bash scripts/inventory-generate.sh service-name
```

- Regenerate inventories for all services (or a single service).
```bash
bash scripts/inventories-regenerate-all.sh
```

- Run a specific Ansible playbook against a service VM.
```bash
bash scripts/run-playbook.sh service-name 15-web-server.yml
bash scripts/run-playbook.sh service-name 23-node-exporter.yml
```

## Default Configurations

### Default Terraform configuration and VM specs

```bash
# 1. Copy shared Terraform/Proxmox defaults
cp config/defaults/terraform/infrastructure.env.example config/defaults/terraform/infrastructure.env

# 1. Edit Terraform/Proxmox defaults (tokens, passwords, clone/storage/network settings)
nano config/defaults/terraform/infrastructure.env
```

### Default Ansible configuration and secrets vault
```bash
# 1. Copy Ansible config template (local.env)
cp config/defaults/local.env.example config/defaults/local.env
```

### Variable structure
- `config/defaults/ansible/base.yml`: Common non-sensitive Ansible variables (including Node Exporter listen address and optional UFW scrape rules for `23-node-exporter.yml`)
- `config/defaults/ansible/vault.yml`: Encrypted sensitive variables (used via Ansible vault)
- `config/services/<service>/ansible/inventory/<service>.deployment.yml`: Per-service inventory auto-generated from Terraform outputs

### Set up your Ansible vault

```bash
# 1. (If needed) Create vault.yml from the example and encrypt it
cp config/defaults/ansible/vault.yml.example config/defaults/ansible/vault.yml
ansible-vault encrypt config/defaults/ansible/vault.yml

# 2. Edit vault (works for already-encrypted files too)
ansible-vault edit config/defaults/ansible/vault.yml
```

## Cluster: targeting different Proxmox nodes

The VM is cloned on the "source" Proxmox node (`TF_VAR_proxmox_node` / `TF_VAR_proxmox_node_ip` from `config/defaults/terraform/infrastructure.env`).

To move the VM to another node after provisioning, set `TF_VAR_proxmox_destination_node` and `TF_VAR_proxmox_destination_node_ip` in the service's `*.infrastructure.env`.
