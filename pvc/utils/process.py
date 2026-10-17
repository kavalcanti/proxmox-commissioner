"""Locating and running external programs."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from ..errors import PvcError

INSTALL_HINTS = {
    "terraform": "Install Terraform: https://developer.hashicorp.com/terraform/install",
    "openssl": "Install OpenSSL from your package manager.",
    "ssh": "Install an OpenSSH client from your package manager.",
    "ssh-keygen": "Install an OpenSSH client from your package manager.",
    "ssh-agent": "Install an OpenSSH client from your package manager.",
    "ssh-add": "Install an OpenSSH client from your package manager.",
}


def find_tool(name: str) -> str:
    """Prefer the project virtualenv (ansible-core ships there), then PATH."""
    beside_python = Path(sys.executable).parent / name
    if beside_python.is_file() and os.access(beside_python, os.X_OK):
        return str(beside_python)
    found = shutil.which(name)
    if found:
        return found
    hint = INSTALL_HINTS.get(name, "Run `uv sync` to install the project dependencies.")
    raise PvcError(f"`{name}` was not found. {hint}")


def run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture: bool = False,
    input_text: str | None = None,
) -> subprocess.CompletedProcess:
    """Run a command with the current terminal attached unless `capture` is set."""
    merged = {**os.environ, **(env or {})}
    result = subprocess.run(
        list(command),
        cwd=cwd,
        env=merged,
        text=True,
        capture_output=capture,
        input=input_text,
    )
    if check and result.returncode != 0:
        detail = f"\n{result.stderr.strip()}" if capture and result.stderr else ""
        raise PvcError(f"`{' '.join(command[:2])}` exited with status {result.returncode}.{detail}")
    return result
