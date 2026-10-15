"""The `pvc` command line."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

import typer

from . import paths
from .ansible import install_collections, run_playbook, wait_for_ssh
from .errors import ConfigError, PvcError
from .inventory import build_inventory, host_group, write_inventory
from .keys import ensure_keypair, private_key_path
from .manifest import (
    ResolvedService,
    list_services,
    load_service,
    next_free_vm_id,
    scaffold_manifest,
    NAME_PATTERN,
)
from .secrets import REQUIRED_KEYS, Secrets, load_secrets
from .site import SiteConfig, load_site
from .terraform import (
    Workspace,
    build_service_tfvars,
    build_site_tfvars,
    proxmox_ssh_agent,
    service_hosts_output,
    service_workspace,
    site_workspace,
)
from .tools import find_tool

app = typer.Typer(
    help="Create and configure services on Proxmox VE from a YAML manifest.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)
site_app = typer.Typer(help="Cluster-wide resources shared by all services.", no_args_is_help=True)
app.add_typer(site_app, name="site")

YES = typer.Option(False, "--yes", "-y", help="Skip Terraform's approval prompt.")


def _heading(text: str) -> None:
    typer.secho(f"\n=== {text} ===", bold=True)


def _load(service_name: str) -> tuple[SiteConfig, ResolvedService]:
    site = load_site()
    return site, load_service(site, service_name)


def _prepared_workspace(
    site: SiteConfig, service: ResolvedService, secrets: Secrets
) -> tuple[Workspace, Path]:
    private_key, public_key = ensure_keypair(site, service.name)
    workspace = service_workspace(service.name, secrets.terraform_env(service.name))
    workspace.write_tfvars(build_service_tfvars(site, service, public_key))
    return workspace, private_key


def _warn_if_images_missing() -> None:
    if not site_workspace().has_state():
        typer.secho(
            "Warning: no cloud images have been downloaded yet. If the VM disk import fails, "
            "run `pvc site apply` first.",
            fg=typer.colors.YELLOW,
            err=True,
        )


def _converge(
    site: SiteConfig,
    service: ResolvedService,
    secrets: Secrets,
    private_key: Path,
    *,
    host: Optional[str] = None,
    tags: Optional[list[str]] = None,
    post_deploy: bool = False,
) -> None:
    if host is not None and host not in service.hosts:
        raise PvcError(f"Service '{service.name}' has no host '{host}' (hosts: {', '.join(service.hosts)}).")

    deployed = service_hosts_output(service.name)
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

    _heading("Waiting for SSH")
    wait_for_ssh(addresses, site.ssh.port)

    inventory = build_inventory(site, service, deployed, private_key)
    inventory_file = write_inventory(inventory, service.name)

    _heading(f"Configuring '{service.name}'")
    run_playbook(
        inventory_file,
        secrets,
        limit=host_group(service.name, host) if host else None,
        tags=tags,
        post_deploy=post_deploy,
    )


def _split_tags(values: Optional[list[str]]) -> list[str]:
    return [tag.strip() for value in values or [] for tag in value.split(",") if tag.strip()]


# ------------------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------------------
@app.command()
def init() -> None:
    """Create site.yml and secrets.yml, install Ansible collections, check prerequisites."""
    paths.SERVICES_DIR.mkdir(exist_ok=True)

    for example, target in ((paths.SITE_EXAMPLE, paths.SITE_FILE), (paths.SECRETS_EXAMPLE, paths.SECRETS_FILE)):
        if target.exists():
            typer.echo(f"{target.name}: already exists, left alone")
            continue
        shutil.copyfile(example, target)
        os.chmod(target, 0o600)
        typer.echo(f"{target.name}: created from {example.name}")

    _heading("Prerequisites")
    missing = []
    for tool in ("terraform", "ansible-playbook", "ansible-vault", "ssh", "ssh-keygen", "openssl"):
        try:
            typer.echo(f"  ok       {tool}: {find_tool(tool)}")
        except PvcError as error:
            missing.append(tool)
            typer.secho(f"  missing  {tool}: {error}", fg=typer.colors.RED)

    if "ansible-playbook" not in missing:
        _heading("Ansible collections")
        install_collections()

    if missing:
        raise PvcError(f"Install the missing tools and rerun `pvc init`: {', '.join(missing)}")

    _heading("Next steps")
    typer.echo(
        "  1. Edit site.yml (Proxmox endpoint, nodes, storage, network)\n"
        "  2. Edit secrets.yml, then encrypt it:  uv run ansible-vault encrypt secrets.yml\n"
        "  3. pvc site apply          download the cloud image to every node\n"
        "  4. pvc new <service>       scaffold a manifest\n"
        "  5. pvc up <service>        create the VMs and configure them"
    )


@site_app.command("apply")
def site_apply(yes: bool = YES) -> None:
    """Download the cloud images listed in site.yml to every node."""
    site = load_site()
    secrets = load_secrets()
    secrets.require("proxmox_api_token")

    workspace = site_workspace(secrets.proxmox_env())
    workspace.write_tfvars(build_site_tfvars(site))
    with proxmox_ssh_agent(site):
        workspace.init()
        workspace.apply(auto_approve=yes)


# ------------------------------------------------------------------------------
# Services
# ------------------------------------------------------------------------------
@app.command()
def new(
    service: str = typer.Argument(..., help="Service name: lowercase letters, digits and '-'"),
    hosts: str = typer.Option("app", "--hosts", help="Comma-separated host names, e.g. db,app"),
) -> None:
    """Scaffold services/<service>/service.yml and a filetree."""
    if not NAME_PATTERN.match(service):
        raise PvcError(f"'{service}' must be lowercase letters, digits and '-' (max 40 characters).")
    host_keys = [key.strip() for key in hosts.split(",") if key.strip()]
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

    typer.echo(f"Created {manifest}")
    typer.echo(f"Edit it, then run: pvc up {service}")


@app.command()
def validate(
    service: Optional[str] = typer.Argument(None, help="Service name; all services when omitted"),
) -> None:
    """Check manifests against site.yml without touching Proxmox."""
    site = load_site()
    names = [service] if service else list_services()
    if not names:
        typer.echo("No services found.")
        return

    failed = False
    for name in names:
        try:
            resolved = load_service(site, name)
        except ConfigError as error:
            failed = True
            typer.secho(str(error), fg=typer.colors.RED, err=True)
            continue
        typer.secho(f"{name}: ok", fg=typer.colors.GREEN)
        for host in resolved.hosts.values():
            roles = ",".join(host.roles) or "-"
            typer.echo(
                f"  {host.key:<12} {host.name:<24} node={host.node} vm_id={host.vm_id} "
                f"ip={host.ip or 'dhcp'} roles={roles}"
            )
    if failed:
        raise typer.Exit(1)


@app.command()
def plan(service: str = typer.Argument(...)) -> None:
    """Validate the manifest and show what Terraform would change."""
    site, resolved = _load(service)
    secrets = load_secrets()
    workspace, _ = _prepared_workspace(site, resolved, secrets)
    with proxmox_ssh_agent(site):
        workspace.init()
        workspace.plan()


@app.command()
def up(
    service: str = typer.Argument(...),
    post_deploy: bool = typer.Option(False, "--post-deploy", help="Also run post-deploy.sh scripts."),
    yes: bool = YES,
) -> None:
    """Create or update the service's VMs, then configure them."""
    site, resolved = _load(service)
    secrets = load_secrets()
    workspace, private_key = _prepared_workspace(site, resolved, secrets)

    _warn_if_images_missing()
    _heading(f"Provisioning '{resolved.name}'")
    with proxmox_ssh_agent(site):
        workspace.init()
        workspace.apply(auto_approve=yes)

    _converge(site, resolved, secrets, private_key, post_deploy=post_deploy)
    _heading(f"Service '{resolved.name}' is up")
    _print_status(resolved.name)


@app.command()
def converge(
    service: str = typer.Argument(...),
    host: Optional[str] = typer.Option(None, "--host", help="Only this host of the service."),
    tags: Optional[list[str]] = typer.Option(None, "--tags", "-t", help="Only these tags (repeatable or comma-separated)."),
    post_deploy: bool = typer.Option(False, "--post-deploy", help="Also run post-deploy.sh scripts."),
) -> None:
    """Re-run configuration on existing VMs without touching Proxmox."""
    site, resolved = _load(service)
    secrets = load_secrets()
    secrets.require(*REQUIRED_KEYS)
    _converge(
        site,
        resolved,
        secrets,
        private_key_path(site, resolved.name),
        host=host,
        tags=_split_tags(tags),
        post_deploy=post_deploy,
    )


@app.command()
def down(service: str = typer.Argument(...), yes: bool = YES) -> None:
    """Destroy every VM of the service."""
    site, resolved = _load(service)
    secrets = load_secrets()
    workspace, _ = _prepared_workspace(site, resolved, secrets)
    if not workspace.has_state():
        raise PvcError(f"Service '{service}' has no Terraform state; nothing to destroy.")

    with proxmox_ssh_agent(site):
        workspace.init()
        workspace.destroy(auto_approve=yes)

    inventory = paths.service_state_dir(service) / "inventory.yml"
    inventory.unlink(missing_ok=True)
    typer.echo(f"Service '{service}' destroyed. Its manifest and filetree are untouched.")


@app.command("ssh", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def ssh_command(
    service: str = typer.Argument(...),
    host: str = typer.Argument(..., help="Host name from the manifest"),
    command: Optional[list[str]] = typer.Argument(None, help="Command to run instead of a shell"),
) -> None:
    """SSH into a host of the service with its key."""
    site, resolved = _load(service)
    if host not in resolved.hosts:
        raise PvcError(f"Service '{service}' has no host '{host}' (hosts: {', '.join(resolved.hosts)}).")
    deployed = service_hosts_output(service).get(host, {})
    address = deployed.get("ip") or resolved.hosts[host].address
    if not address:
        raise PvcError(f"No IP address known for '{host}'.")

    arguments = [
        "ssh",
        "-i", str(private_key_path(site, service)),
        "-p", str(site.ssh.port),
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{site.ssh.user}@{address}",
        *(command or []),
    ]
    os.execvp(find_tool("ssh"), arguments)


def _print_status(name: str) -> None:
    workspace = service_workspace(name)
    if not workspace.has_state():
        typer.echo(f"{name}: not deployed")
        return
    try:
        hosts = service_hosts_output(name)
    except PvcError as error:
        typer.secho(f"{name}: {error}", fg=typer.colors.YELLOW)
        return
    typer.secho(name, bold=True)
    for key, info in hosts.items():
        typer.echo(
            f"  {key:<12} {info.get('name', ''):<24} {info.get('ip') or '-':<16} "
            f"node={info.get('node', '-')} vm_id={info.get('vm_id', '-')}"
        )


@app.command()
def status(service: Optional[str] = typer.Argument(None)) -> None:
    """Show hosts, addresses and nodes from Terraform state."""
    names = [service] if service else list_services()
    if not names:
        typer.echo("No services found.")
        return
    for name in names:
        _print_status(name)


def main() -> None:
    try:
        app()
    except PvcError as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
