# Proxmox Commissioner
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/kavalcanti/lab-provisioning/blob/main/README.md)
[![pt-br](https://img.shields.io/badge/lang-pt--br-green.svg)](https://github.com/kavalcanti/lab-provisioning/blob/main/README.pt-br.md)

## What is this Proxmox Commissioner?

A Terraform and Ansible tool to streamline services running on Proxmox Virtual Environment virtual machines.

It is aimed at homelabbers or small teams running PVE.

### What can it do?

1. Create, configure and secure VMs
2. Push and deploy entire docker stacks with NFS remote storage support
3. Push configs and deploy nginx with cloudflare DNS-01 certificates
4. Add or remove services maintaining configuration
5. Conveniently migrate VMs across cluster nodes

It provisions Virtual Machines on a Proxmox cluster and runs security and service configuration through Ansible. Each **service** (e.g. media stack, database, web app) gets its own Terraform state, config  directory, and lifecycle -- so you can create, secure, and configure VMs independently per service.

### How does it do it?

Simply create a new service from template from the project root dir and run the deploy script!

```bash
bash scripts/new-service-from-template.sh service-name
bash configs/services/service-name/deploy-service.sh
```
This will create a VM with the default configuration:
- 1vCPU
- 1GB ram
- 16gb HDD 

From here a series of Ansible playbooks and roles can:
- Add non-root user
- Harden SSH config
- Install Docker and docker compose
- Install, configure and deploy nginx
- Configure NFS shares
- Copy configuration files
- Deploy docker stacks

Make sure to read the [Setup guide](docs/setup-guide.md) and the [User Guide](docs/user-guide.md) before starting!

### Project structure

```
config/
  defaults/
    terraform/
      infrastructure.env              # Shared Terraform + Proxmox defaults (gitignored)
      infrastructure.env.example      # Example for infrastructure.env
    local.env.example                 # Template for local.env
    local.env                         # Ansible config/vault password file (gitignored)
    ansible/
      base.yml                        # Non-sensitive Ansible vars
      vault.yml.example               # Example vault file (encrypt this)
      vault.yml                       # Encrypted vault secrets used by playbooks
    services/
      service-template/
        service-template.infrastructure.env.example  # Template for per-service overrides
  services/
    <service>/
      <service>.infrastructure.env    # Per-service VM specs & overrides
      terraform/                      # Per-service Terraform root (state + outputs)
      filesystem/                     # Service files payload deployed to the VM
      ansible/
        <service>.inventory.yml       # Auto-generated inventory for this VM

terraform/
  modules/
    proxmox-vm/                       # Shared VM module (resources, variables, outputs)
    proxmox-lxc/

ansible/
  playbooks/                          # Security, Docker, Nginx, etc.
  roles/                              # Reusable Ansible roles

scripts/
  service-commission.sh               # Terraform apply + VM info (and optional qm migrate)
  service-migrate.sh                  # Terraform state + qm migrate existing VM to another Proxmox node
  service-decommission.sh             # Terraform destroy
  new-service-from-template.sh        # Create `config/services/<service>/` from `config/defaults/services/service-template/`
  inventories-regenerate-all.sh       # Generate inventory for all services
  inventory-generate.sh               # Generate inventory for one service
  secure-vm.sh                        # Run security playbooks on a service VM
  install-docker.sh                   # Install Docker on a service VM
  install-nginx.sh                    # Install Nginx on a service VM
  mount-nfs.sh                        # Configure NFS mounts on a service VM
  service-push.sh                     # Push files + (optional) docker compose deploy
  lib/common.sh                       # Shared helpers
```