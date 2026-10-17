# SPDX-FileCopyrightText: 2026 Joel G
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for in-memory mock diagnostic adapter fault injection and simulator state."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.adapters.mock import MockDiagnosticAdapter
from app.config import ToolPreset, save_preset
from app.server import create_app


@pytest.fixture(autouse=True)
def configure_mock_preset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure test suite runs against isolated mock adapter preset."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    preset = ToolPreset(name="default", adapter_type="mock")
    save_preset(preset)


@pytest.fixture(autouse=True)
def reset_mock_state():
    """Ensure in-memory mock state is clean before and after each test."""
    MockDiagnosticAdapter.reset_default_dtcs()
    yield
    MockDiagnosticAdapter.reset_default_dtcs()



@pytest.mark.anyio
async def test_mock_adapter_dynamic_dtc_injection():
    """Verify in-memory state manipulation via adapter class methods."""
    adapter = MockDiagnosticAdapter()
    connected = await adapter.connect()
    assert connected is True

    # Initial state should contain factory defaults
    initial_codes = await adapter.query_dtcs(mode_hex="03")
    assert "P0300" in initial_codes
    assert "P0420" in initial_codes

    # Set custom stored codes
    MockDiagnosticAdapter.set_dtcs(stored=["P0420", "P0442"], pending=["P0115"])
    assert await adapter.query_dtcs(mode_hex="03") == ["P0420", "P0442"]
    assert await adapter.query_dtcs(mode_hex="07") == ["P0115"]

    # Clear codes
    cleared = await adapter.clear_dtcs()
    assert cleared is True
    assert await adapter.query_dtcs(mode_hex="03") == []
    assert await adapter.query_dtcs(mode_hex="07") == []

    # Reset factory defaults
    MockDiagnosticAdapter.reset_default_dtcs()
    stored_reset = await adapter.query_dtcs(mode_hex="03")
    assert "P0300" in stored_reset


def test_server_mock_dtc_endpoints():
    """Verify HTTP API endpoints for reading and injecting simulator trouble codes."""
    app = create_app()
    token = app.state.auth_token
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Query initial state
    resp = client.get("/api/mock/dtc", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "state" in data
    assert "P0300" in data["state"]["03"]

    # Inject custom fault cluster
    inject_resp = client.post(
        "/api/mock/dtc",
        json={"action": "set", "stored": ["P0171", "P0300", "P0420"]},
        headers=headers,
    )
    assert inject_resp.status_code == 200
    assert inject_resp.json()["state"]["03"] == ["P0171", "P0300", "P0420"]

    # Verify DTC endpoint reflects injected codes
    dtc_resp = client.get("/api/dtc", headers=headers)
    assert dtc_resp.status_code == 200
    returned_codes = [item["code"] for item in dtc_resp.json()["dtcs"]]
    assert "P0420" in returned_codes
    assert "P0171" in returned_codes

    # Clear codes via Mode 04 endpoint
    clear_resp = client.post("/api/dtc/clear", headers=headers)
    assert clear_resp.status_code == 200
    assert clear_resp.json()["status"] == "cleared"

    # Verify simulator state is now empty
    empty_resp = client.get("/api/dtc", headers=headers)
    assert empty_resp.json()["dtcs"] == []
