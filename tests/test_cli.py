# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test suite verifying CLI execution, exit codes, and isolated XDG filesystem safety."""

import json
from pathlib import Path

import pytest

from app.cli import main
from app.config import (
    safe_resolve_preset_path,
    sanitize_log_path,
)


@pytest.fixture(autouse=True)
def isolate_xdg_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure all tests run strictly against an isolated temporary directory."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))


def test_cli_help(capsys: pytest.CaptureFixture):
    """Verify --help exits with code 0 and prints usage."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out or "usage:" in captured.err


def test_cli_version(capsys: pytest.CaptureFixture):
    """Verify --version contains AGPL-3.0 reference and repository URL."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    output = captured.out or captured.err
    assert "AGPL" in output
    assert "Source:" in output


def test_preset_show_json(capsys: pytest.CaptureFixture):
    """Verify preset show with --json outputs valid parseable JSON to stdout."""
    ret = main(["--json", "preset", "show"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["name"] == "default"
    assert data["max_items"] == 50


def test_path_traversal_prevention():
    """Verify safe_resolve_preset_path blocks path traversal attempts (CWE-22)."""
    with pytest.raises(PermissionError) as excinfo:
        safe_resolve_preset_path("../../etc/passwd")
    assert "escapes allowed directory" in str(excinfo.value)


def test_log_sanitization():
    """Verify sensitive home directory username is scrubbed from logs."""
    home = str(Path.home())
    test_path = f"{home}/projects/secret/file.txt"
    sanitized = sanitize_log_path(test_path)
    assert home not in sanitized
    assert sanitized.startswith("~<USER>")


def test_reset_config(capsys: pytest.CaptureFixture):
    """Verify --reset-config executes cleanly with code 0."""
    ret = main(["--reset-config"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "reset to factory defaults" in captured.err


def test_serve_help_no_browser(capsys: pytest.CaptureFixture):
    """Verify serve subcommand help documents --no-browser option."""
    with pytest.raises(SystemExit) as excinfo:
        main(["serve", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    output = captured.out or captured.err
    assert "--no-browser" in output


def test_clickable_url_formatting(monkeypatch: pytest.MonkeyPatch):
    """Verify format_clickable_url respects TTY detection and NO_COLOR."""
    from app.server import format_clickable_url

    class MockTTYStream:
        def isatty(self):
            return True

    class MockNonTTYStream:
        def isatty(self):
            return False

    url = "http://127.0.0.1:8080/?token=abc"

    # 1. TTY and NO_COLOR not set -> OSC 8 link
    monkeypatch.delenv("NO_COLOR", raising=False)
    osc8_link = format_clickable_url(url, stream=MockTTYStream())
    assert f"\033]8;;{url}\033\\{url}\033]8;;\033\\" == osc8_link

    # 2. Non-TTY -> plain text URL
    plain_link = format_clickable_url(url, stream=MockNonTTYStream())
    assert plain_link == url

    # 3. NO_COLOR set -> plain text URL even on TTY
    monkeypatch.setenv("NO_COLOR", "1")
    nocolor_link = format_clickable_url(url, stream=MockTTYStream())
    assert nocolor_link == url


def test_open_browser_suppression(monkeypatch: pytest.MonkeyPatch):
    """Verify open_browser correctly honors no_browser flag and CI environment."""
    from app.server import open_browser

    url = "http://127.0.0.1:8080"
    # When no_browser is True, browser is never opened
    assert open_browser(url, no_browser=True) is False

    # When CI is set to true, browser is never opened
    monkeypatch.setenv("CI", "true")
    assert open_browser(url, no_browser=False) is False

