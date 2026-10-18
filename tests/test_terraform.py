from __future__ import annotations

import json

from pvc.manifest import resolve_service
from pvc.models import PciMapping, PciMappingNode
from pvc.providers.terraform import Workspace, build_service_tfvars, build_site_tfvars

from .conftest import BLOG_RAW

PUBLIC_KEY = "ssh-ed25519 AAAA pvc-blog"


def test_service_tfvars_describe_every_host(site):
    service = resolve_service(site, "blog", BLOG_RAW)

    values = build_service_tfvars(site, service, PUBLIC_KEY)

    assert set(values["hosts"]) == {"db", "app"}
    db = values["hosts"]["db"]
    assert db["name"] == "blog-db"
    assert db["ip"] == "172.20.30.21/24" and db["gateway"] == "172.20.30.1"
    assert db["image_file_id"] == "local:iso/debian-13.img"
    assert db["roles"] == ["docker", "compose", "node_exporter"]
    assert db["vlan"] == 30 and db["memory"] == 2048 and db["cores"] == 2

    # The Terraform variable types are strings, so DHCP is an empty string rather than null.
    app = values["hosts"]["app"]
    assert app["ip"] == "" and app["gateway"] == ""
    assert app["node"] == "pve2"

    assert values["ssh_public_key"] == PUBLIC_KEY
    assert values["ssh_port"] == 4224
    assert values["nodes"] == {"pve1": "172.20.10.110", "pve2": "172.20.10.111"}


def test_service_tfvars_carry_network_settings_per_host(site):
    raw = {
        "network": {"bridge": "vmbr1", "nameservers": ["172.20.30.2"]},
        "defaults": {"node": "pve1"},
        "hosts": {
            "a": {"vm_id": 1300, "mac": "bc:24:11:00:00:01"},
            "b": {"vm_id": 1301, "bridge": "vmbr2", "model": "e1000", "nameservers": []},
        },
    }

    hosts = build_service_tfvars(site, resolve_service(site, "blog", raw), PUBLIC_KEY)["hosts"]

    assert (hosts["a"]["bridge"], hosts["a"]["model"], hosts["a"]["mac"]) == ("vmbr1", "virtio", "BC:24:11:00:00:01")
    assert hosts["a"]["nameservers"] == ["172.20.30.2"]
    assert (hosts["b"]["bridge"], hosts["b"]["model"], hosts["b"]["mac"]) == ("vmbr2", "e1000", "")
    assert hosts["b"]["nameservers"] == []


def test_service_tfvars_never_contain_secrets(site):
    service = resolve_service(site, "blog", BLOG_RAW)
    text = json.dumps(build_service_tfvars(site, service, PUBLIC_KEY))

    assert "api_token" not in text
    assert "password" not in text


def test_site_tfvars_list_nodes_and_images(site):
    values = build_site_tfvars(site)

    assert set(values["nodes"]) == {"pve1", "pve2"}
    assert values["images_datastore"] == "local"
    assert values["images"]["debian-13"].endswith(".qcow2")


def test_workspace_keeps_state_and_data_dir_per_service(tmp_path):
    workspace = Workspace(tmp_path / "root", tmp_path / "svc" / ".pvc", {"TF_VAR_x": "1"})

    assert workspace.state_file == tmp_path / "svc" / ".pvc" / "terraform.tfstate"
    assert workspace.env["TF_DATA_DIR"] == str(tmp_path / "svc" / ".pvc" / "terraform")
    assert workspace.env["TF_VAR_x"] == "1"
    assert not workspace.has_state()


def test_tfvars_file_is_private(tmp_path):
    workspace = Workspace(tmp_path / "root", tmp_path / ".pvc", {})
    workspace.write_tfvars({"a": 1})

    assert json.loads(workspace.tfvars_file.read_text()) == {"a": 1}
    assert workspace.tfvars_file.stat().st_mode & 0o777 == 0o600


def test_service_tfvars_carry_machine_and_pci_devices(site):
    raw = {
        "defaults": {"node": "pve1"},
        "hosts": {"a": {"vm_id": 1300}},
    }
    pci_site = site.model_copy(
        update={
            "pci_mappings": {
                "igpu": PciMapping(nodes={"pve1": PciMappingNode(path="0000:00:02.0", id="8086:4680")}),
            }
        }
    )
    raw["hosts"]["a"].update({"machine": "q35", "pci_devices": [{"mapping": "igpu", "pcie": True}]})

    plain = build_service_tfvars(site, resolve_service(site, "blog", {"defaults": {"node": "pve1"}, "hosts": {"a": {"vm_id": 1300}}}), PUBLIC_KEY)
    host = build_service_tfvars(pci_site, resolve_service(pci_site, "blog", raw), PUBLIC_KEY)["hosts"]["a"]

    assert plain["hosts"]["a"]["machine"] == "" and plain["hosts"]["a"]["pci_devices"] == []
    assert host["machine"] == "q35"
    assert host["pci_devices"] == [{"mapping": "igpu", "pcie": True, "rombar": True, "x_vga": False}]


def test_site_tfvars_carry_pci_mappings(site):
    pci_site = site.model_copy(
        update={
            "pci_mappings": {
                "igpu": PciMapping(
                    comment="Intel iGPU",
                    nodes={"pve1": PciMappingNode(path="0000:00:02.0", id="8086:4680", iommu_group=0)},
                ),
                "nic": PciMapping(nodes={"pve2": PciMappingNode(path="0000:03:00.0", id="8086:1533", subsystem_id="8086:0001")}),
            }
        }
    )

    mappings = build_site_tfvars(pci_site)["pci_mappings"]

    assert mappings["igpu"] == {
        "comment": "Intel iGPU",
        "nodes": {"pve1": {"path": "0000:00:02.0", "id": "8086:4680", "subsystem_id": "", "iommu_group": 0}},
    }
    # Unset optional values are sentinels the Terraform side turns back into null.
    nic = mappings["nic"]
    assert nic["comment"] == "" and nic["nodes"]["pve2"]["iommu_group"] == -1
    assert nic["nodes"]["pve2"]["subsystem_id"] == "8086:0001"
    assert build_site_tfvars(site)["pci_mappings"] == {}
