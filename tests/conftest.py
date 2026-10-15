from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pvc import paths
from pvc.site import SiteConfig, parse_site

SITE_RAW = {
    "proxmox": {"endpoint": "https://pve1.lan:8006/"},
    "nodes": {"pve1": {"address": "172.20.10.110"}, "pve2": {"address": "172.20.10.111"}},
    "network": {"gateway": "172.20.30.1"},
    "defaults": {"vlan": 30, "memory": 2048},
    "ansible_vars": {"node_exporter_ufw_from": "172.20.30.0/24"},
}

BLOG_RAW = {
    "defaults": {"node": "pve1", "cores": 2},
    "hosts": {
        "db": {
            "vm_id": 1101,
            "ip": "172.20.30.21/24",
            "roles": ["compose", "node_exporter"],
            "vars": {"compose_stack": "postgres"},
        },
        "app": {
            "vm_id": 1102,
            "node": "pve2",
            "roles": ["nginx", "docker"],
            "vars": {"nginx_sites_enabled_configs": ["blog.conf"]},
        },
    },
}


@pytest.fixture
def site() -> SiteConfig:
    return parse_site(SITE_RAW)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway project root with site.yml, so commands never touch the real checkout."""
    services = tmp_path / "services"
    services.mkdir()
    (tmp_path / "site.yml").write_text(yaml.safe_dump(SITE_RAW))
    monkeypatch.setattr(paths, "SERVICES_DIR", services)
    monkeypatch.setattr(paths, "SITE_FILE", tmp_path / "site.yml")
    return tmp_path


def write_service(project: Path, name: str, raw: dict) -> Path:
    directory = project / "services" / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "service.yml").write_text(yaml.safe_dump(raw))
    return directory
