# Lab Provisioning Tool
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/kavalcanti/lab-provisioning/blob/main/README.md)
[![pt-br](https://img.shields.io/badge/lang-pt--br-green.svg)](https://github.com/kavalcanti/lab-provisioning/blob/main/README.pt-br.md)

## What is this repo?

I have been homelabbing for a while and use proxmox to host VMs for my projects.
I have grown tired of click-ops'ing machines at home, so here is my attempt to
automate some of the effort.

### What does it do?

It provisions Virtual Machines on a Proxmox cluster and runs security and service
configuration through Ansible. Each **service** (e.g. media stack, database, web app)
gets its own Terraform state, config directory, and lifecycle -- so you can create,
secure, and configure VMs independently per service.

### Project structure

```
config/
  defaults/
    terraform/
      infrastructure.env               # Shared Terraform + Proxmox defaults (gitignored)
      infrastructure.env.example      # Example for infrastructure.env
    local.env.example                 # Template for local.env
    local.env                         # Ansible config/vault password file (gitignored)
    ansible/
      base.yml                     # Non-sensitive Ansible vars
      vault.yml.example           # Example vault file (encrypt this)
      vault.yml                   # Encrypted vault secrets used by playbooks
    services/
      service-template/
        service-template.infrastructure.env.example  # Template for per-service overrides
  services/
    <service>/
      <service>.infrastructure.env  # Per-service VM specs & overrides
      terraform/                    # Per-service Terraform root (state + outputs)
      filesystem/                   # Service files payload deployed to the VM
      ansible/
        <service>.inventory.yml  # Auto-generated inventory for this VM

terraform/
  modules/
    proxmox-vm/                      # Shared VM module (resources, variables, outputs)
    proxmox-lxc/

ansible/
  playbooks/                        # Security, Docker, Nginx, etc.
  roles/                            # Reusable Ansible roles

scripts/
  service-commission.sh   # Terraform apply + VM info (and optional qm migrate)
  service-migrate.sh             # Terraform state + qm migrate existing VM to another Proxmox node
  service-decommission.sh        # Terraform destroy
  new-service-from-template.sh  # Create `config/services/<service>/` from `config/defaults/services/service-template/`
  inventories-regenerate-all.sh  # Generate inventory for all services
  inventory-generate.sh         # Generate inventory for one service
  secure-vm.sh                    # Run security playbooks on a service VM
  install-docker.sh               # Install Docker on a service VM
  install-nginx.sh                # Install Nginx on a service VM
  mount-nfs.sh                   # Configure NFS mounts on a service VM
  service-push.sh                # Push files + (optional) docker compose deploy
  lib/common.sh                  # Shared helpers
```

### How does it do it?

Convenience scripts located in `scripts/` are the main entrypoints for
functionality. Every script takes a **service name** as its first argument.

1. Create a new Debian VM for a service.
`scripts/service-commission.sh <service>`

Optional: migrate an existing VM between Proxmox nodes.
`scripts/service-migrate.sh <service> <destination-node> [destination-node-ip]`

2. Generate / update the Ansible inventory from Terraform outputs.
`scripts/inventory-generate.sh <service>`
For all services, use `scripts/inventories-regenerate-all.sh`.

3. Run basic security roles. Can only run once per VM.
`scripts/secure-vm.sh <service>`

4. Install Docker.
`scripts/install-docker.sh <service>`

This configures Docker/UFW safety rules, but it does not automatically open the host
ports published by your `docker-compose.yml`. Add explicit `ufw allow` rules for
any ports you want reachable.

5. Install Nginx (and configure UFW for web traffic: `80/tcp` and `443/tcp`).
`scripts/install-nginx.sh <service>`

6. (Optional) Mount NFS shares.
`scripts/mount-nfs.sh <service>`

7. Deploy service files and (optional) docker compose stack.
`scripts/service-push.sh <service> [docker-deploy=true]`

## Before you begin

### Create a cloud-init template

I am using a cloud-init image for this. It will need to be created beforehand,
so that terraform can clone it when provisioning a new machine. Here are
instructions to make a Debian template machine. The ansible automation in this
repo will probably work for any debian base distros.

``` bash
# Download the Debian cloud image
cd /tmp
wget https://cloud.debian.org/images/cloud/trixie/latest/debian-13-generic-amd64.qcow2

# Import it as a VM template (creates VM ID 9000)
qm create 9000 --name debian-13-cloud --memory 2048 --cores 1 --net0 virtio,bridge=vmbr0
qm importdisk 9000 debian-13-generic-amd64.qcow2 local-lvm
qm set 9000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-9000-disk-0
qm set 9000 --ide2 local-lvm:cloudinit
qm set 9000 --boot c --bootdisk scsi0
qm set 9000 --agent enabled=1
qm set 9000 --serial0 socket
qm set 9000 --vga qxl 
# Convert to template
qm template 9000

# Clean up
rm debian-13-generic-amd64.qcow2
```

### Proxmox credentials

You will need to create a proxmox API key. I also recommend creating a separate
user for terraform. Enabling QEMU Agent requires SSH login, so the user should
be @PAM, not @PVE. This is probably overkill for homelab, but it is good
practice.

### Known issues

Some fiddling might be needed to get cloud-init available in proxmox. Storage
(local and local-lvm) might not be configured for snippet storage.

Check if snippets storage is configured on the Proxmox host with

```bash
pvesm status --content snippets 
```

If no storage is configured, run

```bash
pvesm set local --content vztmpl,iso,backup,snippets
```

## Configuration

All configuration is managed through environment variables in `config/`:

- **`config/defaults/terraform/infrastructure.env`** - Shared Terraform + Proxmox defaults (gitignored; create from `config/defaults/terraform/infrastructure.env.example`)
- **`config/defaults/local.env`** - Ansible configuration (gitignored; create from `config/defaults/local.env.example`)
- **`config/services/<service>/<service>.infrastructure.env`** - Per-service VM specs and overrides (gitignored; created from `config/defaults/services/service-template/`)

Config is layered: Ansible config (`local.env`) is loaded first, then shared
Terraform/Proxmox defaults (`terraform/infrastructure.env`), then per-service
overrides. Later files override earlier ones.

## First Time Setup

### Terraform configuration and VM specs

```bash
# 1. Copy Ansible config template (local.env)
cp config/defaults/local.env.example config/defaults/local.env

# 2. Copy shared Terraform/Proxmox defaults
cp config/defaults/terraform/infrastructure.env.example config/defaults/terraform/infrastructure.env

# 3. Edit Terraform/Proxmox defaults (tokens, passwords, clone/storage/network settings)
nano config/defaults/terraform/infrastructure.env
```

### Ansible configuration and secrets vault

#### Variable structure
- `config/defaults/ansible/base.yml`: Common non-sensitive Ansible variables
- `config/defaults/ansible/vault.yml`: Encrypted sensitive variables (used via Ansible vault)
- `config/services/<service>/ansible/inventory/<service>.deployment.yml`: Per-service inventory auto-generated from Terraform outputs

Set up your Ansible vault

```bash
# 1. (If needed) Create vault.yml from the example and encrypt it
cp config/defaults/ansible/vault.yml.example config/defaults/ansible/vault.yml
ansible-vault encrypt config/defaults/ansible/vault.yml

# 2. Edit vault (works for already-encrypted files too)
ansible-vault edit config/defaults/ansible/vault.yml
```

### Adding a new service

Use `scripts/new-service-from-template.sh <service>` to create
`config/services/<service>/` from `config/defaults/services/service-template/`,
then customize the per-service env.

```bash
# 1. Create the service directory from the template
./scripts/new-service-from-template.sh myservice

# 2. Edit the per-service infra env (VM specs + overrides)
nano config/services/myservice/myservice.infrastructure.env

# 3. Provision the VM
./scripts/service-commission.sh myservice

# 4. Generate/update the Ansible inventory
./scripts/inventory-generate.sh myservice

# 5. Secure the VM
./scripts/secure-vm.sh myservice
```

### Cluster: targeting different Proxmox nodes

The VM is cloned on the "source" Proxmox node (`TF_VAR_proxmox_node` /
`TF_VAR_proxmox_node_ip` from `config/defaults/terraform/infrastructure.env`).

To move the VM to another node after provisioning, set
`TF_VAR_proxmox_destination_node` and `TF_VAR_proxmox_destination_node_ip`
in the service's `*.infrastructure.env`.

## VM Provisioning

```bash
# Run the provisioning script for a service
./scripts/service-commission.sh arr

# After VM is created, generate Ansible inventory for that service
./scripts/inventory-generate.sh arr

# Secure the VM
./scripts/secure-vm.sh arr

# Install Docker
./scripts/install-docker.sh arr

# (Optional) Install Nginx
./scripts/install-nginx.sh arr

# (Optional) Push service files + deploy docker compose
./scripts/service-push.sh arr true
```

The scripts will:
1. Source Ansible config (`config/defaults/local.env`), Terraform/Proxmox
   defaults (`config/defaults/terraform/infrastructure.env`), and the service
   override (`config/services/<service>/<service>.infrastructure.env`)
2. Run Terraform in `config/services/<service>/terraform/` to create the VM
3. Show the VM IP address
4. Generate/update the per-service Ansible inventory from Terraform outputs
