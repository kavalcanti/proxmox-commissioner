"""Discovering and loading services/<name>/service.yml."""

from __future__ import annotations

from pathlib import Path

from .. import paths
from ..errors import ConfigError, PvcError
from ..models import ResolvedService, SiteConfig
from ..utils import read_yaml
from .conflicts import conflicts_between
from .resolver import resolve_service


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

    service = resolve_service(site, name, read_yaml(manifest), str(manifest))

    siblings = []
    for other in list_services(services_dir):
        if other == name:
            continue
        try:
            siblings.append(
                resolve_service(site, other, read_yaml(services_dir / other / "service.yml"))
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
            raw = read_yaml(services_dir / name / "service.yml")
            hosts = raw.get("hosts", {}) if isinstance(raw, dict) else {}
            for spec in hosts.values():
                vm_id = spec.get("vm_id") if isinstance(spec, dict) else None
                if isinstance(vm_id, int):
                    highest = max(highest, vm_id)
        except (PvcError, AttributeError):
            continue
    return highest + 1
