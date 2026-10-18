"""Cluster-wide settings schema (site.yml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from .base import StrictModel

DEBIAN_13_URL = (
    "https://cloud.debian.org/images/cloud/trixie/latest/debian-13-generic-amd64.qcow2"
)


class ProxmoxConnection(StrictModel):
    endpoint: str
    ssh_user: str = "root"
    # SSH port on the nodes. Used by `pvc site configure` (Ansible).
    ssh_port: int = Field(default=22, ge=1, le=65535)
    # Optional. When set, the key is loaded into a throwaway ssh-agent for Terraform.
    # When unset, the ssh-agent already in the environment is used.
    ssh_key: str | None = None
    insecure: bool = True


class Node(StrictModel):
    address: str
    # Set to false to leave this node out of `pvc site configure`.
    configure: bool = True


class Storage(StrictModel):
    disk: str = "local-lvm"
    snippets: str = "local"
    cloudinit: str = "local-lvm"
    # Must have the `iso` content type enabled. Cloud images are downloaded here.
    images: str = "local"


class Network(StrictModel):
    bridge: str = "vmbr0"
    model: str = "virtio"
    gateway: str | None = None
    nameservers: list[str] = Field(default_factory=list)


class NetworkOverrides(StrictModel):
    """`network:` block of a service.yml. Anything left unset falls back to site.yml."""

    bridge: str | None = None
    model: str | None = None
    gateway: str | None = None
    nameservers: list[str] | None = None
    vlan: int | None = Field(default=None, ge=0, le=4094)


class Image(StrictModel):
    url: str


class Ssh(StrictModel):
    port: int = Field(default=4224, ge=1, le=65535)
    user: str = "devops"
    key_dir: str = "~/.ssh/pvc"

    @property
    def key_dir_path(self) -> Path:
        return Path(self.key_dir).expanduser()


class VmOptions(StrictModel):
    qemu_agent: bool = True
    package_update: bool = True
    package_upgrade: bool = False
    disk_interface: str = "scsi0"
    disk_discard: str = "on"
    # raw works on every datastore, including LVM-thin. Use qcow2 only on file storage.
    disk_format: str = "raw"


class HostDefaults(StrictModel):
    """Settings a host can inherit. Everything is optional so precedence can be resolved."""

    node: str | None = None
    cores: int | None = Field(default=None, ge=1)
    sockets: int | None = Field(default=None, ge=1)
    memory: int | None = Field(default=None, ge=512)
    disk: int | None = Field(default=None, ge=8)
    vlan: int | None = Field(default=None, ge=0, le=4094)
    bridge: str | None = None
    model: str | None = None
    gateway: str | None = None
    nameservers: list[str] | None = None
    # `dhcp`, omitted, or a CIDR such as 172.20.30.21/24.
    ip: str | None = None
    # Fixed MAC address, e.g. BC:24:11:A7:A1:C5. Proxmox generates one when unset.
    mac: str | None = None
    image: str | None = None
    roles: list[str] = Field(default_factory=list)
    vars: dict[str, Any] = Field(default_factory=dict)


# Ansible variables every inventory gets. Overridable from site.yml `ansible_vars`.
DEFAULT_ANSIBLE_VARS: dict[str, Any] = {
    "ansible_python_interpreter": "/usr/bin/python3",
    "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
}


class ExporterOptions(StrictModel):
    enabled: bool = True
    port: int = Field(default=9100, ge=1, le=65535)


class SmartctlExporterOptions(ExporterOptions):
    port: int = Field(default=9633, ge=1, le=65535)
    # Empty = let smartctl_exporter discover the disks itself.
    devices: list[str] = Field(default_factory=list)


class HostConfig(StrictModel):
    """What `pvc site configure` installs on the Proxmox nodes themselves.

    Each exporter listens on `<node address>:<port>`. pvc does not touch the PVE firewall.
    """

    node_exporter: ExporterOptions = Field(default_factory=ExporterOptions)
    smartctl_exporter: SmartctlExporterOptions = Field(default_factory=SmartctlExporterOptions)
    # Extra Ansible variables for every node.
    vars: dict[str, Any] = Field(default_factory=dict)


class SiteConfig(StrictModel):
    proxmox: ProxmoxConnection
    nodes: dict[str, Node] = Field(min_length=1)
    storage: Storage = Field(default_factory=Storage)
    network: Network = Field(default_factory=Network)
    images: dict[str, Image] = Field(default_factory=lambda: {"debian-13": Image(url=DEBIAN_13_URL)})
    ssh: Ssh = Field(default_factory=Ssh)
    vm: VmOptions = Field(default_factory=VmOptions)
    defaults: HostDefaults = Field(default_factory=HostDefaults)
    ansible_vars: dict[str, Any] = Field(default_factory=dict)
    host_config: HostConfig = Field(default_factory=HostConfig)

    @field_validator("images")
    @classmethod
    def _image_names(cls, value: dict[str, Image]) -> dict[str, Image]:
        for name in value:
            if not name.replace("-", "").replace("_", "").replace(".", "").isalnum():
                raise ValueError(f"image name '{name}' may only contain letters, digits, '-', '_' and '.'")
        return value

    @property
    def default_image(self) -> str:
        return self.defaults.image or next(iter(self.images))

    def image_file_id(self, image: str) -> str:
        """Proxmox volume id of the downloaded image: `<datastore>:iso/<image>.img`."""
        return f"{self.storage.images}:iso/{image}.img"

    def merged_ansible_vars(self) -> dict[str, Any]:
        return {**DEFAULT_ANSIBLE_VARS, **self.ansible_vars}
