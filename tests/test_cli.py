from __future__ import annotations

import yaml
from typer.testing import CliRunner

from pvc import paths
from pvc.cli import app

from .conftest import BLOG_RAW, write_service

runner = CliRunner()


def test_new_scaffolds_a_manifest_that_validates(project):
    result = runner.invoke(app, ["new", "blog", "--hosts", "db,app"])

    assert result.exit_code == 0, result.output
    directory = paths.service_dir("blog")
    assert (directory / "filetree").is_dir()
    manifest = yaml.safe_load((directory / "service.yml").read_text())
    assert list(manifest["hosts"]) == ["db", "app"]
    assert manifest["hosts"]["db"]["vm_id"] == 1000 and manifest["hosts"]["app"]["vm_id"] == 1001


def test_new_picks_vm_ids_after_existing_services(project):
    write_service(project, "other", BLOG_RAW)

    runner.invoke(app, ["new", "blog"])

    manifest = yaml.safe_load(paths.service_manifest("blog").read_text())
    assert manifest["hosts"]["app"]["vm_id"] == 1103


def test_new_refuses_to_overwrite_and_rejects_bad_names(project):
    assert runner.invoke(app, ["new", "blog"]).exit_code == 0

    again = runner.invoke(app, ["new", "blog"])
    assert again.exit_code != 0 and "already exists" in str(again.exception)

    bad = runner.invoke(app, ["new", "Bad_Name"])
    assert bad.exit_code != 0


def test_validate_reports_ok_and_failures(project):
    write_service(project, "blog", BLOG_RAW)
    good = runner.invoke(app, ["validate", "blog"])
    assert good.exit_code == 0
    assert "blog: ok" in good.output and "blog-db" in good.output

    broken = {**BLOG_RAW, "hosts": {"app": {"vm_id": 2000, "node": "pve1", "roles": ["ngnix"]}}}
    write_service(project, "broken", broken)
    bad = runner.invoke(app, ["validate"])
    assert bad.exit_code == 1


def test_status_for_a_service_that_was_never_deployed(project):
    write_service(project, "blog", BLOG_RAW)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "blog: not deployed" in result.output


def test_ssh_passes_extra_arguments_through_untouched(project, monkeypatch):
    import pvc.cli as cli

    write_service(project, "blog", BLOG_RAW)
    (project / "key").write_text("")
    monkeypatch.setattr(cli, "service_hosts_output", lambda name: {"app": {"ip": "172.20.30.55"}})
    monkeypatch.setattr(cli, "find_tool", lambda name: name)
    captured = {}
    monkeypatch.setattr(cli.os, "execvp", lambda program, argv: captured.update(argv=argv))

    result = runner.invoke(app, ["ssh", "blog", "app", "journalctl", "-u", "docker", "--no-pager"])

    assert result.exit_code == 0, result.output
    argv = captured["argv"]
    assert argv[argv.index("devops@172.20.30.55") + 1 :] == ["journalctl", "-u", "docker", "--no-pager"]
    assert argv[argv.index("-p") + 1] == "4224"


def test_init_creates_private_config_files_and_never_overwrites(project, monkeypatch):
    import pvc.cli as cli

    (project / "site.yml").unlink()
    monkeypatch.setattr(paths, "SITE_FILE", project / "site.yml")
    monkeypatch.setattr(paths, "SECRETS_FILE", project / "secrets.yml")
    monkeypatch.setattr(cli, "install_collections", lambda: None)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.output
    assert (project / "site.yml").read_text() == paths.SITE_EXAMPLE.read_text()
    assert (project / "secrets.yml").stat().st_mode & 0o777 == 0o600

    (project / "secrets.yml").write_text("proxmox_api_token: mine\n")
    runner.invoke(app, ["init"])
    assert (project / "secrets.yml").read_text() == "proxmox_api_token: mine\n"
