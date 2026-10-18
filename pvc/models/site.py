"""Cluster-wide settings schema (site.yml)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .base import NAME_PATTERN, StrictModel

PCI_PATH_PATTERN = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$")
PCI_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{4}$")

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


class PciMappingNode(StrictModel):
    """Where one mapped PCI device sits on one node (see `lspci -Dnn`)."""

    # Full PCI address with domain, e.g. 0000:00:02.0.
    path: str
    # vendor:device, e.g. 8086:4680.
    id: str
    subsystem_id: str | None = None
    iommu_group: int | None = Field(default=None, ge=0)

    @field_validator("path")
    @classmethod
    def _path(cls, value: str) -> str:
        if not PCI_PATH_PATTERN.match(value):
            raise ValueError(f"path '{value}' must look like 0000:00:02.0 (see `lspci -D`)")
        return value.lower()

    @field_validator("id", "subsystem_id")
    @classmethod
    def _ids(cls, value: str | None) -> str | None:
        if value is not None and not PCI_ID_PATTERN.match(value):
            raise ValueError(f"'{value}' must look like 8086:4680 (see `lspci -nn`)")
        return value.lower() if value else value


class PciMapping(StrictModel):
    """A datacenter PCI resource mapping: one logical device, one entry per node that has it."""

    comment: str | None = None
    nodes: dict[str, PciMappingNode] = Field(min_length=1)


class PciDevice(StrictModel):
    """A mapped device attached to a host (one `hostpciN` slot)."""

    mapping: str
    # PCIe instead of legacy PCI. Needs `machine: q35`.
    pcie: bool = False
    rombar: bool = True
    x_vga: bool = False


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
    # QEMU machine type. Unset keeps the Proxmox default (i440fx). PCIe passthrough needs q35.
    machine: Literal["q35", "pc"] | None = None
    # Mapped PCI devices (names from site.yml `pci_mappings`). The most specific layer that
    # sets this replaces the earlier ones.
    pci_devices: list[PciDevice] | None = None
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
    # Datacenter PCI resource mappings, created by `pvc site apply`. Hosts attach them by name.
    pci_mappings: dict[str, PciMapping] = Field(default_factory=dict)
    ansible_vars: dict[str, Any] = Field(default_factory=dict)
    host_config: HostConfig = Field(default_factory=HostConfig)

    @field_validator("pci_mappings")
    @classmethod
    def _mapping_names(cls, value: dict[str, PciMapping]) -> dict[str, PciMapping]:
        for name in value:
            if not NAME_PATTERN.match(name):
                raise ValueError(f"pci mapping name '{name}' must be lowercase letters, digits and '-'")
        return value

    @field_validator("images")
    @classmethod
    def _image_names(cls, value: dict[str, Image]) -> dict[str, Image]:
        for name in value:
            if not name.replace("-", "").replace("_", "").replace(".", "").isalnum():
                raise ValueError(f"image name '{name}' may only contain letters, digits, '-', '_' and '.'")
        return value

    @model_validator(mode="after")
    def _mapping_nodes_exist(self) -> "SiteConfig":
        for name, mapping in self.pci_mappings.items():
            unknown = [node for node in mapping.nodes if node not in self.nodes]
            if unknown:
                raise ValueError(
                    f"pci_mappings.{name}: node(s) {', '.join(repr(n) for n in unknown)} "
                    f"are not in `nodes` (known: {', '.join(self.nodes)})"
                )
        return self

    @property
    def default_image(self) -> str:
        return self.defaults.image or next(iter(self.images))

    def image_file_id(self, image: str) -> str:
        """Proxmox volume id of the downloaded image: `<datastore>:iso/<image>.img`."""
        return f"{self.storage.images}:iso/{image}.img"

    def merged_ansible_vars(self) -> dict[str, Any]:
        return {**DEFAULT_ANSIBLE_VARS, **self.ansible_vars}
