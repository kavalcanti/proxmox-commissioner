"""Running Ansible and waiting for hosts."""

from __future__ import annotations

from pathlib import Path

from .. import paths
from ..utils import find_tool, run
from .secrets import Secrets

COLLECTIONS_MARKER = paths.ANSIBLE_DIR / "collections" / "ansible_collections" / "community" / "general"


def install_collections() -> None:
    run(
        [
            find_tool("ansible-galaxy"),
            "collection",
            "install",
            "-r",
            str(paths.ANSIBLE_REQUIREMENTS),
            "-p",
            str(paths.ANSIBLE_DIR / "collections"),
        ]
    )


def ensure_collections() -> None:
    if not COLLECTIONS_MARKER.is_dir():
        print("Installing Ansible collections...")
        install_collections()


def build_playbook_command(
    inventory: Path,
    secrets: Secrets,
    limit: str | None = None,
    tags: list[str] | None = None,
    post_deploy: bool = False,
    extra_args: list[str] | None = None,
) -> list[str]:
    command = [
        find_tool("ansible-playbook"),
        "-i",
        str(inventory),
        str(paths.ANSIBLE_PLAYBOOK),
        *secrets.ansible_args(),
    ]
    if limit:
        command += ["--limit", limit]

    selected = list(tags or [])
    if post_deploy:
        # `never`-tagged plays only run when named explicitly; `all` keeps the rest.
        selected = selected + ["post_deploy"] if selected else ["all", "post_deploy"]
    if selected:
        command += ["--tags", ",".join(selected)]

    return command + list(extra_args or [])


def run_playbook(
    inventory: Path,
    secrets: Secrets,
    limit: str | None = None,
    tags: list[str] | None = None,
    post_deploy: bool = False,
) -> None:
    ensure_collections()
    command = build_playbook_command(inventory, secrets, limit, tags, post_deploy)
    # Run from ansible/ so ansible.cfg (roles path, pipelining, ControlPersist) applies.
    run(command, cwd=paths.ANSIBLE_DIR)
