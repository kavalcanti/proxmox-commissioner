"""The `pvc` command line."""

from __future__ import annotations

import os
import shutil
from typing import Optional

import typer

from . import paths
from .errors import ConfigError, PvcError
from .manifest import list_services, load_service, load_site
from .ops import (
    ServiceStatus,
    apply_site,
    build_ssh_exec_args,
    converge_existing,
    create_service_scaffold,
    down_service,
    get_service_status,
    plan_service,
    up_service,
)
from .providers.ansible import install_collections
from .utils import find_tool

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


def _warn(text: str) -> None:
    typer.secho(f"Warning: {text}", fg=typer.colors.YELLOW, err=True)


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
    apply_site(yes=yes)


# ------------------------------------------------------------------------------
# Services
# ------------------------------------------------------------------------------
@app.command()
def new(
    service: str = typer.Argument(..., help="Service name: lowercase letters, digits and '-'"),
    hosts: str = typer.Option("app", "--hosts", help="Comma-separated host names, e.g. db,app"),
) -> None:
    """Scaffold services/<service>/service.yml and a filetree."""
    host_keys = [key.strip() for key in hosts.split(",") if key.strip()]
    manifest = create_service_scaffold(service, host_keys)
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
    plan_service(service)


@app.command()
def up(
    service: str = typer.Argument(...),
    post_deploy: bool = typer.Option(False, "--post-deploy", help="Also run post-deploy.sh scripts."),
    yes: bool = YES,
) -> None:
    """Create or update the service's VMs, then configure them."""
    resolved = up_service(
        service,
        post_deploy=post_deploy,
        yes=yes,
        on_step=_heading,
        on_warning=_warn,
    )
    _heading(f"Service '{resolved.name}' is up")
    _print_status(get_service_status(resolved.name))


@app.command()
def converge(
    service: str = typer.Argument(...),
    host: Optional[str] = typer.Option(None, "--host", help="Only this host of the service."),
    tags: Optional[list[str]] = typer.Option(None, "--tags", "-t", help="Only these tags (repeatable or comma-separated)."),
    post_deploy: bool = typer.Option(False, "--post-deploy", help="Also run post-deploy.sh scripts."),
) -> None:
    """Re-run configuration on existing VMs without touching Proxmox."""
    converge_existing(
        service,
        host=host,
        tags=_split_tags(tags),
        post_deploy=post_deploy,
        on_step=_heading,
    )


@app.command()
def down(service: str = typer.Argument(...), yes: bool = YES) -> None:
    """Destroy every VM of the service."""
    down_service(service, yes=yes)
    typer.echo(f"Service '{service}' destroyed. Its manifest and filetree are untouched.")


@app.command("ssh", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def ssh_command(
    service: str = typer.Argument(...),
    host: str = typer.Argument(..., help="Host name from the manifest"),
    command: Optional[list[str]] = typer.Argument(None, help="Command to run instead of a shell"),
) -> None:
    """SSH into a host of the service with its key."""
    arguments = build_ssh_exec_args(service, host, command)
    os.execvp(arguments[0], arguments)


def _print_status(status: ServiceStatus) -> None:
    if not status.deployed:
        typer.echo(f"{status.name}: not deployed")
        return
    if status.error:
        typer.secho(f"{status.name}: {status.error}", fg=typer.colors.YELLOW)
        return
    typer.secho(status.name, bold=True)
    for key, info in status.hosts.items():
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
        _print_status(get_service_status(name))


def main() -> None:
    try:
        app()
    except PvcError as error:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
