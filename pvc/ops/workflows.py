"""Use cases behind the CLI commands.

Nothing here prints or parses arguments. Progress and warnings are reported through the
`on_step` / `on_warning` callbacks so the CLI (or any other front end) decides how to show them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .. import paths
from ..errors import PvcError
from ..manifest import load_service, load_site, next_free_vm_id, scaffold_manifest
from ..models import NAME_PATTERN, ResolvedService, SiteConfig
from ..providers.ansible import run_playbook
from ..providers.inventory import build_inventory, host_group, write_inventory
from ..providers.secrets import REQUIRED_KEYS, Secrets, load_secrets
from ..providers.terraform import (
    Workspace,
    build_service_tfvars,
    proxmox_ssh_agent,
    service_hosts_output,
    service_workspace,
    site_workspace,
)
from ..utils import ensure_keypair, find_tool, private_key_path, wait_for_ssh

Notify = Callable[[str], None]


def _ignore(_: str) -> None:
    return None


# ------------------------------------------------------------------------------
# Loading
# ------------------------------------------------------------------------------
def load_site_and_service(service_name: str) -> tuple[SiteConfig, ResolvedService]:
    site = load_site()
    return site, load_service(site, service_name)


def prepare_service_workspace(
    site: SiteConfig, service: ResolvedService, secrets: Secrets
) -> tuple[Workspace, Path]:
    """Ensure the service keypair exists and write the Terraform variables. Returns (workspace, private key)."""
    private_key, public_key = ensure_keypair(site.ssh.key_dir_path, service.name)
    workspace = service_workspace(service.name, secrets.terraform_env(service.name))
    workspace.write_tfvars(build_service_tfvars(site, service, public_key))
    return workspace, private_key


# ------------------------------------------------------------------------------
# Services
# ------------------------------------------------------------------------------
def create_service_scaffold(service: str, host_keys: list[str]) -> Path:
    """Create services/<service>/service.yml and an empty filetree. Returns the manifest path."""
    if not NAME_PATTERN.match(service):
        raise PvcError(f"'{service}' must be lowercase letters, digits and '-' (max 40 characters).")
    if not host_keys:
        raise PvcError("--hosts needs at least one host name.")
    if len(set(host_keys)) != len(host_keys):
        raise PvcError("--hosts contains a duplicate name.")
    bad = [key for key in host_keys if not NAME_PATTERN.match(key)]
    if bad:
        raise PvcError(f"Invalid host name(s): {', '.join(bad)}. Use lowercase letters, digits and '-'.")

    directory = paths.service_dir(service)
    manifest = paths.service_manifest(service)
    if manifest.exists():
        raise PvcError(f"{manifest} already exists.")

    directory.mkdir(parents=True, exist_ok=True)
    (directory / "filetree").mkdir(exist_ok=True)
    (directory / "filetree" / ".gitkeep").touch()
    manifest.write_text(scaffold_manifest(service, host_keys, next_free_vm_id()))
    return manifest


def plan_service(service_name: str) -> None:
    """Show what Terraform would change for the service."""
    site, service = load_site_and_service(service_name)
    secrets = load_secrets()
    workspace, _ = prepare_service_workspace(site, service, secrets)
    with proxmox_ssh_agent(site):
        workspace.init()
        workspace.plan()


def up_service(
    service_name: str,
    *,
    post_deploy: bool = False,
    yes: bool = False,
    on_step: Notify = _ignore,
    on_warning: Notify = _ignore,
) -> ResolvedService:
    """Create or update the service's VMs, then configure them."""
    site, service = load_site_and_service(service_name)
    secrets = load_secrets()
    workspace, private_key = prepare_service_workspace(site, service, secrets)

    if not site_workspace().has_state():
        on_warning(
            "no cloud images have been downloaded yet. If the VM disk import fails, "
            "run `pvc site apply` first."
        )
    on_step(f"Provisioning '{service.name}'")
    with proxmox_ssh_agent(site):
        workspace.init()
        workspace.apply(auto_approve=yes)

    converge_service(site, service, secrets, private_key, post_deploy=post_deploy, on_step=on_step)
    return service


def resolve_deployed_addresses(
    service: ResolvedService, deployed: dict[str, dict[str, Any]]
) -> dict[str, str]:
    """VM name => address, preferring what the guest agent reported over the manifest."""
    addresses = {
        service.hosts[key].name: info.get("ip") or service.hosts[key].address or ""
        for key, info in deployed.items()
        if key in service.hosts
    }
    missing = [name for name, address in addresses.items() if not address]
    if missing:
        raise PvcError(
            f"No IP address yet for: {', '.join(missing)}. The guest agent has not reported one; "
            "rerun in a moment or use a static ip."
        )
    return addresses


def converge_service(
    site: SiteConfig,
    service: ResolvedService,
    secrets: Secrets,
    private_key: Path,
    *,
    host: str | None = None,
    tags: list[str] | None = None,
    post_deploy: bool = False,
    on_step: Notify = _ignore,
) -> None:
    """Wait for SSH, regenerate the inventory and run the playbook."""
    if host is not None and host not in service.hosts:
        raise PvcError(f"Service '{service.name}' has no host '{host}' (hosts: {', '.join(service.hosts)}).")

    deployed = service_hosts_output(service.name)
    addresses = resolve_deployed_addresses(service, deployed)

    on_step("Waiting for SSH")
    wait_for_ssh(addresses, site.ssh.port)

    inventory = build_inventory(site, service, deployed, private_key)
    inventory_file = write_inventory(inventory, service.name)

    on_step(f"Configuring '{service.name}'")
    run_playbook(
        inventory_file,
        secrets,
        limit=host_group(service.name, host) if host else None,
        tags=tags,
        post_deploy=post_deploy,
    )


def converge_existing(
    service_name: str,
    *,
    host: str | None = None,
    tags: list[str] | None = None,
    post_deploy: bool = False,
    on_step: Notify = _ignore,
) -> None:
    """Re-run configuration on existing VMs without touching Proxmox."""
    site, service = load_site_and_service(service_name)
    secrets = load_secrets()
    secrets.require(*REQUIRED_KEYS)
    converge_service(
        site,
        service,
        secrets,
        private_key_path(site.ssh.key_dir_path, service.name),
        host=host,
        tags=tags,
        post_deploy=post_deploy,
        on_step=on_step,
    )


def down_service(service_name: str, *, yes: bool = False) -> None:
    """Destroy every VM of the service. Its manifest and filetree are untouched."""
    site, service = load_site_and_service(service_name)
    secrets = load_secrets()
    workspace, _ = prepare_service_workspace(site, service, secrets)
    if not workspace.has_state():
        raise PvcError(f"Service '{service_name}' has no Terraform state; nothing to destroy.")

    with proxmox_ssh_agent(site):
        workspace.init()
        workspace.destroy(auto_approve=yes)

    (paths.service_state_dir(service_name) / "inventory.yml").unlink(missing_ok=True)


def build_ssh_exec_args(service_name: str, host: str, command: list[str] | None = None) -> list[str]:
    """Full `ssh` argv for a host of the service, program path first."""
    site, service = load_site_and_service(service_name)
    if host not in service.hosts:
        raise PvcError(f"Service '{service_name}' has no host '{host}' (hosts: {', '.join(service.hosts)}).")
    deployed = service_hosts_output(service_name).get(host, {})
    address = deployed.get("ip") or service.hosts[host].address
    if not address:
        raise PvcError(f"No IP address known for '{host}'.")

    return [
        find_tool("ssh"),
        "-i", str(private_key_path(site.ssh.key_dir_path, service_name)),
        "-p", str(site.ssh.port),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{site.ssh.user}@{address}",
        *(command or []),
    ]


# ------------------------------------------------------------------------------
# Status
# ------------------------------------------------------------------------------
@dataclass(frozen=True)
class ServiceStatus:
    name: str
    deployed: bool
    hosts: dict[str, dict[str, Any]]
    # Set when the service has state but its outputs could not be read.
    error: str | None = None


def get_service_status(service_name: str) -> ServiceStatus:
    """Hosts, addresses and nodes from the service's Terraform state."""
    if not service_workspace(service_name).has_state():
        return ServiceStatus(service_name, deployed=False, hosts={})
    try:
        hosts = service_hosts_output(service_name)
    except PvcError as error:
        return ServiceStatus(service_name, deployed=True, hosts={}, error=str(error))
    return ServiceStatus(service_name, deployed=True, hosts=hosts)
