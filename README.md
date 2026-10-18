# Proxmox Commissioner

[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/kavalcanti/proxmox-commissioner/blob/main/README.md)
[![pt-br](https://img.shields.io/badge/lang-pt--br-green.svg)](https://github.com/kavalcanti/proxmox-commissioner/blob/main/README.pt-br.md)

## What is Proxmox Commissioner?

A small CLI, `pvc`, that turns one YAML manifest into running services on Proxmox Virtual Environment. Terraform creates the VMs, Ansible configures them, and `pvc` wires the two together.

It is aimed at homelabbers and small teams running PVE.

### What can it do?

1. Create one or more VMs per service (a database and an app host, say) from a single file
2. Boot every VM already hardened: key-only SSH on a custom port, root locked, firewall and fail2ban on
3. Install Docker, nginx with Cloudflare DNS-01 certificates, NFS mounts, Node Exporter, cloudflared
4. Push files and deploy Docker Compose stacks to the right host
5. Move a host to another cluster node by changing one line

### How does it work?

```bash
uv sync                          # install pvc
uv run pvc init                  # creates site.yml and secrets.yml
uv run pvc site apply            # downloads the cloud image to every node
uv run pvc new blog --hosts db,app
uv run pvc up blog               # create the VMs and configure them
```

A service is one file, `services/blog/service.yml`:

```yaml
defaults:
  node: pve1
  vlan: 30
  memory: 2048

hosts:
  db:
    vm_id: 1101
    ip: 172.20.30.21/24          # omit for DHCP
    roles: [compose, node_exporter]
  app:
    vm_id: 1102
    roles: [nginx, compose]
    vars:
      nginx_sites_enabled_configs: [blog.conf]
```

`pvc up` validates the manifest, plans and applies Terraform, waits for SSH, generates the Ansible inventory and runs one playbook against all hosts in parallel. Run it again after any change.

Read the [Setup guide](docs/setup-guide.md) and the [User guide](docs/user-guide.md) before starting.

### Commands

| Command | What it does |
|---------|--------------|
| `pvc init` | Create `site.yml` and `secrets.yml`, install Ansible collections, check prerequisites |
| `pvc site apply` | Download the cloud images listed in `site.yml` to every node |
| `pvc site configure [--node n] [--tags t]` | Install node_exporter and smartctl_exporter on the Proxmox nodes |
| `pvc new <svc> [--hosts a,b]` | Scaffold `services/<svc>/service.yml` |
| `pvc validate [svc]` | Check manifests offline |
| `pvc plan <svc>` | Validate, then `terraform plan` |
| `pvc up <svc>` | Apply Terraform, then configure the hosts |
| `pvc converge <svc> [--host h] [--tags t]` | Re-run configuration only |
| `pvc ssh <svc> <host>` | SSH in with the service key |
| `pvc status [svc]` | Hosts, addresses and nodes |
| `pvc down <svc>` | Destroy the service's VMs |

### Project structure

```
pyproject.toml                  # uv project, `pvc` entry point
pvc/                            # the CLI
  site/                         # cluster-level work: image downloads, Proxmox node configuration
site.example.yml                # cluster-wide settings (copy: site.yml, gitignored)
secrets.example.yml             # secrets (copy: secrets.yml, encrypt it, gitignored)
terraform/
  site/                         # cloud image downloads, one state for the whole cluster
  service/                      # one root shared by every service, for_each over hosts
  modules/proxmox-vm/           # VM + hardened cloud-init
ansible/
  site.yml                      # the VM playbook; one play per role group
  pve-hosts.yml                 # the Proxmox nodes themselves (`pvc site configure`)
  roles/
services/<svc>/
  service.yml                   # the one file you edit
  filetree/                     # files for every host of the service
  hosts/<host>/filetree/        # files for one host, overrides the above
  post-deploy.sh                # optional
  .pvc/                         # tfstate, tfvars and generated inventory (gitignored)
```
