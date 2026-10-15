"""Service manifests (services/<name>/service.yml): parsing, merging and validation."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ConfigDict, Field, ValidationError

from . import paths
from .errors import ConfigError, PvcError, format_validation_error
from .roles import KNOWN_ROLES, BASE_ROLE, expand_roles
from .site import HostDefaults, SiteConfig, StrictModel

NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$")
HOSTNAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
MIN_VM_ID = 100


class HostSpec(HostDefaults):
    """One host as written in service.yml."""

    model_config = ConfigDict(extra="forbid")

    vm_id: int
    # `dhcp`, omitted, or a CIDR such as 172.20.30.21/24.
    ip: str | None = None
    # Override the VM name / hostname. Defaults to <service>-<host>.
    name: str | None = None


class ServiceFile(StrictModel):
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


def _merge_layers(layers: list[dict[str, Any]]) -> dict[str, Any]:
    """Later layers win. `roles` are unioned and `vars` are merged key by key."""
    merged: dict[str, Any] = {"roles": [], "vars": {}}
    for layer in layers:
        for key, value in layer.items():
            if key == "roles":
                merged["roles"] = [*merged["roles"], *(r for r in value if r not in merged["roles"])]
            elif key == "vars":
                merged["vars"] = {**merged["vars"], **value}
            elif value is not None:
                merged[key] = value
    return merged


def _set_fields(model: HostDefaults) -> dict[str, Any]:
    return model.model_dump(exclude_unset=True, exclude_none=True)


def parse_service_file(raw: Any, source: str) -> ServiceFile:
    if not isinstance(raw, dict):
        raise ConfigError(source, ["file must be a YAML mapping"])
    try:
        return ServiceFile.model_validate(raw)
    except ValidationError as error:
        raise ConfigError(source, format_validation_error(error)) from error


def resolve_service(site: SiteConfig, name: str, raw: Any, source: str | None = None) -> ResolvedService:
    """Merge site, service and host settings and check everything that can be checked offline."""
    source = source or f"services/{name}/service.yml"
    problems: list[str] = []

    if not NAME_PATTERN.match(name):
        problems.append(
            f"service name '{name}' must be lowercase letters, digits and '-' (max 40 characters)"
        )

    service_file = parse_service_file(raw, source)
    site_layer = _set_fields(site.defaults)
    service_layer = _set_fields(service_file.defaults)

    hosts: dict[str, ResolvedHost] = {}
    for key, spec in service_file.hosts.items():
        where = f"hosts.{key}"
        if not NAME_PATTERN.match(key):
            problems.append(f"{where}: host key must be lowercase letters, digits and '-'")

        merged = _merge_layers([site_layer, service_layer, _set_fields(spec)])

        vm_name = spec.name or f"{name}-{key}"
        if not HOSTNAME_PATTERN.match(vm_name):
            problems.append(f"{where}: VM name '{vm_name}' is not a valid hostname")

        node = merged.get("node") or (next(iter(site.nodes)) if len(site.nodes) == 1 else None)
        if node is None:
            problems.append(f"{where}: no node set and site.yml defines several ({', '.join(site.nodes)})")
            node = ""
        elif node not in site.nodes:
            problems.append(f"{where}: node '{node}' is not in site.yml (known: {', '.join(site.nodes)})")

        image = merged.get("image") or site.default_image
        if image not in site.images:
            problems.append(f"{where}: image '{image}' is not in site.yml (known: {', '.join(site.images)})")

        roles = merged["roles"]
        unknown = [role for role in roles if role not in KNOWN_ROLES and role != BASE_ROLE]
        if unknown:
            problems.append(
                f"{where}: unknown role(s) {', '.join(repr(r) for r in unknown)} (known: {', '.join(KNOWN_ROLES)})"
            )

        ip = spec.ip
        if ip is not None and ip.lower() == "dhcp":
            ip = None
        gateway = merged.get("gateway") or site.network.gateway
        if ip is not None:
            try:
                interface = ipaddress.ip_interface(ip)
                if interface.version != 4 or "/" not in ip:
                    raise ValueError
            except ValueError:
                problems.append(f"{where}: ip '{spec.ip}' must be 'dhcp' or an IPv4 CIDR like 172.20.30.21/24")
            else:
                if not gateway:
                    problems.append(f"{where}: static ip needs a gateway (set network.gateway in site.yml or gateway)")
        if gateway:
            try:
                ipaddress.IPv4Address(gateway)
            except ValueError:
                problems.append(f"{where}: gateway '{gateway}' is not an IPv4 address")

        if spec.vm_id < MIN_VM_ID:
            problems.append(f"{where}: vm_id must be {MIN_VM_ID} or higher")

        hosts[key] = ResolvedHost(
            key=key,
            name=vm_name,
            node=node,
            vm_id=spec.vm_id,
            ip=ip,
            gateway=gateway if ip else None,
            cores=merged.get("cores", 1),
            sockets=merged.get("sockets", 1),
            memory=merged.get("memory", 1024),
            disk=merged.get("disk", 16),
            vlan=merged.get("vlan", 0),
            bridge=merged.get("bridge") or site.network.bridge,
            image=image,
            roles=tuple(expand_roles([r for r in roles if r in KNOWN_ROLES or r == BASE_ROLE])),
            vars=merged["vars"],
        )

    problems.extend(_duplicates(hosts.values(), "vm_id", lambda h: h.vm_id))
    problems.extend(_duplicates(hosts.values(), "VM name", lambda h: h.name))
    problems.extend(_duplicates([h for h in hosts.values() if h.address], "ip", lambda h: h.address))

    if problems:
        raise ConfigError(source, problems)
    return ResolvedService(name=name, hosts=hosts)


def _duplicates(hosts, label: str, attribute) -> list[str]:
    seen: dict[Any, str] = {}
    problems = []
    for host in hosts:
        value = attribute(host)
        if value in seen:
            problems.append(f"hosts.{seen[value]} and hosts.{host.key} share the same {label} ({value})")
        else:
            seen[value] = host.key
    return problems


def conflicts_between(service: ResolvedService, others: list[ResolvedService]) -> list[str]:
    """vm_id, VM name and static IP collisions with other services in the same cluster."""
    problems = []
    for other in others:
        if other.name == service.name:
            continue
        for mine in service.hosts.values():
            for theirs in other.hosts.values():
                if mine.vm_id == theirs.vm_id:
                    problems.append(
                        f"hosts.{mine.key}: vm_id {mine.vm_id} is already used by service "
                        f"'{other.name}' (host '{theirs.key}')"
                    )
                if mine.name == theirs.name:
                    problems.append(
                        f"hosts.{mine.key}: VM name '{mine.name}' is already used by service '{other.name}'"
                    )
                if mine.address and mine.address == theirs.address:
                    problems.append(
                        f"hosts.{mine.key}: ip {mine.address} is already used by service "
                        f"'{other.name}' (host '{theirs.key}')"
                    )
    return problems


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise PvcError(f"{path} is not valid YAML: {error}") from error


def list_services(services_dir: Path | None = None) -> list[str]:
    """Services that have a service.yml. Directories without one (legacy layouts) are ignored."""
    services_dir = services_dir or paths.SERVICES_DIR
    if not services_dir.is_dir():
        return []
    return sorted(p.name for p in services_dir.iterdir() if (p / "service.yml").is_file())


def load_service(site: SiteConfig, name: str, services_dir: Path | None = None) -> ResolvedService:
    """Load, resolve and cross-check one service against its siblings."""
    services_dir = services_dir or paths.SERVICES_DIR
    manifest = services_dir / name / "service.yml"
    if not manifest.is_file():
        raise PvcError(f"No manifest at {manifest}. Create one with `pvc new {name}`.")

    service = resolve_service(site, name, _read_yaml(manifest), str(manifest))

    siblings = []
    for other in list_services(services_dir):
        if other == name:
            continue
        try:
            siblings.append(
                resolve_service(site, other, _read_yaml(services_dir / other / "service.yml"))
            )
        except (ConfigError, PvcError):
            continue  # a broken sibling is reported when that service is used
    problems = conflicts_between(service, siblings)
    if problems:
        raise ConfigError(str(manifest), problems)
    return service


def next_free_vm_id(services_dir: Path | None = None, start: int = 1000) -> int:
    """One above the highest vm_id any manifest uses, or `start` when there are none."""
    services_dir = services_dir or paths.SERVICES_DIR
    highest = start - 1
    for name in list_services(services_dir):
        try:
            raw = _read_yaml(services_dir / name / "service.yml")
            hosts = raw.get("hosts", {}) if isinstance(raw, dict) else {}
            for spec in hosts.values():
                vm_id = spec.get("vm_id") if isinstance(spec, dict) else None
                if isinstance(vm_id, int):
                    highest = max(highest, vm_id)
        except (PvcError, AttributeError):
            continue
    return highest + 1


def scaffold_manifest(name: str, host_keys: list[str], first_vm_id: int) -> str:
    """Starter service.yml text. Kept as text so the comments survive."""
    lines = [
        f"# services/{name}/service.yml: the only file to edit for this service.",
        f"# Apply changes with `pvc up {name}`.",
        "defaults:",
        "  # node: pve1                # required when site.yml lists more than one node",
        "  cores: 1",
        "  memory: 1024",
        "  disk: 16",
        "  # vlan: 30",
        "",
        "hosts:",
    ]
    for offset, key in enumerate(host_keys):
        lines += [
            f"  {key}:",
            f"    vm_id: {first_vm_id + offset}",
            "    # ip: 172.20.30.21/24    # omit for DHCP",
            f"    roles: []                # any of: {', '.join(KNOWN_ROLES)}",
            "    vars: {}                 # Ansible variables for this host",
            "",
        ]
    return "\n".join(lines)
