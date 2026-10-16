# SPDX-FileCopyrightText: 2026 Joel G
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests for Linux SocketCAN adapter integration."""

import anyio

from app.adapters.socketcan import SocketCanAdapter


def test_socketcan_capabilities():
    """Verify SocketCanAdapter returns high-speed CAN capabilities."""
    adapter = SocketCanAdapter(interface="can0")
    caps = adapter.get_capabilities()
    assert caps.adapter_type == "socketcan"
    assert caps.can_high_speed is True
    assert "Zero" in caps.buffer_overflow_risk
    assert caps.max_sample_rate_hz == 100


def test_socketcan_status():
    """Verify SocketCanAdapter returns status dictionary."""
    adapter = SocketCanAdapter(interface="can0")
    status = adapter.get_status()
    assert status["adapter_type"] == "Linux SocketCAN (can0)"
    assert status["channel"] == "can0"
    assert status["connected"] is False


def test_socketcan_connect_invalid_interface():
    """Verify that connecting to a non-existent interface fails gracefully without crashing."""
    async def _run():
        adapter = SocketCanAdapter(interface="nonexistent_can_interface_99")
        connected = await adapter.connect()
        # Should safely return False when network interface does not exist
        assert connected is False
        assert adapter.is_connected is False
        await adapter.disconnect()

    anyio.run(_run)
