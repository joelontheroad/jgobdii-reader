# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Deterministic mock diagnostic adapter for test suites and offline execution.

Provides predictable responses conforming to the DiagnosticAdapterBase contract
without requiring active physical network interfaces.
"""

from typing import Any, Dict, List, Optional, Set

from app.adapters.base import AdapterCapabilities, DiagnosticAdapterBase
from app.can_bus import CanFrame

_DEFAULT_STORED_DTCS = ["P0420", "P0300"]
_DEFAULT_PENDING_DTCS = ["P0171"]
_DEFAULT_PERMANENT_DTCS: List[str] = []

_mock_dtc_state: Dict[str, List[str]] = {
    "03": list(_DEFAULT_STORED_DTCS),
    "07": list(_DEFAULT_PENDING_DTCS),
    "0A": list(_DEFAULT_PERMANENT_DTCS),
}


class MockDiagnosticAdapter(DiagnosticAdapterBase):
    """In-memory mock adapter returning deterministic vehicle parameters."""

    def __init__(self, should_fail: bool = False):
        """Initialize mock adapter.

        Args:
            should_fail: If True, forces connect() to simulate network/device failure.
        """
        self.should_fail = should_fail
        self.is_connected = False
        self.active_header = "7DF"

    @classmethod
    def set_dtcs(
        cls,
        stored: Optional[List[str]] = None,
        pending: Optional[List[str]] = None,
        permanent: Optional[List[str]] = None,
    ) -> None:
        """Set simulated DTC codes for modes 03, 07, and 0A.

        Args:
            stored: Optional list of confirmed trouble codes (Mode 03).
            pending: Optional list of pending trouble codes (Mode 07).
            permanent: Optional list of permanent trouble codes (Mode 0A).
        """
        if stored is not None:
            _mock_dtc_state["03"] = [c.upper().strip() for c in stored if c.strip()]
        if pending is not None:
            _mock_dtc_state["07"] = [c.upper().strip() for c in pending if c.strip()]
        if permanent is not None:
            _mock_dtc_state["0A"] = [c.upper().strip() for c in permanent if c.strip()]

    @classmethod
    def add_dtc(cls, code: str, mode_hex: str = "03") -> None:
        """Add a single DTC to the mock simulation state.

        Args:
            code: 5-character alphanumeric trouble code string.
            mode_hex: Diagnostic mode identifier ('03', '07', or '0A').
        """
        clean_code = code.upper().strip()
        mode = mode_hex.upper().strip()
        if mode not in _mock_dtc_state:
            _mock_dtc_state[mode] = []
        if clean_code and clean_code not in _mock_dtc_state[mode]:
            _mock_dtc_state[mode].append(clean_code)

    @classmethod
    def reset_default_dtcs(cls) -> None:
        """Reset simulated DTCs to factory mock defaults."""
        _mock_dtc_state["03"] = list(_DEFAULT_STORED_DTCS)
        _mock_dtc_state["07"] = list(_DEFAULT_PENDING_DTCS)
        _mock_dtc_state["0A"] = list(_DEFAULT_PERMANENT_DTCS)

    @classmethod
    def get_all_dtcs(cls) -> Dict[str, List[str]]:
        """Return a copy of the active simulated DTC dictionary with mode and alias keys."""
        state = {k: list(v) for k, v in _mock_dtc_state.items()}
        state["stored"] = list(_mock_dtc_state.get("03", []))
        state["pending"] = list(_mock_dtc_state.get("07", []))
        state["permanent"] = list(_mock_dtc_state.get("0A", []))
        return state

    async def connect(self) -> bool:
        """Simulate adapter connection."""
        if self.should_fail:
            self.is_connected = False
            return False
        self.is_connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnect."""
        self.is_connected = False

    async def query_pid(self, mode_hex: str, pid_hex: str) -> Optional[List[int]]:
        """Return simulated PID bytes."""
        if not self.is_connected:
            return None
        pid = pid_hex.upper().strip()
        # Mode 01 Support Bitmaps
        if pid == "00":  # PIDs 01-20 Supported Bitmap
            return [0xBE, 0x1F, 0xF8, 0x13]
        if pid == "20":  # PIDs 21-40 Supported Bitmap
            return [0x80, 0x00, 0x20, 0x01]
        if pid == "40":  # PIDs 41-60 Supported Bitmap
            return [0xFE, 0x00, 0x00, 0x00]

        if pid == "01":  # I/M Readiness (MIL ON, 2 DTCs, tests ready/incomplete)
            return [0x82, 0x07, 0x65, 0x01]
        if pid == "04":  # Calculated Engine Load (~35%)
            return [0x5A]
        if pid == "05":  # 85 °C (85 + 40 = 125 = 0x7D)
            return [0x7D]
        if pid == "06":  # STFT Bank 1 (+1.56%)
            return [0x82]
        if pid == "07":  # LTFT Bank 1 (+0.78%)
            return [0x81]
        if pid == "0A":  # Fuel Pressure (gauge, 300 kPa)
            return [0x64]
        if pid == "0B":  # MAP (35 kPa)
            return [0x23]
        if pid == "0C":  # 800 RPM: ((0x0C * 256) + 0x80) / 4 = 800
            return [0x0C, 0x80]
        if pid == "0D":  # 60 km/h
            return [0x3C]
        if pid == "0E":  # Timing Advance (14.5 degrees -> (14.5 + 64) * 2 = 157 = 0x9D)
            return [0x9D]
        if pid == "0F":  # Intake Air Temp (28 °C -> 68 = 0x44)
            return [0x44]
        if pid == "10":  # 3.5 g/s MAF (350 = 0x015E)
            return [0x01, 0x5E]
        if pid == "11":  # 20 % throttle (20 * 255 / 100 = 51 = 0x33)
            return [0x33]
        if pid == "14":  # 0.45 V O2 (0.45 * 200 = 90 = 0x5A)
            return [0x5A]
        if pid == "1F":  # Run time since engine start (600s = 0x0258)
            return [0x02, 0x58]
        if pid == "21":  # Distance traveled with MIL on (100km = 0x0064)
            return [0x00, 0x64]
        if pid == "22":  # Fuel Rail Pressure gauge (316 kPa)
            return [0x0F, 0xA0]
        if pid == "2C":  # Commanded EGR (12.5%)
            return [0x20]
        if pid == "2E":  # Commanded Evap Purge (25%)
            return [0x40]
        if pid == "2F":  # Fuel Tank Level (70.6%)
            return [0xB4]
        if pid == "31":  # Distance since codes cleared (1200km = 0x04B0)
            return [0x04, 0xB0]
        if pid == "33":  # Absolute Barometric Pressure (101 kPa)
            return [0x65]
        if pid == "42":  # Control Module Voltage (14.000 V -> 14000 = 0x36B0)
            return [0x36, 0xB0]
        if pid == "44":  # Commanded Equivalence Ratio (Lambda 1.000)
            return [0x80, 0x00]
        if pid == "45":  # Relative Throttle Position (20%)
            return [0x33]
        if pid == "46":  # Ambient Air Temp (20 °C -> 60 = 0x3C)
            return [0x3C]
        if pid == "52":  # Ethanol fuel (10.2%)
            return [0x1A]
        if pid == "5B":  # Hybrid Battery Remaining (74.9%)
            return [0xBF]
        if pid == "5C":  # Engine Oil Temp (80 °C -> 120 = 0x78)
            return [0x78]
        if pid == "5E":  # Fuel Rate (2.5 L/h -> 50 = 0x0032)
            return [0x00, 0x32]
        return [0x00]

    async def query_supported_pids(self) -> Set[str]:
        """Return simulated set of vehicle-supported Mode 01 PIDs."""
        if not self.is_connected:
            return set()
        return {
            "01", "03", "04", "05", "06", "07", "0A", "0B", "0C", "0D", "0E", "0F",
            "10", "11", "12", "14", "15", "1C", "1F", "20", "21", "22", "2C", "2E",
            "2F", "30", "31", "33", "40", "42", "43", "44", "45", "46", "4C", "52",
            "5B", "5C", "5E",
        }

    async def query_mode05(self, tid: int = 1) -> Optional[Dict[str, Any]]:
        """Return simulated Mode 05 Oxygen Sensor Monitoring test result."""
        if not self.is_connected:
            return None
        from app.protocol import decode_mode05_test
        return decode_mode05_test(tid, [0x00, 0x5A])

    async def query_dtcs(self, mode_hex: str = "03") -> List[str]:
        """Return simulated DTC codes."""
        if not self.is_connected:
            return []
        mode = mode_hex.upper().strip()
        return list(_mock_dtc_state.get(mode, []))

    async def clear_dtcs(self) -> bool:
        """Simulate clearing DTCs."""
        if not self.is_connected:
            return False
        _mock_dtc_state["03"].clear()
        _mock_dtc_state["07"].clear()
        return True

    async def query_freeze_frame(self) -> Dict[str, Any]:
        """Return simulated Mode 02 Freeze Frame telemetry snapshot."""
        if not self.is_connected:
            return {"dtc": None, "frame_number": 0, "telemetry": {}}
        stored = _mock_dtc_state.get("03", [])
        causing_dtc = stored[0] if stored else "P0420"
        return {
            "dtc": causing_dtc,
            "frame_number": 0,
            "telemetry": {
                "0C": 2450.0,
                "0D": 65.0,
                "05": 92.0,
                "04": 62.4,
                "11": 28.5,
                "0F": 24.0,
                "0E": 14.5,
                "10": 18.2,
                "06": 2.34,
                "07": 0.78,
            },
        }

    async def query_mode06(self) -> List[Dict[str, Any]]:
        """Return simulated Mode 06 On-Board Diagnostic Component Monitoring test results."""
        if not self.is_connected:
            return []
        return [
            {
                "obdmid": "01",
                "name": "Exhaust Gas Sensor Monitor Bank 1 - Sensor 1",
                "tid": "81",
                "cid": "01",
                "description": "Rich-to-Lean sensor switch time",
                "value": 0.045,
                "min": 0.010,
                "max": 0.080,
                "unit": "s",
                "status": "PASS",
            },
            {
                "obdmid": "02",
                "name": "Exhaust Gas Sensor Monitor Bank 1 - Sensor 2",
                "tid": "82",
                "cid": "02",
                "description": "Lean-to-Rich sensor switch time",
                "value": 0.052,
                "min": 0.010,
                "max": 0.080,
                "unit": "s",
                "status": "PASS",
            },
            {
                "obdmid": "21",
                "name": "Catalyst Monitor Bank 1",
                "tid": "A2",
                "cid": "0B",
                "description": "Catalytic converter oxygen storage capacity ratio",
                "value": 0.82,
                "min": 0.00,
                "max": 0.75,
                "unit": "ratio",
                "status": "FAIL",
            },
            {
                "obdmid": "31",
                "name": "Evaporative System Monitor (0.040 in leak detection)",
                "tid": "3C",
                "cid": "05",
                "description": "EVAP canister bleed-down vacuum decay",
                "value": 1.45,
                "min": 1.20,
                "max": 3.50,
                "unit": "kPa",
                "status": "PASS",
            },
            {
                "obdmid": "35",
                "name": "Purge Flow Monitor",
                "tid": "3F",
                "cid": "01",
                "description": "Purge valve delta flow vs duty cycle",
                "value": 12.4,
                "min": 8.0,
                "max": 25.0,
                "unit": "g/s",
                "status": "PASS",
            },
            {
                "obdmid": "A1",
                "name": "Misfire Cylinder 1 Monitor",
                "tid": "0C",
                "cid": "01",
                "description": "Weighted cylinder misfire percentage",
                "value": 0.12,
                "min": 0.00,
                "max": 1.50,
                "unit": "%",
                "status": "PASS",
            },
        ]

    async def query_vin(self) -> Dict[str, str]:
        """Return simulated Mode 09 vehicle identification data."""
        if not self.is_connected:
            return {"vin": "", "calibration_id": "", "cvn": ""}
        return {
            "vin": "4T1BE32K0YU123456",
            "calibration_id": "89663-33230",
            "cvn": "E8B2C41D",
        }

    async def check_vehicle_connected(self) -> bool:
        """Check simulated vehicle connectivity. Always returns True in mock mode."""
        return self.is_connected


    async def query_enhanced(
        self,
        header: str,
        service_mode: str,
        pid_hex: str,
    ) -> Optional[List[int]]:
        """Return simulated enhanced manufacturer data."""
        if not self.is_connected:
            return None
        self.active_header = header.upper().strip()
        pid = pid_hex.upper().strip()

        if pid == "C3":  # Hybrid battery (15.2V)
            return [0x05, 0xF0]
        if pid == "82":  # Toyota ATF temp (70 °C -> 110 = 0x6E)
            return [0x6E]
        if pid == "1940":  # GM Trans temp (75 °C -> 115 = 0x73)
            return [0x73]
        if pid == "1624":  # Ford CHT (90 °C -> 130 = 0x82)
            return [0x82]
        if pid == "1101":  # Honda VTEC
            return [0x01]
        return [0x00]

    async def capture_can_frames(
        self,
        count: int = 10,
        filter_id: Optional[str] = None,
        timeout: float = 2.0,
    ) -> List[CanFrame]:
        """Return simulated CAN frames."""
        frames = []
        fid = int(filter_id, 16) if filter_id else 0x7E8
        for i in range(min(count, 3)):
            frames.append(CanFrame(
                timestamp=1000.0 + i,
                can_id=fid,
                can_id_hex=f"{fid:03X}",
                is_extended=False,
                dlc=8,
                data=[0x04, 0x41, 0x0C, 0x0C, 0x80, 0x00, 0x00, 0x00],
                raw_ascii=f"{fid:03X} 08 04 41 0C 0C 80 00 00 00",
            ))
        return frames

    def get_capabilities(self) -> AdapterCapabilities:
        """Return capabilities for the mock adapter."""
        return AdapterCapabilities(
            adapter_type="Mock Diagnostic Adapter",
            can_high_speed=True,
            can_medium_speed=True,
            single_wire_can=True,
            iso_9141_kline=True,
            multi_channel_parallel=True,
            bi_directional_tests=True,
            buffer_overflow_risk="Zero",
            max_sample_rate_hz=1000,
            supported_protocols=["All Protocols (Mock)"],
        )

    def get_status(self) -> Dict[str, Any]:
        """Return mock adapter status."""
        return {
            "adapter_type": "Mock Diagnostic Adapter",
            "connected": self.is_connected,
            "host": "localhost",
            "port": 0,
            "protocol": "Mock Protocol",
            "battery_voltage": "14.2V",
            "active_header": self.active_header,
        }
