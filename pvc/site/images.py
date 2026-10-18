"""Cloud images, downloaded to every node through Terraform."""

from __future__ import annotations

from ..manifest import load_site
from ..providers.secrets import load_secrets
from ..providers.terraform import build_site_tfvars, proxmox_ssh_agent, site_workspace


def apply_images(*, yes: bool = False) -> None:
    """Download the cloud images listed in site.yml to every node."""
    site = load_site()
    secrets = load_secrets()
    secrets.require("proxmox_api_token")

    workspace = site_workspace(secrets.proxmox_env())
    workspace.write_tfvars(build_site_tfvars(site))
    with proxmox_ssh_agent(site):
        workspace.init()
        workspace.apply(auto_approve=yes)
