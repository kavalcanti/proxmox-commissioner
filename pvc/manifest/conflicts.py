"""Collisions between services that share one cluster."""

from __future__ import annotations

from ..models import ResolvedService


def conflicts_between(service: ResolvedService, others: list[ResolvedService]) -> list[str]:
    """vm_id, VM name, MAC and static IP collisions with other services in the same cluster."""
    problems = []
    for other in others:
        if other.name == service.name:
            continue
        for mine in service.hosts.values():
            for theirs in other.hosts.values():
                if mine.vm_id == theirs.vm_id:
                    problems.append(
                        f"hosts.{mine.key}: vm_id {mine.vm_id} is already used by service "
                        f"'{other.name}' (host '{theirs.key}')"
                    )
                if mine.name == theirs.name:
                    problems.append(
                        f"hosts.{mine.key}: VM name '{mine.name}' is already used by service '{other.name}'"
                    )
                if mine.mac and mine.mac == theirs.mac:
                    problems.append(
                        f"hosts.{mine.key}: mac {mine.mac} is already used by service "
                        f"'{other.name}' (host '{theirs.key}')"
                    )
                if mine.address and mine.address == theirs.address:
                    problems.append(
                        f"hosts.{mine.key}: ip {mine.address} is already used by service "
                        f"'{other.name}' (host '{theirs.key}')"
                    )
    return problems
