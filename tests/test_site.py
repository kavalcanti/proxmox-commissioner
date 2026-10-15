from __future__ import annotations

import pytest

from pvc.errors import ConfigError
from pvc.site import parse_site


def test_minimal_site_gets_sensible_defaults():
    site = parse_site({"proxmox": {"endpoint": "https://x:8006/"}, "nodes": {"pve": {"address": "10.0.0.1"}}})

    assert site.ssh.port == 4224
    assert site.storage.images == "local"
    assert site.vm.disk_format == "raw"
    assert site.default_image == "debian-13"
    assert site.image_file_id("debian-13") == "local:iso/debian-13.img"


def test_unknown_keys_are_rejected_so_typos_surface():
    with pytest.raises(ConfigError) as error:
        parse_site(
            {"proxmox": {"endpoint": "https://x:8006/"}, "nodes": {"pve": {"address": "10.0.0.1"}}, "storege": {}}
        )
    assert "storege" in str(error.value)


def test_nodes_are_required():
    with pytest.raises(ConfigError):
        parse_site({"proxmox": {"endpoint": "https://x:8006/"}, "nodes": {}})


def test_site_ansible_vars_override_built_in_defaults():
    site = parse_site(
        {
            "proxmox": {"endpoint": "https://x:8006/"},
            "nodes": {"pve": {"address": "10.0.0.1"}},
            "ansible_vars": {"ansible_python_interpreter": "/usr/bin/python3.13", "custom": 1},
        }
    )
    merged = site.merged_ansible_vars()

    assert merged["ansible_python_interpreter"] == "/usr/bin/python3.13"
    assert merged["custom"] == 1
    assert "StrictHostKeyChecking=no" in merged["ansible_ssh_common_args"]


def test_example_site_file_is_valid():
    import yaml

    from pvc import paths

    parse_site(yaml.safe_load(paths.SITE_EXAMPLE.read_text()), "site.example.yml")
