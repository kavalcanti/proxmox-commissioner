"""Starter service.yml text for `pvc new`."""

from __future__ import annotations

from ..roles import KNOWN_ROLES


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
