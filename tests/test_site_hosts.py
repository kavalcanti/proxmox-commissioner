from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from pvc import paths
from pvc.cli import app
from pvc.errors import PvcError
from pvc.manifest import parse_site
from pvc.site import build_hosts_inventory, configure_hosts, write_hosts_inventory
from pvc.site import hosts as hosts_module

from .conftest import SITE_RAW


def make_site(**overrides):
    return parse_site({**SITE_RAW, **overrides})


def test_inventory_has_one_host_per_node_bound_to_its_address():
    inventory = build_hosts_inventory(make_site())["all"]

    assert list(inventory["children"]["pve_hosts"]["hosts"]) == ["pve1", "pve2"]
    pve2 = inventory["hosts"]["pve2"]
    assert pve2["ansible_host"] == "172.20.10.111"
    assert pve2["node_exporter_listen_address"] == "172.20.10.111:9100"
    assert pve2["smartctl_exporter_listen_address"] == "172.20.10.111:9633"
    assert pve2["smartctl_exporter_devices"] == []
    assert pve2["node_exporter_open_ufw"] is False
    assert inventory["vars"]["ansible_user"] == "root"
    assert inventory["vars"]["ansible_port"] == 22


def test_node_with_configure_false_is_left_out():
    site = make_site(nodes={"pve1": {"address": "10.0.0.1"}, "pve2": {"address": "10.0.0.2", "configure": False}})

    inventory = build_hosts_inventory(site)["all"]

    assert list(inventory["hosts"]) == ["pve1"]


def test_key_file_only_when_ssh_key_is_set():
    plain = build_hosts_inventory(make_site())["all"]["vars"]
    keyed = build_hosts_inventory(
        make_site(proxmox={"endpoint": "https://x:8006/", "ssh_key": "/keys/pve"})
    )["all"]["vars"]

    assert "ansible_ssh_private_key_file" not in plain
    assert keyed["ansible_ssh_private_key_file"] == "/keys/pve"


def test_become_only_for_non_root_users():
    root = build_hosts_inventory(make_site())["all"]["vars"]
    admin_site = make_site(proxmox={"endpoint": "https://x:8006/", "ssh_user": "admin", "ssh_port": 2222})
    admin = build_hosts_inventory(admin_site)["all"]["vars"]
    with_password = build_hosts_inventory(admin_site, become_password=True)["all"]["vars"]

    assert "ansible_become" not in root
    assert admin["ansible_become"] is True and admin["ansible_port"] == 2222
    assert "ansible_become_password" not in admin
    assert with_password["ansible_become_password"] == "{{ proxmox_become_password }}"


def test_vm_ansible_vars_do_not_leak_but_host_config_vars_do():
    site = make_site(host_config={"vars": {"custom": 1}, "smartctl_exporter": {"devices": ["/dev/sda"], "port": 9700}})

    inventory = build_hosts_inventory(site)["all"]

    assert "node_exporter_ufw_from" not in inventory["vars"]
    assert inventory["vars"]["custom"] == 1
    assert inventory["hosts"]["pve1"]["smartctl_exporter_devices"] == ["/dev/sda"]
    assert inventory["hosts"]["pve1"]["smartctl_exporter_listen_address"].endswith(":9700")


def test_write_hosts_inventory_round_trips(tmp_path: Path):
    inventory = build_hosts_inventory(make_site())

    path = write_hosts_inventory(inventory, tmp_path / "state" / "inv.yml")

    assert yaml.safe_load(path.read_text()) == inventory


@pytest.fixture
def captured(project, monkeypatch):
    calls = {}
    monkeypatch.setattr(paths, "SITE_HOSTS_INVENTORY", project / ".pvc" / "site" / "hosts-inventory.yml")
    monkeypatch.setattr(paths, "SECRETS_FILE", project / "secrets.yml")
    monkeypatch.setattr(hosts_module, "wait_for_ssh", lambda addresses, port, timeout=0: calls.update(wait=(addresses, port)))
    monkeypatch.setattr(hosts_module, "run_playbook", lambda inventory, secrets, **kw: calls.update(inventory=inventory, secrets=secrets, **kw))
    return calls


def test_configure_runs_the_hosts_playbook_without_secrets_for_root(captured):
    configure_hosts(tags=["monitoring"])

    assert captured["secrets"] is None
    assert captured["playbook"] == paths.ANSIBLE_HOSTS_PLAYBOOK
    assert captured["limit"] is None and captured["tags"] == ["monitoring"]
    assert set(captured["wait"][0]) == {"pve1", "pve2"} and captured["wait"][1] == 22
    assert Path(captured["inventory"]).is_file()


def test_configure_node_limits_the_run(captured):
    configure_hosts(node="pve2")

    assert captured["limit"] == "pve2"
    assert set(captured["wait"][0]) == {"pve2"}


def test_configure_rejects_unknown_and_excluded_nodes(project, captured):
    with pytest.raises(PvcError, match="Unknown node"):
        configure_hosts(node="pve9")

    raw = {**SITE_RAW, "nodes": {"pve1": {"address": "10.0.0.1", "configure": False}}}
    (project / "site.yml").write_text(yaml.safe_dump(raw))
    with pytest.raises(PvcError, match="configure: false"):
        configure_hosts(node="pve1")
    with pytest.raises(PvcError, match="nothing to configure"):
        configure_hosts()


def test_site_configure_command_is_wired_up(captured):
    result = CliRunner().invoke(app, ["site", "configure", "--node", "pve1", "--tags", "node_exporter,monitoring"])

    assert result.exit_code == 0, result.output
    assert captured["limit"] == "pve1"
    assert captured["tags"] == ["node_exporter", "monitoring"]
