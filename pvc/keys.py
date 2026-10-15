"""Per-service SSH keypair used by Ansible (and `pvc ssh`)."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import PvcError
from .site import SiteConfig
from .tools import find_tool, run


def private_key_path(site: SiteConfig, service_name: str) -> Path:
    return site.ssh.key_dir_path / service_name


def ensure_keypair(site: SiteConfig, service_name: str) -> tuple[Path, str]:
    """Create ~/.ssh/pvc/<service> if missing. Returns (private key path, public key text)."""
    private = private_key_path(site, service_name)
    public = private.with_suffix(private.suffix + ".pub")

    if not private.is_file():
        private.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(private.parent, 0o700)
        run(
            [
                find_tool("ssh-keygen"),
                "-q",
                "-t", "ed25519",
                "-N", "",
                "-C", f"pvc-{service_name}",
                "-f", str(private),
            ],
            capture=True,
        )

    if not public.is_file():
        # Private key survived but the public half did not: derive it.
        result = run([find_tool("ssh-keygen"), "-y", "-f", str(private)], capture=True)
        public.write_text(result.stdout)

    key = public.read_text().strip()
    if not key:
        raise PvcError(f"{public} is empty. Delete {private} and {public} to generate a new keypair.")
    return private, key
