# Ansible-only workflow (single VM by IP)

This guide shows how to run this repository's Ansible playbooks (or a single role) against one VM IP, without running the full service commission workflow.

## Quickest path (convenience script)

Use:

```bash
bash scripts/run_ansible_standalone.sh --ip VM_IP --playbook PLAYBOOK
bash scripts/run_ansible_standalone.sh --ip VM_IP --role ROLE
```

Examples:

```bash
bash scripts/run_ansible_standalone.sh --ip 192.168.1.50 --playbook 23-node-exporter.yml
bash scripts/run_ansible_standalone.sh --ip 192.168.1.50 --role install-node-exporter
```

This script reads:
- `config/ansible-standalone/inventory.yml` (uses `__VM_IP__` placeholder)
- `config/ansible-standalone/base.yml`
- `config/ansible-standalone/vault.yml` (encrypted)

## Prerequisites

- You are in the project root:

```bash
cd /home/kaoue/code/proxmox-commissioner
```

- Required files exist:
  - `config/defaults/local.env`
  - `config/ansible-standalone/base.yml`
  - `config/ansible-standalone/inventory.yml`
  - `config/ansible-standalone/vault.yml` (encrypted)

- Python and Ansible are available (use `uv`):

```bash
uv venv
source .venv/bin/activate
uv pip install ansible
```

## Option 1: Existing service inventory (recommended when service already exists)

If your VM already belongs to a service in `config/services/<service>/`, use the existing helper script.

1. Regenerate inventory from Terraform outputs:

```bash
bash scripts/inventory-generate.sh <service>
```

2. Run one playbook:

```bash
bash scripts/run-playbook.sh <service> 23-node-exporter.yml
```

This uses:
- inventory: `config/services/<service>/ansible/<service>.inventory.yml`
- vars files: `config/defaults/ansible/base.yml` and `config/defaults/ansible/vault.yml`

## Option 2: Run directly against any VM IP (manual mode)

Use this when you only have an IP and credentials.

### 1) Create a temporary inventory file

Create `tmp/single-vm.inventory.yml` (or use `config/ansible-standalone/inventory.yml` with your own placeholder replacement logic):

```yaml
all:
  vars:
    ansible_connection: ssh
  children:
    servers:
      hosts:
        single_vm:
          ansible_host: "192.168.1.50"
          ansible_user: "{{ user_devops }}"
          ansible_port: "{{ prod_ssh_port }}"
          ansible_ssh_private_key_file: "{{ ssh_private_key }}"
```

Notes:
- Replace `192.168.1.50` with your VM IP.
- If you need password auth, swap key auth for:
  - `ansible_password: "{{ vault_devops_password }}"`
  - and remove `ansible_ssh_private_key_file`.

### 2) Export Ansible config

```bash
source config/defaults/local.env
export ANSIBLE_CONFIG="$PWD/ansible/ansible.cfg"
```

### 3) Run a playbook against that VM

```bash
ansible-playbook ansible/playbooks/23-node-exporter.yml \
  -i tmp/single-vm.inventory.yml \
  -e @config/ansible-standalone/base.yml \
  -e @config/ansible-standalone/vault.yml \
  --ask-vault-pass
```

If your `local.env` defines `ANSIBLE_VAULT_PASSWORD_FILE`, you can use:

```bash
ansible-playbook ansible/playbooks/23-node-exporter.yml \
  -i tmp/single-vm.inventory.yml \
  -e @config/ansible-standalone/base.yml \
  -e @config/ansible-standalone/vault.yml \
  --vault-password-file "$ANSIBLE_VAULT_PASSWORD_FILE"
```

## Run one role only (against a single VM)

Roles are executed through a playbook. For one-off role runs, create a temporary playbook:

`tmp/run-role.yml`

```yaml
- name: Run one role on one VM
  hosts: servers
  become: true
  vars:
    ansible_user: "{{ user_devops }}"
    ansible_port: "{{ prod_ssh_port }}"
    ansible_ssh_private_key_file: "{{ ssh_private_key }}"
  roles:
    - role: install-node-exporter
```

Then run:

```bash
ansible-playbook tmp/run-role.yml \
  -i tmp/single-vm.inventory.yml \
  -e @config/ansible-standalone/base.yml \
  -e @config/ansible-standalone/vault.yml \
  --ask-vault-pass
```

## Quick troubleshooting

- `UNREACHABLE`: verify VM IP, SSH port, firewall rules, and username.
- `Permission denied (publickey)`: verify `ssh_private_key` value in `config/defaults/ansible/base.yml`.
- Vault variable errors (`vault_*` undefined): include both `-e @config/ansible-standalone/base.yml` and `-e @config/ansible-standalone/vault.yml`.
- Host key issues: this repo sets `ansible_ssh_common_args` in `base.yml`; ensure it is loaded.
