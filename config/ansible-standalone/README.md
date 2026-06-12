# ansible-standalone config

This directory contains variables and inventory dedicated to standalone Ansible runs against one VM IP.

Used by:
- `scripts/run_ansible_standalone.sh`

Files:
- `inventory.yml`: inventory template. Keep `__VM_IP__` placeholder; the script replaces it at runtime.
- `base.yml`: non-sensitive defaults for standalone runs.
- `vault.yml`: encrypted secrets file (gitignored by repo rules).
- `vault.yml.example`: template to initialize `vault.yml`.

Quick setup:

```bash
cp config/ansible-standalone/vault.yml.example config/ansible-standalone/vault.yml
ansible-vault encrypt config/ansible-standalone/vault.yml
```
