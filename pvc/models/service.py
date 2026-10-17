"""Service manifest schema (service.yml) and its resolved form."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field

from .. import paths
from .base import StrictModel
from .site import HostDefaults, NetworkOverrides


class HostSpec(HostDefaults):
    """One host as written in service.yml."""

    model_config = ConfigDict(extra="forbid")

    vm_id: int
    # Override the VM name / hostname. Defaults to <service>-<host>.
    name: str | None = None


class ServiceFile(StrictModel):
    # Service-wide network settings. Override site.yml `network` and `defaults`.
    network: NetworkOverrides = Field(default_factory=NetworkOverrides)
    defaults: HostDefaults = Field(default_factory=HostDefaults)
    hosts: dict[str, HostSpec] = Field(min_length=1)


@dataclass(frozen=True)
class ResolvedHost:
    key: str
    name: str
    node: str
    vm_id: int
    ip: str | None
    gateway: str | None
    cores: int
    sockets: int
    memory: int
    disk: int
    vlan: int
    bridge: str
    model: str
    nameservers: tuple[str, ...]
    mac: str | None
    image: str
    roles: tuple[str, ...]
    vars: dict[str, Any] = field(default_factory=dict)

    @property
    def address(self) -> str | None:
        """Static IPv4 address without the prefix length, or None for DHCP."""
        return self.ip.split("/")[0] if self.ip else None


@dataclass(frozen=True)
class ResolvedService:
    name: str
    hosts: dict[str, ResolvedHost]

    @property
    def directory(self) -> Path:
        return paths.service_dir(self.name)
