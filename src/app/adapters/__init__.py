# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Diagnostic adapter factory package.

Instantiates either AsyncELM327Adapter, J2534UsbAdapter, or MockDiagnosticAdapter
based on configuration settings or runtime parameters.
"""

from typing import Optional

from app.adapters.base import AdapterCapabilities, DiagnosticAdapterBase
from app.adapters.elm327 import AsyncELM327Adapter
from app.adapters.j2534 import J2534UsbAdapter
from app.adapters.mock import MockDiagnosticAdapter
from app.adapters.socketcan import SocketCanAdapter


def get_adapter(
    adapter_type: str = "elm327",
    host: str = "192.168.0.10",
    port: int = 35000,
    timeout: float = 2.5,
    protocol_cmd: str = "ATSP0",
    device_name: Optional[str] = None,
) -> DiagnosticAdapterBase:
    """Instantiate a DiagnosticAdapterBase implementation.

    Args:
        adapter_type: Adapter identifier ('elm327', 'j2534', 'socketcan', or 'mock').
        host: Hostname or IP address for ELM327 Wi-Fi.
        port: TCP port number for ELM327 Wi-Fi.
        timeout: Socket read/write timeout in seconds.
        protocol_cmd: AT command protocol selection.
        device_name: Optional J2534 or SocketCAN device/interface identifier string.

    Returns:
        Configured DiagnosticAdapterBase instance.
    """
    clean_type = adapter_type.lower().strip()
    if clean_type == "j2534":
        return J2534UsbAdapter(device_name=device_name or "J2534 Pass-Thru Device")
    if clean_type == "socketcan":
        return SocketCanAdapter(interface=device_name or "can0", timeout=timeout)
    if clean_type == "mock":
        return MockDiagnosticAdapter()
    return AsyncELM327Adapter(host=host, port=port, timeout=timeout, protocol_cmd=protocol_cmd)


__all__ = [
    "AdapterCapabilities",
    "AsyncELM327Adapter",
    "DiagnosticAdapterBase",
    "J2534UsbAdapter",
    "MockDiagnosticAdapter",
    "SocketCanAdapter",
    "get_adapter",
]
