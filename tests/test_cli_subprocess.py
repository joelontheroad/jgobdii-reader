# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Dedicated subprocess test suite verifying CLI exit codes and stream discipline.

Enforces Standard 3 (Separation of Streams), Standard 7 (Subprocess Testing),
and Standard 8 (Standardized Exit Codes: 0, 1, 2, 130).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def isolated_env(tmp_path: Path) -> dict:
    """Return a clean environment dictionary with XDG directories redirected to tmp_path."""
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
    env["XDG_DATA_HOME"] = str(tmp_path / "data")
    env["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent / "src")
    return env


def test_subprocess_help(isolated_env: dict):
    """Verify that --help exits with code 0 and prints usage to stdout or stderr."""
    res = subprocess.run(
        [sys.executable, "-m", "app.cli", "--help"],
        capture_output=True,
        text=True,
        env=isolated_env,
    )
    assert res.returncode == 0
    combined = res.stdout + res.stderr
    assert "usage:" in combined
    assert "jgobdii-reader" in combined


def test_subprocess_version(isolated_env: dict):
    """Verify that --version exits with code 0 and outputs AGPLv3 and repository URL."""
    res = subprocess.run(
        [sys.executable, "-m", "app.cli", "--version"],
        capture_output=True,
        text=True,
        env=isolated_env,
    )
    assert res.returncode == 0
    combined = res.stdout + res.stderr
    assert "AGPL" in combined
    assert "Source:" in combined


def test_subprocess_syntax_error_exit_code_2(isolated_env: dict):
    """Verify that invalid arguments or unknown subcommands exit with code 2."""
    res = subprocess.run(
        [sys.executable, "-m", "app.cli", "--non-existent-flag"],
        capture_output=True,
        text=True,
        env=isolated_env,
    )
    assert res.returncode == 2
    assert "error:" in res.stderr.lower() or "unrecognized" in res.stderr.lower()


def test_subprocess_operational_failure_exit_code_1(isolated_env: dict):
    """Verify that operational failure (such as unreachable host) exits with code 1."""
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "scan",
            "--adapter",
            "elm327",
            "--host",
            "192.0.2.1",  # RFC 5737 TEST-NET unreachable IP
            "--port",
            "35000",
        ],
        capture_output=True,
        text=True,
        env=isolated_env,
    )
    assert res.returncode == 1
    assert "Failed to connect" in res.stderr or "Error" in res.stderr


def test_subprocess_stream_separation_json(isolated_env: dict):
    """Verify strict stream separation: machine JSON on stdout, diagnostics on stderr."""
    res = subprocess.run(
        [sys.executable, "-m", "app.cli", "--json", "pins", "toyota"],
        capture_output=True,
        text=True,
        env=isolated_env,
    )
    assert res.returncode == 0
    # stdout MUST be valid parseable JSON without diagnostic banner contamination
    data = json.loads(res.stdout)
    assert "pinout" in data
    assert len(data["pinout"]) == 16


def test_subprocess_no_color_compliance(isolated_env: dict):
    """Verify that NO_COLOR environment variable suppresses ANSI color escape sequences."""
    env_with_no_color = isolated_env.copy()
    env_with_no_color["NO_COLOR"] = "1"

    res = subprocess.run(
        [sys.executable, "-m", "app.cli", "pins"],
        capture_output=True,
        text=True,
        env=env_with_no_color,
    )
    assert res.returncode == 0
    # Zero ANSI escape sequences in stdout and stderr
    assert "\033[" not in res.stdout
    assert "\033[" not in res.stderr


def test_subprocess_preset_show_json(isolated_env: dict):
    """Verify preset show with --json produces valid JSON on stdout."""
    res = subprocess.run(
        [sys.executable, "-m", "app.cli", "--json", "preset", "show"],
        capture_output=True,
        text=True,
        env=isolated_env,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["name"] == "default"
    assert "adapter_type" in data
    assert "vehicle_domain" in data


def test_subprocess_mock_scan(isolated_env: dict):
    """Verify scan command using mock adapter runs cleanly and returns code 0."""
    res = subprocess.run(
        [sys.executable, "-m", "app.cli", "--json", "scan", "--adapter", "mock"],
        capture_output=True,
        text=True,
        env=isolated_env,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["status"] == "success"
    assert "stored_dtcs" in data
    assert "capabilities" in data


def test_subprocess_enhanced_toyota(isolated_env: dict):
    """Verify enhanced manufacturer telemetry outputs valid JSON with Mode 21/22 parameters."""
    res = subprocess.run(
        [sys.executable, "-m", "app.cli", "--json", "enhanced", "toyota", "--adapter", "mock"],
        capture_output=True,
        text=True,
        env=isolated_env,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["manufacturer"] == "toyota"
    assert len(data["parameters"]) > 0
    assert any(p["id"] == "toyota_hybrid_soc" for p in data["parameters"])


def test_subprocess_can_monitor(isolated_env: dict):
    """Verify can-monitor command captures frames and outputs valid JSON."""
    res = subprocess.run(
        [sys.executable, "-m", "app.cli", "--json", "can-monitor", "--count", "3", "--adapter", "mock"],
        capture_output=True,
        text=True,
        env=isolated_env,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert "frames" in data
    assert len(data["frames"]) == 3


def test_subprocess_dtc_list_and_clear(isolated_env: dict):
    """Verify dtc list and dtc clear subcommands execute cleanly."""
    res_list = subprocess.run(
        [sys.executable, "-m", "app.cli", "--json", "dtc", "list", "--adapter", "mock"],
        capture_output=True,
        text=True,
        env=isolated_env,
    )
    assert res_list.returncode == 0
    data = json.loads(res_list.stdout)
    assert "codes" in data
    assert len(data["codes"]) > 0

    res_clear = subprocess.run(
        [sys.executable, "-m", "app.cli", "--json", "dtc", "clear", "--adapter", "mock"],
        capture_output=True,
        text=True,
        env=isolated_env,
    )
    assert res_clear.returncode == 0
    clear_data = json.loads(res_clear.stdout)
    assert clear_data["status"] == "cleared"

