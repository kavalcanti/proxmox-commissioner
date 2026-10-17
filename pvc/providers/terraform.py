"""Terraform orchestration: shared roots, per-service state."""

from __future__ import annotations

import json
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .. import paths
from ..errors import PvcError
from ..models import ResolvedService, SiteConfig
from ..utils import find_tool, run


# ------------------------------------------------------------------------------
# Variable files
# ------------------------------------------------------------------------------
def _provider_vars(site: SiteConfig) -> dict[str, Any]:
    return {
        "proxmox_endpoint": site.proxmox.endpoint,
        "proxmox_insecure": site.proxmox.insecure,
        "proxmox_ssh_user": site.proxmox.ssh_user,
        "nodes": {name: node.address for name, node in site.nodes.items()},
    }


def build_site_tfvars(site: SiteConfig) -> dict[str, Any]:
    return {
        **_provider_vars(site),
        "images_datastore": site.storage.images,
        "images": {name: image.url for name, image in site.images.items()},
    }


def build_service_tfvars(site: SiteConfig, service: ResolvedService, ssh_public_key: str) -> dict[str, Any]:
    """Everything except the two secrets, which travel as TF_VAR_* environment variables."""
    hosts = {
        key: {
            "name": host.name,
            "node": host.node,
            "vm_id": host.vm_id,
            "ip": host.ip or "",
            "gateway": host.gateway or "",
            "cores": host.cores,
            "sockets": host.sockets,
            "memory": host.memory,
            "disk": host.disk,
            "vlan": host.vlan,
            "bridge": host.bridge,
            "model": host.model,
            "nameservers": list(host.nameservers),
            "mac": host.mac or "",
            "image_file_id": site.image_file_id(host.image),
            "roles": list(host.roles),
        }
        for key, host in service.hosts.items()
    }
    return {
        **_provider_vars(site),
        "service_name": service.name,
        "hosts": hosts,
        "storage": {
            "disk": site.storage.disk,
            "snippets": site.storage.snippets,
            "cloudinit": site.storage.cloudinit,
        },
        "vm_options": {
            "qemu_agent": site.vm.qemu_agent,
            "package_update": site.vm.package_update,
            "package_upgrade": site.vm.package_upgrade,
            "disk_interface": site.vm.disk_interface,
            "disk_discard": site.vm.disk_discard,
            "disk_format": site.vm.disk_format,
        },
        "devops_user": site.ssh.user,
        "ssh_public_key": ssh_public_key,
        "ssh_port": site.ssh.port,
    }


# ------------------------------------------------------------------------------
# Workspaces
# ------------------------------------------------------------------------------
class Workspace:
    """One Terraform root plus the scratch directory that holds its state."""

    def __init__(self, root: Path, state_dir: Path, secret_env: dict[str, str]):
        self.root = root
        self.state_dir = state_dir
        self.data_dir = state_dir / "terraform"
        self.state_file = state_dir / "terraform.tfstate"
        self.tfvars_file = state_dir / "terraform.tfvars.json"
        self.secret_env = secret_env

    @property
    def env(self) -> dict[str, str]:
        return {"TF_DATA_DIR": str(self.data_dir), **self.secret_env}

    def has_state(self) -> bool:
        return self.state_file.is_file()

    def write_tfvars(self, values: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.tfvars_file.write_text(json.dumps(values, indent=2) + "\n")
        os.chmod(self.tfvars_file, 0o600)

    def _terraform(self, *args: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
        return run(
            [find_tool("terraform"), f"-chdir={self.root}", *args],
            env=self.env,
            capture=capture,
            check=check,
        )

    def init(self) -> None:
        self._terraform(
            "init",
            "-input=false",
            "-reconfigure",
            f"-backend-config=path={self.state_file}",
        )

    def plan(self) -> None:
        self._terraform("plan", f"-var-file={self.tfvars_file}")

    def apply(self, auto_approve: bool = False) -> None:
        args = ["apply", f"-var-file={self.tfvars_file}"]
        if auto_approve:
            args.append("-auto-approve")
        self._terraform(*args)

    def destroy(self, auto_approve: bool = False) -> None:
        args = ["destroy", f"-var-file={self.tfvars_file}"]
        if auto_approve:
            args.append("-auto-approve")
        self._terraform(*args)

    def output(self, name: str) -> Any:
        if not self.has_state():
            raise PvcError(f"No Terraform state at {self.state_file}. Nothing has been created yet.")
        result = self._terraform("output", "-json", name, capture=True, check=False)
        if result.returncode != 0:
            raise PvcError(f"Could not read Terraform output '{name}': {result.stderr.strip()}")
        return json.loads(result.stdout)


def site_workspace(secret_env: dict[str, str] | None = None) -> Workspace:
    return Workspace(paths.TERRAFORM_SITE_DIR, paths.SITE_STATE_DIR, secret_env or {})


def service_workspace(service_name: str, secret_env: dict[str, str] | None = None) -> Workspace:
    return Workspace(paths.TERRAFORM_SERVICE_DIR, paths.service_state_dir(service_name), secret_env or {})


def service_hosts_output(service_name: str) -> dict[str, dict[str, Any]]:
    """host key => {name, vm_id, node, ip, mac}, read from the service's state."""
    hosts = service_workspace(service_name).output("hosts")
    if not isinstance(hosts, dict):
        raise PvcError(f"Service '{service_name}' has no hosts in its Terraform state.")
    return hosts


# ------------------------------------------------------------------------------
# SSH agent
# ------------------------------------------------------------------------------
@contextmanager
def proxmox_ssh_agent(site: SiteConfig) -> Iterator[None]:
    """Terraform reaches the nodes over SSH (snippet upload, image import) through an agent.

    With `proxmox.ssh_key` set, a throwaway agent holds that key for the duration of the
    run, so a passphrase is asked once and never persisted. Otherwise the agent already
    in the environment is used.
    """
    key = site.proxmox.ssh_key
    if not key:
        if not os.environ.get("SSH_AUTH_SOCK"):
            raise PvcError(
                "Terraform needs SSH access to the Proxmox nodes. Start an ssh-agent with the key "
                "loaded, or set proxmox.ssh_key in site.yml."
            )
        yield
        return

    key_path = Path(key).expanduser()
    if not key_path.is_file():
        raise PvcError(f"proxmox.ssh_key points to {key_path}, which does not exist.")

    started = subprocess.run([find_tool("ssh-agent"), "-s"], capture_output=True, text=True, check=True)
    environment = dict(re.findall(r"(\w+)=([^;]+);", started.stdout))
    previous = {name: os.environ.get(name) for name in ("SSH_AUTH_SOCK", "SSH_AGENT_PID")}
    os.environ.update({name: environment[name] for name in ("SSH_AUTH_SOCK", "SSH_AGENT_PID")})
    try:
        run([find_tool("ssh-add"), str(key_path)])
        yield
    finally:
        subprocess.run([find_tool("ssh-agent"), "-k"], capture_output=True, text=True)
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
