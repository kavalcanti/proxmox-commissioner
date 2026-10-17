from __future__ import annotations

import pytest

from pvc.errors import PvcError
from pvc.providers.secrets import load_secrets
from pvc.utils import hash_password

PLAIN = "proxmox_api_token: root@pam!pvc=abc\nvault_devops_password: hunter2\n"


def test_plain_file_loads_without_asking_for_a_vault_password(tmp_path):
    path = tmp_path / "secrets.yml"
    path.write_text(PLAIN)

    secrets = load_secrets(path)

    assert secrets.data["vault_devops_password"] == "hunter2"
    assert secrets.password_file is None
    assert secrets.ansible_args() == ["-e", f"@{path}"]


def test_terraform_env_has_token_and_hash_but_never_the_plain_password(tmp_path):
    path = tmp_path / "secrets.yml"
    path.write_text(PLAIN)

    env = load_secrets(path).terraform_env("blog")

    assert env["TF_VAR_proxmox_api_token"] == "root@pam!pvc=abc"
    assert env["TF_VAR_devops_password_hash"].startswith("$6$")
    assert "hunter2" not in "".join(env.values())


def test_hash_is_stable_per_service_so_terraform_sees_no_change():
    first = hash_password("hunter2", seed="blog")

    assert first == hash_password("hunter2", seed="blog")
    assert first != hash_password("hunter2", seed="other")
    assert first != hash_password("different", seed="blog")


def test_missing_keys_are_named(tmp_path):
    path = tmp_path / "secrets.yml"
    path.write_text("proxmox_api_token: x\n")

    with pytest.raises(PvcError, match="vault_devops_password"):
        load_secrets(path).terraform_env("blog")


def test_missing_file_points_at_init(tmp_path):
    with pytest.raises(PvcError, match="pvc init"):
        load_secrets(tmp_path / "nope.yml")


def test_encrypted_file_is_read_through_ansible_vault(tmp_path, monkeypatch):
    from pvc.utils import find_tool, run

    path = tmp_path / "secrets.yml"
    path.write_text(PLAIN)
    password_file = tmp_path / "pw"
    password_file.write_text("vaultpass\n")
    env = {"ANSIBLE_LOCAL_TEMP": str(tmp_path / "tmp"), "ANSIBLE_HOME": str(tmp_path / "home")}
    run(
        [find_tool("ansible-vault"), "encrypt", "--vault-password-file", str(password_file), str(path)],
        env=env,
        capture=True,
    )
    assert path.read_text().startswith("$ANSIBLE_VAULT")

    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("PVC_VAULT_PASSWORD_FILE", str(password_file))
    secrets = load_secrets(path)

    assert secrets.data["vault_devops_password"] == "hunter2"
    assert secrets.ansible_args()[-2:] == ["--vault-password-file", str(password_file)]
