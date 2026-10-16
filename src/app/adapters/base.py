# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Diagnostic adapter base interface and capability reporting models.

Defines the universal abstract contract implemented by ELM327 Wi-Fi adapters,
J2534 Pass-Thru USB hardware, and testing mock adapters.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass(frozen=True)
class AdapterCapabilities:
    """Hardware and protocol capabilities exposed by an OBD-II interface."""

    adapter_type: str
    can_high_speed: bool = True
    can_medium_speed: bool = False
    single_wire_can: bool = False
    iso_9141_kline: bool = True
    multi_channel_parallel: bool = False
    bi_directional_tests: bool = False
    buffer_overflow_risk: str = "Low"
    max_sample_rate_hz: int = 25
    supported_protocols: List[str] = field(default_factory=lambda: ["ISO 15765-4 CAN", "ISO 9141-2"])


class DiagnosticAdapterBase(ABC):
    """Abstract base interface for all diagnostic hardware adapters."""

    @abstractmethod
    async def connect(self) -> bool:
        """Establish physical or network connection to the diagnostic interface.

        Returns:
            True if connection and handshake succeeded, False otherwise.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully terminate connection and release hardware channels."""
        pass

    @abstractmethod
    async def query_pid(self, mode_hex: str, pid_hex: str) -> Optional[List[int]]:
        """Send a standard diagnostic query and return raw data payload bytes.

        Args:
            mode_hex: 2-character hexadecimal mode (e.g. '01').
            pid_hex: 2-character hexadecimal PID (e.g. '0C').

        Returns:
            List of data bytes, or None on error or timeout.
        """
        pass

    @abstractmethod
    async def query_dtcs(self, mode_hex: str = "03") -> List[str]:
        """Request diagnostic trouble codes for the designated service mode.

        Args:
            mode_hex: Service mode ('03' for stored, '07' for pending, '0A' for permanent).

        Returns:
            List of 5-character DTC strings (e.g. ['P0420', 'P0300']).
        """
        pass

    @abstractmethod
    async def clear_dtcs(self) -> bool:
        """Issue Mode 04 clear diagnostic information request.

        Returns:
            True if vehicle accepted reset, False otherwise.
        """
        pass

    @abstractmethod
    async def query_enhanced(
        self,
        header: str,
        service_mode: str,
        pid_hex: str,
    ) -> Optional[List[int]]:
        """Send a targeted physical request to an ECU for enhanced manufacturer data.

        Args:
            header: Target ECU physical CAN identifier (e.g. '7E0', '7E1', '7E2').
            service_mode: Service mode ('21' or '22').
            pid_hex: Enhanced Parameter ID or DID (e.g. '1940', 'C3', '1624').

        Returns:
            List of payload data bytes, or None if unrecognized.
        """
        pass

    @abstractmethod
    async def capture_can_frames(
        self,
        count: int = 10,
        filter_id: Optional[str] = None,
        timeout: float = 2.0,
    ) -> List[Any]:
        """Capture raw CAN frames from the bus with optional address filtering.

        Args:
            count: Maximum number of frames to capture.
            filter_id: Optional CAN identifier to isolate (e.g. '7E8' or '201').
            timeout: Maximum seconds to wait for frames.

        Returns:
            List of captured CanFrame instances.
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> AdapterCapabilities:
        """Return the hardware capabilities matrix for this adapter."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return instantaneous adapter status, battery voltage, and connection health."""
        pass

    async def query_supported_pids(self) -> Set[str]:
        """Query Mode 01 PID 0x00 and subsequent blocks to discover vehicle-supported PIDs.

        Returns:
            Set of 2-character hex PID strings supported by the connected ECU.
        """
        return set()

    async def query_mode05(self, tid: int = 1) -> Optional[Dict[str, Any]]:
        """Query Mode 05 Oxygen Sensor Monitoring test results for legacy vehicles.

        Args:
            tid: Test Identifier (TID, 1 to 10).

        Returns:
            Dictionary with test value, thresholds, and status, or None if unsupported.
        """
        return None
