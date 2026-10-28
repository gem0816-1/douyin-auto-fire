import json
import os
from pathlib import Path
import subprocess

import pytest

from scripts import deploy


@pytest.fixture
def project(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(deploy, "PROJECT_ROOT", tmp_path)
    (tmp_path / "requirements.txt").write_text("playwright>=1.54,<2\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("HEADLESS=false\n", encoding="utf-8")
    (tmp_path / "config.example.json").write_text('{"friends":["示例"]}', encoding="utf-8")
    return tmp_path


@pytest.fixture
def commands(project, monkeypatch):
    recorded = []

    def fake_execute(command, *, capture=False):
        recorded.append(command)
        if "venv" in command:
            (project / ".venv").mkdir()
        return subprocess.CompletedProcess(command, 0, stdout="{}")

    monkeypatch.setattr(deploy, "execute", fake_execute)
    monkeypatch.setattr(deploy, "environment_health", lambda python: {"python": "3.11", "packages": {"playwright": "1.54"}})
    return recorded


def test_config_preserves_existing_even_empty_files(project):
    (project / ".env").write_bytes(b"TOKEN=local-secret\n")
    (project / "config.json").touch()
    deploy.initialize_config()
    assert (project / ".env").read_bytes() == b"TOKEN=local-secret\n"
    assert (project / "config.json").read_bytes() == b""


def test_cached_deploy_skips_packages_but_repairs_browser_cache(project, commands):
    deploy.prepare("uv")
    assert any("venv" in cmd for cmd in commands)
    assert any("pip" in cmd for cmd in commands)
    commands.clear()
    deploy.prepare("uv")
    assert not any("venv" in cmd or "pip" in cmd for cmd in commands)
    assert any(cmd[1:] == ["-m", "playwright", "install", "chromium"] for cmd in commands)
    assert any(deploy.BROWSER_CHECK in cmd for cmd in commands)


@pytest.mark.parametrize("change", ["requirements", "environment", "refresh", "corrupt-marker"])
def test_cache_invalidates_on_changes(project, commands, monkeypatch, change):
    deploy.prepare("uv")
    if change == "requirements":
        (project / "requirements.txt").write_text("playwright>=1.55,<2\n", encoding="utf-8")
    elif change == "environment":
        monkeypatch.setattr(deploy, "environment_health", lambda python: {"python": "3.12", "packages": {}})
    elif change == "corrupt-marker":
        (project / ".venv" / ".deploy-state.json").write_text("broken", encoding="utf-8")
    commands.clear()
    deploy.prepare("uv", refresh=change == "refresh")
    install = next(cmd for cmd in commands if "pip" in cmd)
    assert ("--upgrade" in install) == (change == "refresh")


def test_failed_browser_install_is_retried_and_does_not_mark_success(project, commands, monkeypatch):
    original = deploy.execute

    def fail_browser(command, *, capture=False):
        if command[1:] == ["-m", "playwright", "install", "chromium"]:
            raise subprocess.CalledProcessError(1, command)
        return original(command, capture=capture)

    monkeypatch.setattr(deploy, "execute", fail_browser)
    assert deploy.main(["--uv", "uv"]) == 1
    assert not (project / ".venv" / ".deploy-state.json").exists()
    assert not (project / "config.json").exists()
    monkeypatch.setattr(deploy, "execute", original)
    assert deploy.main(["--uv", "uv"]) == 0
    assert json.loads((project / "config.json").read_text(encoding="utf-8"))["friends"] == ["示例"]


def test_unusable_existing_venv_is_preserved(project, monkeypatch):
    (project / ".venv").mkdir()
    sentinel = project / ".venv" / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    def missing_python(*args, **kwargs):
        raise FileNotFoundError("missing python")

    monkeypatch.setattr(deploy, "execute", missing_python)
    assert deploy.main(["--uv", "uv"]) == 1
    assert sentinel.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("action,expected", [("login", "login.py"), ("dry-run", "run.py"), ("run", "run.py")])
def test_actions_and_application_exit_codes(project, commands, monkeypatch, action, expected):
    monkeypatch.setenv("HEADLESS", "false")
    original = deploy.execute

    def fail_application(command, *, capture=False):
        if len(command) > 1 and command[1].endswith(expected):
            commands.append(command)
            raise subprocess.CalledProcessError(2, command)
        return original(command, capture=capture)

    monkeypatch.setattr(deploy, "execute", fail_application)
    assert deploy.main([action, "--uv", "uv"]) == 2
    application = commands[-1]
    assert Path(application[1]).name == expected
    assert ("--dry-run" in application) == (action == "dry-run")
    assert os.environ["HEADLESS"] == "true"


def test_default_setup_never_runs_login_or_sender(project, commands):
    assert deploy.main(["--uv", "uv"]) == 0
    assert not any(any(arg.endswith(("run.py", "login.py")) for arg in cmd) for cmd in commands)


def test_subprocess_always_runs_from_project_root_with_literal_arguments(project, monkeypatch):
    calls = []
    monkeypatch.setattr(deploy.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    command = ["python path/中文/python", "file with spaces.py"]
    deploy.execute(command)
    assert calls[0][0] == (command,)
    assert calls[0][1]["cwd"] == project
    assert calls[0][1]["check"] is True
    assert not calls[0][1].get("shell", False)


@pytest.mark.parametrize("headless_line", ["HEADLESS=false\n", "HEADLESS='false'\n", "", "HEADLESS=true\n"])
def test_persist_headless_preserves_auth_and_other_settings(project, monkeypatch, headless_line):
    monkeypatch.chdir(project)
    existing = "# local settings\nDOUYIN_COOKIE='private-cookie'\nWEBHOOK_TEMPLATE='first\nHEADLESS=false\nlast'\n"
    env_file = project / ".env"
    env_file.write_text(existing + headless_line + "TRACE=false\n", encoding="utf-8")

    exec(deploy.HEADLESS_CONFIG, {})

    from dotenv import dotenv_values

    values = dotenv_values(env_file)
    assert values["HEADLESS"] == "true"
    assert values["DOUYIN_COOKIE"] == "private-cookie"
    assert values["WEBHOOK_TEMPLATE"] == "first\nHEADLESS=false\nlast"
    assert values["TRACE"] == "false"
    assert env_file.read_text(encoding="utf-8").startswith(existing)
    updated = env_file.read_bytes()
    exec(deploy.HEADLESS_CONFIG, {})
    assert env_file.read_bytes() == updated


def test_persist_headless_covers_enabled_accounts_only(project, monkeypatch):
    monkeypatch.chdir(project)
    (project / ".env").write_text("HEADLESS=false\n", encoding="utf-8")
    (project / "config").mkdir()
    (project / "config" / "accounts.json").write_text(json.dumps({"accounts": [
        {"id": "one", "env_file": ".env.account1"},
        {"id": "two", "env_file": ".env.account2"},
        {"id": "off", "env_file": ".env.disabled", "enabled": False},
    ]}), encoding="utf-8")
    (project / ".env.account1").write_text("HEADLESS=false\nDOUYIN_COOKIE=one\n", encoding="utf-8")
    (project / ".env.account2").write_text("DOUYIN_COOKIE=two\n", encoding="utf-8")
    (project / ".env.disabled").write_text("HEADLESS=false\n", encoding="utf-8")

    exec(deploy.HEADLESS_CONFIG, {})

    from dotenv import dotenv_values

    for filename in (".env", ".env.account1", ".env.account2"):
        assert dotenv_values(project / filename)["HEADLESS"] == "true"
    assert dotenv_values(project / ".env.account1")["DOUYIN_COOKIE"] == "one"
    assert dotenv_values(project / ".env.account2")["DOUYIN_COOKIE"] == "two"
    assert (project / ".env.disabled").read_text(encoding="utf-8") == "HEADLESS=false\n"


def test_missing_account_env_does_not_create_empty_credentials_or_change_settings(project, monkeypatch):
    monkeypatch.chdir(project)
    (project / ".env").write_text("HEADLESS=false\n", encoding="utf-8")
    (project / "config").mkdir()
    (project / "config" / "accounts.json").write_text(
        '{"accounts":[{"id":"missing","env_file":".env.missing"}]}', encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="账号环境文件不存在"):
        exec(deploy.HEADLESS_CONFIG, {})
    assert not (project / ".env.missing").exists()
    assert (project / ".env").read_text(encoding="utf-8") == "HEADLESS=false\n"
