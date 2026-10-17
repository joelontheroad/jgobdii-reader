# SPDX-FileCopyrightText: 2026 Joel G
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for two-tier connection status detection, state reflection, and offline VIN decoding."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import ToolPreset, save_preset
from app.protocol import decode_vin
from app.server import create_app

AUTH_TOKEN = "test-token-conn-state-999"  # noqa: S105 - Test fixture auth token for isolated server tests


@pytest.fixture
def isolated_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Provide a TestClient connected to an isolated temporary XDG environment."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    # Initial default preset configured with physical ELM327 Wi-Fi adapter (unreachable in tests)
    preset = ToolPreset(name="default", adapter_type="elm327", adapter_host="127.0.0.1", adapter_port=39999)
    save_preset(preset)

    app = create_app(auth_token=AUTH_TOKEN)
    return TestClient(app)


def test_decode_vin_valid_vehicles():
    """Verify ISO 3779 VIN decoder correctly identifies Year, Make, Model, and Country."""
    # 2000 Toyota Camry
    res_camry = decode_vin("4T1BE32K0YU123456")
    assert res_camry["valid"] is True
    assert res_camry["year"] == 2000
    assert res_camry["make"] == "Toyota"
    assert res_camry["model"] == "Camry"
    assert "2000 Toyota Camry" in res_camry["display"]
    assert res_camry["country"] == "United States"

    # 2018 Honda Accord
    res_accord = decode_vin("1HGCR2F83JA123456")
    assert res_accord["valid"] is True
    assert res_accord["year"] == 2018
    assert res_accord["make"] == "Honda"
    assert res_accord["model"] == "Accord"
    assert "2018 Honda Accord" in res_accord["display"]

    # 2023 Ford F-150
    res_f150 = decode_vin("1FTFW1ED4PK123456")
    assert res_f150["valid"] is True
    assert res_f150["year"] == 2023
    assert res_f150["make"] == "Ford"
    assert res_f150["model"] == "F-150"
    assert "2023 Ford F-150" in res_f150["display"]


def test_decode_vin_invalid_and_empty():
    """Verify decode_vin handles empty strings, none, and malformed identifiers cleanly."""
    res_none = decode_vin(None)
    assert res_none["valid"] is False
    assert res_none["display"] == "Vehicle: Not Detected"

    res_empty = decode_vin("")
    assert res_empty["valid"] is False
    assert res_empty["year"] is None

    res_short = decode_vin("12345")
    assert res_short["valid"] is False


def test_connection_status_disconnected(isolated_client: TestClient):
    """Verify /api/connection-status accurately reports disconnected state when hardware is absent."""
    res = isolated_client.get(f"/api/connection-status?force=true&token={AUTH_TOKEN}")
    assert res.status_code == 200
    data = res.json()
    assert data["configured_adapter"] == "elm327"
    assert data["adapter_connected"] is False
    assert data["vehicle_detected"] is False
    assert data["is_mock"] is False
    assert data["status_state"] == "disconnected"
    assert "Disconnected" in data["status_text"]
    assert data["vehicle"]["display"] == "Vehicle: Not Detected"


def test_telemetry_disconnected_no_fake_data(isolated_client: TestClient):
    """Verify /api/telemetry does NOT emit simulated fake data when disconnected."""
    res = isolated_client.get(f"/api/telemetry?token={AUTH_TOKEN}")
    assert res.status_code == 200
    data = res.json()
    assert data["connected"] is False
    assert data["is_mock"] is False
    assert data["0C"] is None
    assert data["0D"] is None
    assert data["telemetry"] is None


def test_adapter_switch_to_mock_and_back(isolated_client: TestClient):
    """Verify switching to mock adapter activates simulation and vehicle display."""
    # 1. Switch to mock
    switch_res = isolated_client.post(f"/api/adapter/switch?adapter_type=mock&token={AUTH_TOKEN}")
    assert switch_res.status_code == 200
    assert switch_res.json()["adapter_type"] == "mock"

    # 2. Verify connection status in mock mode
    status_res = isolated_client.get(f"/api/connection-status?token={AUTH_TOKEN}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["is_mock"] is True
    assert status_data["adapter_connected"] is True
    assert status_data["status_state"] == "mock"
    assert "Toyota Camry" in status_data["vehicle"]["display"]

    # 3. Verify telemetry in mock mode provides simulated values
    telem_res = isolated_client.get(f"/api/telemetry?token={AUTH_TOKEN}")
    assert telem_res.status_code == 200
    telem_data = telem_res.json()
    assert telem_data["connected"] is True
    assert telem_data["is_mock"] is True
    assert telem_data["0C"] is not None

    # 4. Verify invalid adapter type is rejected with 400
    bad_res = isolated_client.post(f"/api/adapter/switch?adapter_type=nonexistent_cable&token={AUTH_TOKEN}")
    assert bad_res.status_code == 400
