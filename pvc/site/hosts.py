"""Configuring the Proxmox nodes themselves (node_exporter, smartctl_exporter)."""

from __future__ import annotations

from typing import Callable

from .. import paths
from ..errors import PvcError
from ..manifest import load_site
from ..providers.ansible import run_playbook
from ..providers.secrets import Secrets, load_secrets
from ..utils import wait_for_ssh
from .inventory import BECOME_PASSWORD_SECRET, build_hosts_inventory, configurable_nodes, write_hosts_inventory

Notify = Callable[[str], None]


def _ignore(_: str) -> None:
    return None


def _become_secrets(root: bool) -> Secrets | None:
    """Secrets only matter for a non-root user whose sudo needs a password."""
    if root or not paths.SECRETS_FILE.is_file():
        return None
    secrets = load_secrets()
    return secrets if secrets.data.get(BECOME_PASSWORD_SECRET) else None


def configure_hosts(
    *,
    node: str | None = None,
    tags: list[str] | None = None,
    on_step: Notify = _ignore,
) -> None:
    """Install and configure the monitoring exporters on the Proxmox nodes."""
    site = load_site()
    nodes = configurable_nodes(site)
    if node is not None:
        if node not in site.nodes:
            raise PvcError(f"Unknown node '{node}' (nodes: {', '.join(site.nodes)}).")
        if node not in nodes:
            raise PvcError(f"Node '{node}' has `configure: false` in site.yml.")
    if not nodes:
        raise PvcError("Every node has `configure: false` in site.yml; nothing to configure.")

    secrets = _become_secrets(site.proxmox.ssh_user == "root")
    inventory = build_hosts_inventory(site, become_password=secrets is not None)
    inventory_file = write_hosts_inventory(inventory)

    targets = [node] if node else nodes
    on_step("Waiting for SSH")
    wait_for_ssh({name: site.nodes[name].address for name in targets}, site.proxmox.ssh_port, timeout=30)

    on_step("Configuring Proxmox nodes")
    run_playbook(
        inventory_file,
        secrets,
        limit=node,
        tags=tags,
        playbook=paths.ANSIBLE_HOSTS_PLAYBOOK,
    )
