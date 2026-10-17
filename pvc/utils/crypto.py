"""Password hashing and per-service SSH keypairs."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

from ..errors import PvcError
from .process import find_tool, run


def hash_password(password: str, seed: str) -> str:
    """SHA-512 crypt hash with a salt derived from `seed`.

    A fixed salt per service keeps the hash stable between runs, so Terraform does not
    see a changed cloud-init file (and touch the VM) every time pvc runs.
    """
    openssl = find_tool("openssl")
    salt = hashlib.sha256(f"pvc:{seed}".encode()).hexdigest()[:16]
    result = subprocess.run(
        [openssl, "passwd", "-6", "-salt", salt, "-stdin"],
        input=password,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PvcError(f"openssl could not hash the devops password: {result.stderr.strip()}")
    return result.stdout.strip()


def private_key_path(key_dir: Path, service_name: str) -> Path:
    return key_dir / service_name


def ensure_keypair(key_dir: Path, service_name: str) -> tuple[Path, str]:
    """Create <key_dir>/<service> if missing. Returns (private key path, public key text)."""
    private = private_key_path(key_dir, service_name)
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
