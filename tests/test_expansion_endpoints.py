# SPDX-FileCopyrightText: 2026 Joel G
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Integration tests for new server endpoints (interfaces, diagnostic modes, and OEM DTCs)."""

from fastapi.testclient import TestClient

from app.server import create_app

AUTH_TOKEN = "test-token-expansion-secret-999"  # noqa: S105 - Test fixture token for isolated server endpoint tests
app = create_app(auth_token=AUTH_TOKEN)
client = TestClient(app)


def test_api_interfaces_endpoint():
    """Verify /api/interfaces returns hardware detection payload."""
    res = client.get(f"/api/interfaces?token={AUTH_TOKEN}")
    assert res.status_code == 200
    data = res.json()
    assert "has_can_hardware" in data
    assert "interfaces" in data
    assert "usb_cables" in data
    assert "summary" in data


def test_api_protocols_endpoint():
    """Verify /api/protocols returns all 10 supported communication standards."""
    res = client.get(f"/api/protocols?token={AUTH_TOKEN}")
    assert res.status_code == 200
    data = res.json()
    assert len(data.get("protocols", [])) == 10


def test_api_im_readiness_endpoint():
    """Verify /api/im-readiness returns MIL status and readiness monitors."""
    res = client.get(f"/api/im-readiness?token={AUTH_TOKEN}")
    assert res.status_code == 200
    data = res.json()
    assert "mil_on" in data
    assert "dtc_count" in data
    assert "monitors" in data
    assert "catalyst" in data["monitors"]


def test_api_freeze_frame_endpoint():
    """Verify /api/freeze-frame returns Mode 02 snapshot data."""
    res = client.get(f"/api/freeze-frame?token={AUTH_TOKEN}")
    assert res.status_code == 200
    data = res.json()
    assert "dtc" in data
    assert "telemetry" in data
    assert "0C" in data["telemetry"]  # RPM


def test_api_mode06_endpoint():
    """Verify /api/mode06 returns component monitoring tests."""
    res = client.get(f"/api/mode06?token={AUTH_TOKEN}")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] > 0
    tests = data["tests"]
    assert any(t["status"] in ("PASS", "FAIL") for t in tests)


def test_api_vin_endpoint():
    """Verify /api/vin returns vehicle identification numbers."""
    res = client.get(f"/api/vin?token={AUTH_TOKEN}")
    assert res.status_code == 200
    data = res.json()
    assert "vin" in data
    assert "calibration_id" in data
    assert "cvn" in data


def test_api_decode_dtc_endpoint():
    """Verify /api/decode-dtc decomposes codes and looks up descriptions."""
    res = client.get(f"/api/decode-dtc?code=P0420&token={AUTH_TOKEN}")
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["system"]["letter"] == "P"
    assert "Catalyst" in data.get("known_description", "")


def test_api_reference_mfg_dtc_multi_brands():
    """Verify /api/reference/mfg-dtc returns OEM database codes for various brands."""
    # BMW
    bmw_res = client.get(f"/api/reference/mfg-dtc?mfg=bmw&token={AUTH_TOKEN}")
    assert bmw_res.status_code == 200
    bmw_data = bmw_res.json()
    assert bmw_data["total_count"] > 4000
    assert bmw_data["count"] <= 500

    # Volkswagen with search
    vw_res = client.get(f"/api/reference/mfg-dtc?mfg=volkswagen&search=turbo&token={AUTH_TOKEN}")
    assert vw_res.status_code == 200
    vw_data = vw_res.json()
    assert vw_data["total_count"] > 0
    assert all("turbo" in c["description"].lower() or "turbo" in c["code"].lower() for c in vw_data["codes"])

    # Toyota fallback/merge
    toyota_res = client.get(f"/api/reference/mfg-dtc?mfg=toyota&token={AUTH_TOKEN}")
    assert toyota_res.status_code == 200
    toyota_data = toyota_res.json()
    assert toyota_data["count"] > 0
