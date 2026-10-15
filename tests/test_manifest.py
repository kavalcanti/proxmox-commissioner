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
    from pvc.site import parse_site

    one_node = parse_site({"proxmox": {"endpoint": "https://x:8006/"}, "nodes": {"only": {"address": "10.0.0.1"}}})
    service = resolve_service(one_node, "blog", {"hosts": {"app": {"vm_id": 1200}}})

    assert service.hosts["app"].node == "only"


def test_vm_name_defaults_to_service_dash_host_and_can_be_overridden(site):
    raw = copy.deepcopy(BLOG_RAW)
    raw["hosts"]["app"]["name"] = "blog"
    service = resolve(site, raw)

    assert service.hosts["db"].name == "blog-db"
    assert service.hosts["app"].name == "blog"


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

    from pvc.site import parse_site

    no_gateway = parse_site(
        {"proxmox": {"endpoint": "https://x:8006/"}, "nodes": {"pve1": {"address": "10.0.0.1"}}}
    )
    raw = {"hosts": {"db": {"vm_id": 1300, "ip": "172.20.30.21/24"}}}
    with pytest.raises(ConfigError) as error:
        resolve_service(no_gateway, "blog", raw)
    assert "needs a gateway" in str(error.value)


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
