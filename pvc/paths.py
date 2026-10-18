"""Filesystem layout. Everything is relative to the commissioner checkout."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("PVC_HOME") or Path(__file__).resolve().parents[1])

SITE_FILE = ROOT / "site.yml"
SITE_EXAMPLE = ROOT / "site.example.yml"
SECRETS_FILE = ROOT / "secrets.yml"
SECRETS_EXAMPLE = ROOT / "secrets.example.yml"
SERVICES_DIR = ROOT / "services"

TERRAFORM_DIR = ROOT / "terraform"
TERRAFORM_SITE_DIR = TERRAFORM_DIR / "site"
TERRAFORM_SERVICE_DIR = TERRAFORM_DIR / "service"

ANSIBLE_DIR = ROOT / "ansible"
ANSIBLE_PLAYBOOK = ANSIBLE_DIR / "site.yml"
ANSIBLE_REQUIREMENTS = ANSIBLE_DIR / "requirements.yml"
# Configures the Proxmox nodes themselves, separate from the VM playbook on purpose.
ANSIBLE_HOSTS_PLAYBOOK = ANSIBLE_DIR / "pve-hosts.yml"

# Image downloads are shared by every service, so they keep their own state.
SITE_STATE_DIR = ROOT / ".pvc" / "site"
SITE_HOSTS_INVENTORY = SITE_STATE_DIR / "hosts-inventory.yml"


def service_dir(name: str) -> Path:
    return SERVICES_DIR / name


def service_manifest(name: str) -> Path:
    return service_dir(name) / "service.yml"


def service_state_dir(name: str) -> Path:
    """Per-service scratch area: tfstate, TF_DATA_DIR, tfvars, inventory. Gitignored."""
    return service_dir(name) / ".pvc"
