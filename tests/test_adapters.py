# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests verifying diagnostic adapter implementations and capabilities."""

import asyncio

from app.adapters import AsyncELM327Adapter, J2534UsbAdapter, MockDiagnosticAdapter, get_adapter


def test_mock_adapter_lifecycle():
    """Verify mock adapter connect, query, and disconnect lifecycle."""
    async def _test():
        adapter = MockDiagnosticAdapter()
        assert await adapter.connect() is True
        assert adapter.is_connected is True

        # Test standard PID query (0C = RPM)
        data = await adapter.query_pid("01", "0C")
        assert data == [0x0C, 0x80]

        # Test DTC query
        codes = await adapter.query_dtcs("03")
        assert "P0420" in codes

        # Test enhanced query
        enh_data = await adapter.query_enhanced("7E1", "22", "1940")
        assert enh_data == [0x73]

        # Test CAN frame capture
        frames = await adapter.capture_can_frames(count=2)
        assert len(frames) == 2

        await adapter.disconnect()
        assert adapter.is_connected is False

    asyncio.run(_test())


def test_j2534_adapter_capabilities():
    """Verify J2534 adapter capabilities matrix reflects multi-channel and pin-mux support."""
    async def _test():
        adapter = J2534UsbAdapter(device_name="Tactrix OpenPort 2.0")
        assert await adapter.connect() is True

        caps = adapter.get_capabilities()
        assert caps.can_high_speed is True
        assert caps.can_medium_speed is True  # J2534-2 Ford Pins 3/11
        assert caps.single_wire_can is True   # J2534-2 GM Pin 1
        assert caps.multi_channel_parallel is True
        assert caps.bi_directional_tests is True
        assert "Zero" in caps.buffer_overflow_risk

        await adapter.disconnect()

    asyncio.run(_test())


def test_adapter_factory():
    """Verify adapter factory instantiates the correct adapter subclasses."""
    elm = get_adapter("elm327", host="192.168.0.10", port=35000)
    assert isinstance(elm, AsyncELM327Adapter)

    j2534 = get_adapter("j2534")
    assert isinstance(j2534, J2534UsbAdapter)

    mock = get_adapter("mock")
    assert isinstance(mock, MockDiagnosticAdapter)
