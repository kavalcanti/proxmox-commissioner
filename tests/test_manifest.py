from __future__ import annotations

import copy

import pytest
import yaml

from pvc.errors import ConfigError
from pvc.manifest import (
    conflicts_between,
    load_service,
    next_free_vm_id,
    resolve_service,
    scaffold_manifest,
)

from .conftest import BLOG_RAW, write_service


def resolve(site, raw, name="blog"):
    return resolve_service(site, name, raw)


def problems(site, raw, name="blog") -> str:
    with pytest.raises(ConfigError) as error:
        resolve(site, raw, name)
    return "\n".join(error.value.problems)


# ------------------------------------------------------------------------------
# Merging
# ------------------------------------------------------------------------------
def test_precedence_is_site_then_service_defaults_then_host(site):
    service = resolve(site, BLOG_RAW)

    # site.defaults: vlan 30, memory 2048. service.defaults: cores 2, node pve1.
    db = service.hosts["db"]
    assert (db.vlan, db.memory, db.cores, db.node) == (30, 2048, 2, "pve1")

    # The host's own node wins over the service default.
    assert service.hosts["app"].node == "pve2"


def test_host_value_beats_service_default(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["db"]["cores"] = 4
    assert resolve(site, raw).hosts["db"].cores == 4
    assert resolve(site, raw).hosts["app"].cores == 2


def test_roles_union_across_layers_and_vars_merge_by_key(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["defaults"]["roles"] = ["node_exporter"]
    raw["defaults"]["vars"] = {"shared": 1, "overridden": "default"}
    raw["hosts"]["app"]["vars"]["overridden"] = "host"

    app = resolve(site, raw).hosts["app"]

    assert "node_exporter" in app.roles and "nginx" in app.roles
    assert app.vars["shared"] == 1
    assert app.vars["overridden"] == "host"
    assert app.vars["nginx_sites_enabled_configs"] == ["blog.conf"]


def test_implied_roles_are_added_and_base_is_dropped(site):
    raw = {"hosts": {"app": {"vm_id": 1200, "node": "pve1", "roles": ["compose", "base"]}}}

    assert resolve(site, raw).hosts["app"].roles == ("docker", "compose")


def test_single_node_site_needs_no_node_in_the_manifest():
    from pvc.manifest import parse_site

    one_node = parse_site({"proxmox": {"endpoint": "https://x:8006/"}, "nodes": {"only": {"address": "10.0.0.1"}}})
    service = resolve_service(one_node, "blog", {"hosts": {"app": {"vm_id": 1200}}})

    assert service.hosts["app"].node == "only"


def test_vm_name_defaults_to_service_dash_host_and_can_be_overridden(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["app"]["name"] = "blog"
    service = resolve(site, raw)

    assert service.hosts["db"].name == "blog-db"
    assert service.hosts["app"].name == "blog"


def test_network_precedence_is_site_service_network_service_defaults_host():
    from pvc.manifest import parse_site

    site = parse_site(
        {
            "proxmox": {"endpoint": "https://x:8006/"},
            "nodes": {"pve1": {"address": "10.0.0.1"}},
            "network": {"bridge": "vmbr0", "model": "virtio", "gateway": "10.0.0.1", "nameservers": ["10.0.0.1"]},
            "defaults": {"vlan": 10},
        }
    )
    raw = {
        "network": {"bridge": "vmbr1", "gateway": "172.20.30.1", "vlan": 30, "nameservers": ["172.20.30.2"]},
        "defaults": {"model": "e1000", "vlan": 40},
        "hosts": {
            "plain": {"vm_id": 1200},
            "custom": {
                "vm_id": 1201,
                "bridge": "vmbr2",
                "vlan": 0,
                "gateway": "172.20.40.1",
                "nameservers": [],
                "ip": "172.20.40.5/24",
            },
        },
    }

    hosts = resolve_service(site, "blog", raw).hosts

    plain = hosts["plain"]
    assert (plain.bridge, plain.model, plain.vlan) == ("vmbr1", "e1000", 40)  # service defaults beat service network
    assert plain.nameservers == ("172.20.30.2",)
    custom = hosts["custom"]
    assert (custom.bridge, custom.vlan, custom.nameservers, custom.gateway) == ("vmbr2", 0, (), "172.20.40.1")


def test_site_network_applies_when_the_service_sets_nothing(site):
    host = resolve(site, BLOG_RAW).hosts["db"]

    assert (host.bridge, host.model, host.nameservers, host.mac) == ("vmbr0", "virtio", (), None)


def test_service_defaults_can_carry_ip_and_mac(site):
    raw = {"defaults": {"node": "pve1", "ip": "172.20.30.10/32", "mac": "bc:24:11:a7:a1:c5"}, "hosts": {"a": {"vm_id": 1300}}}

    host = resolve(site, raw).hosts["a"]

    assert host.ip == "172.20.30.10/32" and host.gateway == "172.20.30.1"
    assert host.mac == "BC:24:11:A7:A1:C5"


def test_dhcp_and_static_addresses(site):
    service = resolve(site, BLOG_RAW)
    assert service.hosts["db"].ip == "172.20.30.21/24"
    assert service.hosts["db"].address == "172.20.30.21"
    assert service.hosts["db"].gateway == "172.20.30.1"
    assert service.hosts["app"].ip is None and service.hosts["app"].gateway is None

    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["db"]["ip"] = "dhcp"
    assert resolve(site, raw).hosts["db"].ip is None


# ------------------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------------------
def test_unknown_role_lists_the_valid_ones(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["app"]["roles"] = ["ngnix"]
    text = problems(site, raw)

    assert "ngnix" in text and "nginx" in text


def test_unknown_node_and_image_are_reported(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["app"]["node"] = "pve9"
    raw["hosts"]["app"]["image"] = "arch"
    text = problems(site, raw)

    assert "node 'pve9'" in text and "image 'arch'" in text


def test_duplicate_vm_id_and_ip_within_a_service(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["app"]["vm_id"] = 1101
    raw["hosts"]["app"]["ip"] = "172.20.30.21/24"
    text = problems(site, raw)

    assert "share the same vm_id" in text and "share the same ip" in text


def test_static_ip_must_be_cidr_and_needs_a_gateway(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["db"]["ip"] = "172.20.30.21"
    assert "IPv4 CIDR" in problems(site, raw)

    from pvc.manifest import parse_site

    no_gateway = parse_site(
        {"proxmox": {"endpoint": "https://x:8006/"}, "nodes": {"pve1": {"address": "10.0.0.1"}}}
    )
    raw = {"hosts": {"db": {"vm_id": 1300, "ip": "172.20.30.21/24"}}}
    with pytest.raises(ConfigError) as error:
        resolve_service(no_gateway, "blog", raw)
    assert "needs a gateway" in str(error.value)


def test_mac_and_nameserver_values_are_checked(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["db"]["mac"] = "not-a-mac"
    raw["hosts"]["app"]["mac"] = "01:00:5E:00:00:01"
    raw["network"] = {"nameservers": ["dns.lan"], "gateway": "gw"}
    text = problems(site, raw)

    assert "mac 'not-a-mac'" in text and "multicast" in text
    assert "nameserver 'dns.lan'" in text and "gateway 'gw'" in text


def test_duplicate_mac_within_a_service_is_caught(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["db"]["mac"] = "BC:24:11:00:00:01"
    raw["hosts"]["app"]["mac"] = "bc:24:11:00:00:01"

    assert "share the same mac" in problems(site, raw)


def test_unknown_network_key_is_rejected(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["network"] = {"brigde": "vmbr1"}

    assert "brigde" in problems(site, raw)


def test_multiple_nodes_require_an_explicit_node(site):
    raw = {"hosts": {"app": {"vm_id": 1200}}}
    assert "no node set" in problems(site, raw)


def test_typos_in_host_fields_are_rejected(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["app"]["memroy"] = 4096
    assert "memroy" in problems(site, raw)


def test_service_and_host_names_are_checked(site):
    assert "service name" in problems(site, BLOG_RAW, name="Blog_App")

    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["Bad_Host"] = {"vm_id": 1400}
    assert "host key" in problems(site, raw)


def test_every_problem_is_reported_at_once(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["app"]["roles"] = ["nope"]
    raw["hosts"]["app"]["node"] = "pve9"
    raw["hosts"]["db"]["vm_id"] = 5

    assert len([line for line in problems(site, raw).splitlines() if line]) >= 3


# ------------------------------------------------------------------------------
# Several services in one cluster
# ------------------------------------------------------------------------------
def test_vm_id_and_ip_clashes_between_services_are_caught(site, project):
    write_service(project, "other", {"hosts": {"x": {"vm_id": 1101, "node": "pve1", "ip": "172.20.30.21/24"}}})
    write_service(project, "blog", BLOG_RAW)

    with pytest.raises(ConfigError) as error:
        load_service(site, "blog")

    text = str(error.value)
    assert "vm_id 1101" in text and "172.20.30.21" in text and "'other'" in text


def test_mac_clash_between_services_is_caught(site, project):
    write_service(project, "other", {"hosts": {"x": {"vm_id": 1500, "node": "pve1", "mac": "BC:24:11:00:00:09"}}})
    raw = {"hosts": {"y": {"vm_id": 1501, "node": "pve1", "mac": "bc:24:11:00:00:09"}}}
    write_service(project, "blog", raw)

    with pytest.raises(ConfigError) as error:
        load_service(site, "blog")

    assert "mac BC:24:11:00:00:09" in str(error.value) and "'other'" in str(error.value)


def test_broken_sibling_does_not_block_a_good_service(site, project):
    (project / "services" / "broken").mkdir()
    (project / "services" / "broken" / "service.yml").write_text("hosts: [not, a, mapping]")
    (project / "services" / "legacy").mkdir()  # no service.yml at all
    write_service(project, "blog", BLOG_RAW)

    assert set(load_service(site, "blog").hosts) == {"db", "app"}


def test_conflicts_between_ignores_the_same_service(site):
    service = resolve(site, BLOG_RAW)
    assert conflicts_between(service, [service]) == []


# ------------------------------------------------------------------------------
# Scaffolding
# ------------------------------------------------------------------------------
def test_next_free_vm_id(project):
    assert next_free_vm_id() == 1000
    write_service(project, "blog", BLOG_RAW)
    assert next_free_vm_id() == 1103


def test_scaffold_is_valid_yaml_that_resolves(site):
    text = scaffold_manifest("blog", ["db", "app"], 1500)
    raw = yaml.safe_load(text)
    raw["defaults"]["node"] = "pve1"

    service = resolve_service(site, "blog", raw)

    assert [host.vm_id for host in service.hosts.values()] == [1500, 1501]
    assert "# ip:" in text


# ------------------------------------------------------------------------------
# PCI passthrough
# ------------------------------------------------------------------------------
@pytest.fixture
def pci_site():
    from pvc.manifest import parse_site

    from .conftest import SITE_RAW

    raw = copy.deepcopy(SITE_RAW)
    raw["pci_mappings"] = {
        "igpu": {"nodes": {"pve1": {"path": "0000:00:02.0", "id": "8086:4680"}}},
        "nic": {"nodes": {"pve1": {"path": "0000:03:00.0", "id": "8086:1533"}, "pve2": {"path": "0000:03:00.0", "id": "8086:1533"}}},
    }
    return parse_site(raw)


def pci_raw(*devices, machine=None, node="pve1"):
    host = {"vm_id": 1600, "node": node, "pci_devices": list(devices)}
    if machine:
        host["machine"] = machine
    return {"hosts": {"a": host}}


def test_pci_devices_resolve_with_defaults(pci_site):
    host = resolve(pci_site, pci_raw({"mapping": "igpu"})).hosts["a"]

    assert host.machine is None
    assert [(d.mapping, d.pcie, d.rombar, d.x_vga) for d in host.pci_devices] == [("igpu", False, True, False)]


def test_pci_devices_from_service_defaults_and_host_replaces(pci_site):
    raw = {
        "defaults": {"node": "pve1", "pci_devices": [{"mapping": "igpu"}]},
        "hosts": {"a": {"vm_id": 1600}, "b": {"vm_id": 1601, "pci_devices": [{"mapping": "nic"}]}},
    }
    # Both hosts end up with a device; the host-level list replaces the default one.
    hosts = resolve(pci_site, raw).hosts

    assert [d.mapping for d in hosts["a"].pci_devices] == ["igpu"]
    assert [d.mapping for d in hosts["b"].pci_devices] == ["nic"]


def test_pcie_with_q35(pci_site):
    host = resolve(pci_site, pci_raw({"mapping": "igpu", "pcie": True}, machine="q35")).hosts["a"]

    assert host.machine == "q35" and host.pci_devices[0].pcie


def test_unknown_pci_mapping_is_reported(pci_site):
    assert "mapping 'gpu'" in problems(pci_site, pci_raw({"mapping": "gpu"}))


def test_pci_mapping_must_cover_the_hosts_node(pci_site):
    text = problems(pci_site, pci_raw({"mapping": "igpu"}, node="pve2"))

    assert "no entry for node 'pve2'" in text and "pve1" in text


def test_pcie_needs_q35(pci_site):
    assert "machine: q35" in problems(pci_site, pci_raw({"mapping": "igpu", "pcie": True}))


def test_same_pci_mapping_twice_on_a_host_is_rejected(pci_site):
    assert "more than once" in problems(pci_site, pci_raw({"mapping": "igpu"}, {"mapping": "igpu"}))


def test_same_pci_mapping_on_two_hosts_of_a_service_is_rejected(pci_site):
    raw = {
        "defaults": {"node": "pve1", "pci_devices": [{"mapping": "igpu"}]},
        "hosts": {"a": {"vm_id": 1600}, "b": {"vm_id": 1601}},
    }

    assert "both use pci mapping 'igpu'" in problems(pci_site, raw)


def test_pci_mapping_clash_between_services_is_caught(pci_site, project):
    other = resolve_service(pci_site, "other", pci_raw({"mapping": "igpu"}))
    mine = resolve_service(pci_site, "blog", {"hosts": {"b": {"vm_id": 1700, "node": "pve1", "pci_devices": [{"mapping": "igpu"}]}}})

    text = "\n".join(conflicts_between(mine, [other]))

    assert "pci mapping 'igpu'" in text and "'other'" in text


def test_pci_mapping_definitions_are_validated():
    from pvc.manifest import parse_site

    from .conftest import SITE_RAW

    def site_with(mappings):
        return {**SITE_RAW, "pci_mappings": mappings}

    node = {"path": "0000:00:02.0", "id": "8086:4680"}
    for bad, expected in [
        ({"igpu": {"nodes": {"pve1": {**node, "path": "00:02.0"}}}}, "0000:00:02.0"),
        ({"igpu": {"nodes": {"pve1": {**node, "id": "8086"}}}}, "8086:4680"),
        ({"igpu": {"nodes": {"pve9": node}}}, "pve9"),
        ({"Bad_Name": {"nodes": {"pve1": node}}}, "Bad_Name"),
    ]:
        with pytest.raises(ConfigError) as error:
            parse_site(site_with(bad))
        assert expected in str(error.value)
