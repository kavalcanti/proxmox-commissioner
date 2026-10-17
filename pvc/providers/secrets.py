"""Secrets: one ansible-vault file shared by Terraform and Ansible."""

from __future__ import annotations

import atexit
import getpass
import os
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .. import paths
from ..errors import PvcError
from ..utils import find_tool, hash_password, parse_yaml_mapping

REQUIRED_KEYS = ("proxmox_api_token", "vault_devops_password")
VAULT_HEADER = "$ANSIBLE_VAULT"


class Secrets:
    def __init__(self, path: Path, data: dict[str, Any], password_file: Path | None):
        self.path = path
        self.data = data
        self.password_file = password_file

    def require(self, *keys: str) -> None:
        missing = [key for key in keys if not self.data.get(key)]
        if missing:
            raise PvcError(
                f"{self.path} is missing: {', '.join(missing)}. See secrets.example.yml."
            )

    def terraform_env(self, service_name: str) -> dict[str, str]:
        """Secrets handed to Terraform as TF_VAR_* so they never touch a tfvars file."""
        self.require(*REQUIRED_KEYS)
        return {
            "TF_VAR_proxmox_api_token": str(self.data["proxmox_api_token"]),
            "TF_VAR_devops_password_hash": hash_password(
                str(self.data["vault_devops_password"]), seed=service_name
            ),
        }

    def proxmox_env(self) -> dict[str, str]:
        """Only the API token, for roots that create no VMs."""
        self.require("proxmox_api_token")
        return {"TF_VAR_proxmox_api_token": str(self.data["proxmox_api_token"])}

    def ansible_args(self) -> list[str]:
        args = ["-e", f"@{self.path}"]
        if self.password_file:
            args += ["--vault-password-file", str(self.password_file)]
        return args


def _is_encrypted(path: Path) -> bool:
    with path.open() as handle:
        return handle.readline().startswith(VAULT_HEADER)


def _vault_password_file() -> Path:
    configured = os.environ.get("PVC_VAULT_PASSWORD_FILE")
    if configured:
        password_file = Path(configured).expanduser()
        if not password_file.is_file():
            raise PvcError(f"PVC_VAULT_PASSWORD_FILE points to {password_file}, which does not exist.")
        return password_file

    password = getpass.getpass("Vault password: ")
    descriptor, name = tempfile.mkstemp(prefix="pvc-vault-")
    os.chmod(name, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(password + "\n")
    atexit.register(lambda: Path(name).unlink(missing_ok=True))
    return Path(name)


def load_secrets(path: Path | None = None) -> Secrets:
    path = path or paths.SECRETS_FILE
    if not path.is_file():
        raise PvcError(f"{path} not found. Run `pvc init`, then fill it in and encrypt it.")

    if not _is_encrypted(path):
        return Secrets(path, parse_yaml_mapping(path.read_text(), path), password_file=None)

    password_file = _vault_password_file()
    result = subprocess.run(
        [find_tool("ansible-vault"), "view", "--vault-password-file", str(password_file), str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PvcError(f"Could not decrypt {path}: {result.stderr.strip() or 'wrong vault password?'}")
    return Secrets(path, parse_yaml_mapping(result.stdout, path), password_file=password_file)
