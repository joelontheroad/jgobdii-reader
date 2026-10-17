# SPDX-FileCopyrightText: 2026 Joel G
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for server presets management and SAE / OEM reference endpoints."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.config import ToolPreset, save_preset
from app.server import create_app


@pytest.fixture(autouse=True)
def configure_mock_preset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure test suite runs against isolated mock adapter preset."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    preset = ToolPreset(name="default", adapter_type="mock")
    save_preset(preset)


def test_presets_list_and_load_endpoints(tmp_path, monkeypatch):
    """Verify listing presets and loading active configuration."""


    app = create_app()
    token = app.state.auth_token
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Presets listing endpoint
    list_resp = client.get("/api/presets", headers=headers)
    assert list_resp.status_code == 200
    presets = list_resp.json()["presets"]
    assert "default" in presets

    # Preset load endpoint
    load_resp = client.get("/api/preset?name=default", headers=headers)
    assert load_resp.status_code == 200
    data = load_resp.json()
    assert data["name"] == "default"
    assert "adapter_type" in data
    assert "adapter_host" in data

    # Path traversal attempt is rejected with 400
    traversal_resp = client.get("/api/preset?name=../../etc/passwd", headers=headers)
    assert traversal_resp.status_code == 400


def test_sae_reference_dtc_endpoints():
    """Verify SAE J2012 reference directory search and system filtering."""
    app = create_app()
    token = app.state.auth_token
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Query all SAE DTCs
    all_resp = client.get("/api/reference/dtc", headers=headers)
    assert all_resp.status_code == 200
    all_dtcs = all_resp.json()["codes"]
    assert len(all_dtcs) > 0

    # Search with query string
    search_resp = client.get("/api/reference/dtc?search=P0420", headers=headers)
    assert search_resp.status_code == 200
    codes = [d["code"] for d in search_resp.json()["codes"]]
    assert "P0420" in codes

    # Filter by subsystem
    sys_resp = client.get("/api/reference/dtc?system=Powertrain", headers=headers)
    assert sys_resp.status_code == 200
    for d in sys_resp.json()["codes"]:
        assert "Powertrain" in d["system"]


def test_manufacturer_specific_dtc_endpoints():
    """Verify OEM manufacturer reference databases for Toyota, Honda, GM, and Ford."""
    app = create_app()
    token = app.state.auth_token
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    for mfg in ["toyota", "honda", "gm", "ford"]:
        resp = client.get(f"/api/reference/mfg-dtc?mfg={mfg}", headers=headers)
        assert resp.status_code == 200
        payload = resp.json()
        assert "manufacturer" in payload
        assert "primary_protocol" in payload
        assert "codes" in payload
        assert len(payload["codes"]) > 0

        # Check fields of OEM DTCs
        sample_code = payload["codes"][0]
        assert "code" in sample_code
        assert "description" in sample_code
        assert "system" in sample_code or "subsystem" in sample_code
        assert "symptoms" in sample_code
        assert "causes" in sample_code
        assert "is_supported" in sample_code


def test_pid_catalog_and_supported_endpoints():
    """Verify PID catalog and vehicle-supported PID bitmask endpoints."""
    app = create_app()
    token = app.state.auth_token
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Catalog
    cat_resp = client.get("/api/pids/catalog", headers=headers)
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    assert cat_data["total_pids"] >= 50
    assert len(cat_data["catalog"]) >= 50

    # Supported PIDs (queries mock adapter by default)
    supp_resp = client.get("/api/pids/supported", headers=headers)
    assert supp_resp.status_code == 200
    supp_data = supp_resp.json()
    assert "supported_pids" in supp_data
    assert "0C" in supp_data["supported_pids"]
    assert "0D" in supp_data["supported_pids"]


def test_mode05_endpoint():
    """Verify Mode 05 Oxygen Sensor test result endpoint."""
    app = create_app()
    token = app.state.auth_token
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/mode05?tid=1", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tid"] == "01"
    assert data["unit"] == "V"
    assert "status" in data


def test_reference_dtc_supported_only_filtering():
    """Verify supported_only query flag on SAE and OEM reference directories."""
    app = create_app()
    token = app.state.auth_token
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # SAE DTCs with supported_only=true
    sae_supp_resp = client.get("/api/reference/dtc?supported_only=true", headers=headers)
    assert sae_supp_resp.status_code == 200
    sae_data = sae_supp_resp.json()
    assert sae_data["count"] > 0
    for d in sae_data["codes"]:
        assert d["is_supported"] is True

    # OEM DTCs with supported_only=true for matching vs non-matching brand
    toyota_resp = client.get("/api/reference/mfg-dtc?mfg=toyota&supported_only=true", headers=headers)
    assert toyota_resp.status_code == 200
    assert toyota_resp.json()["is_brand_supported"] is True
    assert toyota_resp.json()["count"] > 0

    bmw_resp = client.get("/api/reference/mfg-dtc?mfg=bmw&supported_only=true", headers=headers)
    assert bmw_resp.status_code == 200
    assert bmw_resp.json()["is_brand_supported"] is False
    assert bmw_resp.json()["count"] == 0


def test_silent_browser_launch(monkeypatch):
    """Verify that _launch_browser_silently handles subprocess invocation cleanly."""
    from app.server import _launch_browser_silently

    launched = []

    def mock_popen(cmd, **kwargs):
        launched.append((cmd, kwargs))

    monkeypatch.setattr("subprocess.Popen", mock_popen)
    monkeypatch.setattr("shutil.which", lambda prog: f"/usr/bin/{prog}")
    monkeypatch.setattr("sys.platform", "linux")

    test_url = "http://127.0.0.1:8080/?token=abc"
    _launch_browser_silently(test_url)

    assert len(launched) == 1
    assert launched[0][0] == ["/usr/bin/xdg-open", test_url]
    assert launched[0][1].get("start_new_session") is True

