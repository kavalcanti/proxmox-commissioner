from __future__ import annotations

from pathlib import Path

from pvc.providers.ansible import build_playbook_command
from pvc.providers.secrets import Secrets

INVENTORY = Path("/tmp/inventory.yml")


def secrets(password_file=None):
    return Secrets(Path("/tmp/secrets.yml"), {}, password_file)


def option(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]


def test_plain_run_passes_inventory_and_secrets():
    command = build_playbook_command(INVENTORY, secrets())

    assert option(command, "-i") == str(INVENTORY)
    assert command[command.index("-i") + 2].endswith("ansible/site.yml")
    assert option(command, "-e") == "@/tmp/secrets.yml"
    assert "--tags" not in command and "--limit" not in command
    assert "--vault-password-file" not in command


def test_vault_password_file_is_forwarded():
    command = build_playbook_command(INVENTORY, secrets(Path("/tmp/pw")))

    assert option(command, "--vault-password-file") == "/tmp/pw"


def test_limit_and_tags():
    command = build_playbook_command(INVENTORY, secrets(), limit="svc_blog_app", tags=["nginx", "files"])

    assert option(command, "--limit") == "svc_blog_app"
    assert option(command, "--tags") == "nginx,files"


def test_post_deploy_alone_keeps_the_normal_plays():
    command = build_playbook_command(INVENTORY, secrets(), post_deploy=True)

    assert option(command, "--tags") == "all,post_deploy"


def test_post_deploy_with_tags_adds_to_them():
    command = build_playbook_command(INVENTORY, secrets(), tags=["compose"], post_deploy=True)

    assert option(command, "--tags") == "compose,post_deploy"


def test_custom_playbook_and_no_secrets():
    command = build_playbook_command(INVENTORY, None, playbook=Path("/tmp/pve-hosts.yml"))

    assert command[command.index("-i") + 2] == "/tmp/pve-hosts.yml"
    assert "-e" not in command and "--vault-password-file" not in command
