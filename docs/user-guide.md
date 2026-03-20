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
      terraform/                      # Per-service Terraform root (state + outputs)
      filesystem/                     # Service files payload deployed to the VM
      ansible/
        <service>.inventory.yml       # Auto-generated inventory for this VM
```

Services will allow the scripts to run, maintain terraform state and configuration for each VM.
While multi VM services are not supported, I have been using `service-role` pattern to group them.

Files in the `service/filesystem` should replicate desired absolute paths and will be pushed to the VM.
Content in `/home/*` dirs is handled different to maintain user permission. Other locations are copied with `root` ownership.

### Setting up a service

Services are generated from the template in `config/defaults/service/service-template`. Use the helper script:

```bash
bash scripts/new-service-from-template.sh your-service-name
```

This will add boilerplate filetree and deploy script, as well as `your-service-name.infrastructure.env` and required Terraform files.

Configure the infrastructure file with desired hardware configuration and run the deploy script and your VM will be ready shortly.

```bash
bash config/services/your-service-name/deploy-service.sh
```

### Full workflow

Use `scripts/new-service-from-template.sh <service>` to create `config/services/<service>/` from `config/defaults/services/service-template/`, then customize the per-service env.

```bash
# 1. Create the service directory from the template
bash scripts/new-service-from-template.sh myservice

# 2. Edit the per-service infra env (VM specs + overrides)
nano config/services/myservice/myservice.infrastructure.env

# 3. Provision the VM
bash scripts/service-commission.sh myservice

# 4. Generate/update the Ansible inventory
bash scripts/inventory-generate.sh myservice

# 5. Secure the VM
bash scripts/secure-vm.sh myservice

# 6. Delete the VM
bash scripts/service-decomission.sh myservice
```

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

- Push service filesystem files to the VM.
```bash
bash scripts/service-push.sh service-name
```

- Push service files and deploy Docker Compose stack.
```bash
bash scripts/service-push.sh service-name true
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
- `config/defaults/ansible/base.yml`: Common non-sensitive Ansible variables
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
