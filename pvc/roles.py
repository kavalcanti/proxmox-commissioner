"""Role groups a host can opt into. Must match the plays in ansible/site.yml."""

from __future__ import annotations

# `base` is applied to every host and does not need to be listed.
BASE_ROLE = "base"

KNOWN_ROLES: tuple[str, ...] = (
    "nfs",
    "docker",
    "nginx",
    "cloudflared",
    "node_exporter",
    "kubernetes",
    "compose",
)

# Roles that only make sense on top of another one. Resolved automatically.
ROLE_REQUIRES: dict[str, tuple[str, ...]] = {
    "compose": ("docker",),
}


def expand_roles(roles: list[str]) -> list[str]:
    """Drop `base`, add implied roles, and de-duplicate while keeping order."""
    ordered: list[str] = []

    def add(role: str) -> None:
        if role == BASE_ROLE or role in ordered:
            return
        for required in ROLE_REQUIRES.get(role, ()):
            add(required)
        ordered.append(role)

    for role in roles:
        add(role)
    return ordered
