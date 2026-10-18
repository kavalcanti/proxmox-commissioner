"""Merging site, service and host settings into a `ResolvedService`."""

from __future__ import annotations

import ipaddress
from typing import Any, Callable, Iterable

from pydantic import BaseModel, ValidationError

from ..errors import ConfigError, format_validation_error
from ..models import (
    HOSTNAME_PATTERN,
    MAC_PATTERN,
    MIN_VM_ID,
    NAME_PATTERN,
    PciDevice,
    ResolvedHost,
    ResolvedService,
    ServiceFile,
    SiteConfig,
)
from ..roles import BASE_ROLE, KNOWN_ROLES, expand_roles


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


def _set_fields(model: BaseModel) -> dict[str, Any]:
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
    # Least to most specific; later layers win.
    shared_layers = [
        site.network.model_dump(exclude_none=True),
        _set_fields(site.defaults),
        _set_fields(service_file.network),
        _set_fields(service_file.defaults),
    ]

    hosts: dict[str, ResolvedHost] = {}
    for key, spec in service_file.hosts.items():
        where = f"hosts.{key}"
        if not NAME_PATTERN.match(key):
            problems.append(f"{where}: host key must be lowercase letters, digits and '-'")

        merged = _merge_layers([*shared_layers, _set_fields(spec)])

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

        raw_ip = merged.get("ip")
        ip = None if raw_ip is not None and raw_ip.lower() == "dhcp" else raw_ip
        gateway = merged.get("gateway")
        if ip is not None:
            try:
                interface = ipaddress.ip_interface(ip)
                if interface.version != 4 or "/" not in ip:
                    raise ValueError
            except ValueError:
                problems.append(f"{where}: ip '{raw_ip}' must be 'dhcp' or an IPv4 CIDR like 172.20.30.21/24")
            else:
                if not gateway:
                    problems.append(
                        f"{where}: static ip needs a gateway (set network.gateway in site.yml or service.yml, or gateway)"
                    )
        if gateway:
            try:
                ipaddress.IPv4Address(gateway)
            except ValueError:
                problems.append(f"{where}: gateway '{gateway}' is not an IPv4 address")

        nameservers = tuple(merged.get("nameservers") or ())
        for nameserver in nameservers:
            try:
                ipaddress.ip_address(nameserver)
            except ValueError:
                problems.append(f"{where}: nameserver '{nameserver}' is not an IP address")

        mac = merged.get("mac")
        if mac is not None:
            if not MAC_PATTERN.match(mac):
                problems.append(f"{where}: mac '{mac}' must look like BC:24:11:A7:A1:C5")
            elif int(mac[:2], 16) & 1:
                problems.append(f"{where}: mac '{mac}' is a multicast address; the first byte must be even")
            else:
                mac = mac.upper()

        if spec.vm_id < MIN_VM_ID:
            problems.append(f"{where}: vm_id must be {MIN_VM_ID} or higher")

        machine = merged.get("machine")
        pci_devices = tuple(PciDevice.model_validate(d) for d in merged.get("pci_devices") or ())
        problems.extend(_pci_problems(site, where, node, machine, pci_devices))

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
            model=merged.get("model") or site.network.model,
            nameservers=nameservers,
            mac=mac,
            image=image,
            machine=machine,
            pci_devices=pci_devices,
            roles=tuple(expand_roles([r for r in roles if r in KNOWN_ROLES or r == BASE_ROLE])),
            vars=merged["vars"],
        )

    problems.extend(_duplicates(hosts.values(), "vm_id", lambda h: h.vm_id))
    problems.extend(_duplicates(hosts.values(), "VM name", lambda h: h.name))
    problems.extend(_duplicates([h for h in hosts.values() if h.address], "ip", lambda h: h.address))
    problems.extend(_duplicates([h for h in hosts.values() if h.mac], "mac", lambda h: h.mac))
    problems.extend(_shared_pci_mappings(hosts.values()))

    if problems:
        raise ConfigError(source, problems)
    return ResolvedService(name=name, hosts=hosts)


def _pci_problems(
    site: SiteConfig, where: str, node: str, machine: str | None, devices: tuple[PciDevice, ...]
) -> list[str]:
    problems = []
    seen: set[str] = set()
    for index, device in enumerate(devices):
        at = f"{where}.pci_devices[{index}]"
        mapping = site.pci_mappings.get(device.mapping)
        if mapping is None:
            known = ", ".join(site.pci_mappings) or "none defined"
            problems.append(f"{at}: mapping '{device.mapping}' is not in site.yml pci_mappings (known: {known})")
        elif node and node not in mapping.nodes:
            problems.append(
                f"{at}: mapping '{device.mapping}' has no entry for node '{node}' "
                f"(it covers: {', '.join(mapping.nodes)})"
            )
        if device.mapping in seen:
            problems.append(f"{at}: mapping '{device.mapping}' is listed more than once on this host")
        seen.add(device.mapping)
        if device.pcie and machine != "q35":
            problems.append(f"{at}: pcie: true needs `machine: q35` on this host")
    return problems


def _shared_pci_mappings(hosts: Iterable[ResolvedHost]) -> list[str]:
    """A passthrough device can only belong to one running VM."""
    owners: dict[str, str] = {}
    problems = []
    for host in hosts:
        for mapping in {device.mapping for device in host.pci_devices}:
            if mapping in owners:
                problems.append(
                    f"hosts.{owners[mapping]} and hosts.{host.key} both use pci mapping '{mapping}'"
                )
            else:
                owners[mapping] = host.key
    return problems


def _duplicates(
    hosts: Iterable[ResolvedHost], label: str, attribute: Callable[[ResolvedHost], Any]
) -> list[str]:
    seen: dict[Any, str] = {}
    problems = []
    for host in hosts:
        value = attribute(host)
        if value in seen:
            problems.append(f"hosts.{seen[value]} and hosts.{host.key} share the same {label} ({value})")
        else:
            seen[value] = host.key
    return problems
