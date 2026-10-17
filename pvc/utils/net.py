"""Waiting for hosts on the network."""

from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor

from ..errors import PvcError


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
