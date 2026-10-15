"""Running Ansible and waiting for hosts."""

from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import paths
from .errors import PvcError
from .secrets import Secrets
from .tools import find_tool, run

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


def _wait_for_port(address: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((address, port), timeout=5):
                return True
        except OSError:
            time.sleep(3)
    return False


def wait_for_ssh(addresses: dict[str, str], port: int, timeout: float = 600) -> None:
    """Block until every host accepts TCP connections on the SSH port."""
    if not addresses:
        return
    with ThreadPoolExecutor(max_workers=len(addresses)) as pool:
        futures = {
            name: pool.submit(_wait_for_port, address, port, timeout) for name, address in addresses.items()
        }
    unreachable = [f"{name} ({addresses[name]})" for name, future in futures.items() if not future.result()]
    if unreachable:
        raise PvcError(
            f"Timed out after {int(timeout)}s waiting for SSH on port {port}: {', '.join(unreachable)}. "
            "Check the VM console; cloud-init may have failed."
        )
