# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Asynchronous ELM327 Wi-Fi TCP diagnostic adapter implementation.

Manages socket connections to ELM327 hardware dongles (typically 192.168.0.10:35000),
command sequencing, prompt parsing, and timeout handling.
"""

import asyncio
from typing import Any, Dict, List, Optional, Set

from app.adapters.base import AdapterCapabilities, DiagnosticAdapterBase
from app.can_bus import CanFrame, parse_can_frame
from app.protocol import parse_dtc_response_payload, parse_hex_bytes


class AsyncELM327Adapter(DiagnosticAdapterBase):
    """Asynchronous TCP socket client for ELM327 Wi-Fi OBD-II adapters."""

    def __init__(
        self,
        host: str = "192.168.0.10",
        port: int = 35000,
        timeout: float = 2.5,
        protocol_cmd: str = "ATSP0",
    ):
        """Initialize adapter with network address and timeout parameters.

        Args:
            host: IP address of the ELM327 Wi-Fi adapter (default: 192.168.0.10).
            port: TCP listening port of the adapter (default: 35000).
            timeout: Socket command read timeout in seconds.
            protocol_cmd: AT protocol select command (e.g. 'ATSP0', 'ATSP3', 'ATSP6').
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.protocol_cmd = protocol_cmd

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.is_connected: bool = False
        self.detected_protocol: str = "Unknown"
        self.battery_voltage: str = "Unknown"
        self.active_header: str = "7DF"

    async def connect(self) -> bool:
        """Establish TCP connection and execute ELM327 AT initialization sequence.

        Returns:
            True if socket connected and AT handshake completed, False otherwise.
        """
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
            # Drain initial banner or prompt
            await self._read_until_prompt(timeout=1.5)

            # AT handshake sequence
            await self._send_command("ATZ")   # Warm reset
            await self._send_command("ATE0")  # Echo off
            await self._send_command("ATL0")  # Linefeeds off
            await self._send_command("ATS0")  # Spaces off
            await self._send_command("ATH0")  # Headers off
            await self._send_command(self.protocol_cmd)  # Set protocol

            voltage_resp = await self._send_command("ATRV")
            self.battery_voltage = voltage_resp.strip() if voltage_resp else "12.0V"

            protocol_resp = await self._send_command("ATDP")
            self.detected_protocol = protocol_resp.strip() if protocol_resp else "ISO 15765-4"

            self.is_connected = True
            return True
        except (OSError, asyncio.TimeoutError):
            await self.disconnect()
            return False

    async def disconnect(self) -> None:
        """Close socket connection and reset state."""
        self.is_connected = False
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:  # noqa: S110 - Socket teardown errors during disconnect are safely discarded
                pass
        self.reader = None
        self.writer = None

    async def _read_until_prompt(self, timeout: Optional[float] = None) -> str:
        """Read incoming ASCII bytes from socket until the prompt '>' appears."""
        if not self.reader:
            return ""
        eff_timeout = timeout or self.timeout
        buffer = ""
        start = asyncio.get_event_loop().time()

        while True:
            remaining = eff_timeout - (asyncio.get_event_loop().time() - start)
            if remaining <= 0:
                break
            try:
                chunk = await asyncio.wait_for(self.reader.read(128), timeout=remaining)
                if not chunk:
                    break
                text = chunk.decode("ascii", errors="ignore")
                buffer += text
                if ">" in buffer:
                    buffer = buffer.replace(">", "").strip()
                    break
            except (asyncio.TimeoutError, OSError):
                break

        return buffer

    async def _send_command(self, cmd: str) -> str:
        """Send an ASCII command terminated by carriage return and read response."""
        if not self.writer or not self.reader:
            return ""
        try:
            self.writer.write(f"{cmd.strip()}\r".encode("ascii"))
            await self.writer.drain()
            return await self._read_until_prompt()
        except OSError:
            self.is_connected = False
            return ""

    async def query_pid(self, mode_hex: str, pid_hex: str) -> Optional[List[int]]:
        """Query standard diagnostic mode and PID."""
        cmd = f"{mode_hex.strip()}{pid_hex.strip()}"
        raw_response = await self._send_command(cmd)
        clean = raw_response.replace(" ", "").replace("\r", "").replace("\n", "")

        # Mode 01 response starts with 41 + PID
        expected_prefix = f"4{mode_hex.strip()[-1]}{pid_hex.strip().upper()}"
        idx = clean.find(expected_prefix)
        if idx == -1:
            return None

        payload_hex = clean[idx + len(expected_prefix):]
        return parse_hex_bytes(payload_hex)

    async def query_dtcs(self, mode_hex: str = "03") -> List[str]:
        """Query diagnostic trouble codes."""
        raw_resp = await self._send_command(mode_hex)
        return parse_dtc_response_payload(raw_resp)

    async def clear_dtcs(self) -> bool:
        """Issue Mode 04 clear diagnostic information."""
        resp = await self._send_command("04")
        return "44" in resp or "OK" in resp

    async def query_enhanced(
        self,
        header: str,
        service_mode: str,
        pid_hex: str,
    ) -> Optional[List[int]]:
        """Query manufacturer-specific physical ECU address."""
        if self.active_header != header.upper():
            await self._send_command(f"ATSH{header.strip()}")
            self.active_header = header.upper()

        cmd = f"{service_mode.strip()}{pid_hex.strip()}"
        raw_resp = await self._send_command(cmd)
        clean = raw_resp.replace(" ", "").replace("\r", "").replace("\n", "")

        # Look for echo response byte (e.g. 61 for Mode 21, 62 for Mode 22)
        resp_mode = f"6{service_mode.strip()[-1]}"
        target = f"{resp_mode}{pid_hex.strip().upper()}"
        idx = clean.find(target)
        if idx == -1:
            return None

        payload_hex = clean[idx + len(target):]
        return parse_hex_bytes(payload_hex)

    async def capture_can_frames(
        self,
        count: int = 10,
        filter_id: Optional[str] = None,
        timeout: float = 2.0,
    ) -> List[CanFrame]:
        """Capture raw CAN frames using AT MA / AT CRA with anti-overflow protections."""
        frames: List[CanFrame] = []
        if filter_id:
            await self._send_command(f"ATCRA{filter_id.strip()}")
        else:
            await self._send_command("ATCRA")

        await self._send_command("ATH1")  # Headers on to capture ID
        await self._send_command("ATS1")  # Spaces on

        # Trigger monitor
        if not self.writer or not self.reader:
            return []

        try:
            self.writer.write(b"ATMA\r")
            await self.writer.drain()

            start_t = asyncio.get_event_loop().time()
            buf = ""

            while len(frames) < count and (asyncio.get_event_loop().time() - start_t) < timeout:
                try:
                    chunk = await asyncio.wait_for(self.reader.read(256), timeout=0.5)
                    if not chunk:
                        break
                    buf += chunk.decode("ascii", errors="ignore")
                    while "\r" in buf:
                        line, buf = buf.split("\r", 1)
                        frame = parse_can_frame(line)
                        if frame:
                            frames.append(frame)
                            if len(frames) >= count:
                                break
                except asyncio.TimeoutError:
                    break

            # Send interrupt character to exit ATMA loop
            self.writer.write(b" ")
            await self.writer.drain()
            await self._read_until_prompt(timeout=0.5)
            await self._send_command("ATH0")  # Restore headers off
        except OSError:
            pass

        return frames

    def get_capabilities(self) -> AdapterCapabilities:
        """Return ELM327 hardware capabilities."""
        return AdapterCapabilities(
            adapter_type="ELM327 Wi-Fi",
            can_high_speed=True,
            can_medium_speed=False,  # Requires physical switch for Pins 3/11
            single_wire_can=False,   # Requires SWCAN transceiver
            iso_9141_kline=True,
            multi_channel_parallel=False,
            bi_directional_tests=False,
            buffer_overflow_risk="High on unrestricted AT MA (filter with AT CRA)",
            max_sample_rate_hz=25,
            supported_protocols=[
                "ISO 15765-4 CAN (11-bit / 29-bit)",
                "ISO 9141-2 (K-Line)",
                "ISO 14230-4 (KWP2000)",
                "SAE J1850 VPW/PWM",
                "SAE J1939 (Marine)",
            ],
        )

    def get_status(self) -> Dict[str, Any]:
        """Return connection health and telemetry status."""
        return {
            "adapter_type": "ELM327 Wi-Fi",
            "connected": self.is_connected,
            "host": self.host,
            "port": self.port,
            "protocol": self.detected_protocol,
            "battery_voltage": self.battery_voltage,
            "active_header": self.active_header,
        }

    async def query_supported_pids(self) -> Set[str]:
        """Query Mode 01 PID 0x00 and subsequent blocks to discover vehicle-supported PIDs."""
        from app.protocol import decode_supported_pids_bitmap
        if not self.is_connected:
            return set()

        supported: Set[str] = set()
        base = 0x00
        while base <= 0xC0:
            bytes_resp = await self.query_pid("01", f"{base:02X}")
            if not bytes_resp or len(bytes_resp) < 4:
                break
            pids, has_next = decode_supported_pids_bitmap(base, bytes_resp)
            supported.update(pids)
            if not has_next:
                break
            base += 0x20

        return supported

    async def query_mode05(self, tid: int = 1) -> Optional[Dict[str, Any]]:
        """Query legacy Mode 05 Oxygen Sensor Monitoring test result."""
        from app.protocol import decode_mode05_test
        if not self.is_connected:
            return None

        raw = await self._send_command(f"05{tid:02X}")
        bytes_list = parse_hex_bytes(raw)
        # Look for Mode 05 response byte 0x45
        for i, b in enumerate(bytes_list):
            if b == 0x45 and len(bytes_list) > i + 1:
                return decode_mode05_test(tid, bytes_list[i + 1:])

        return None

    async def query_vin(self) -> Dict[str, str]:
        """Query Mode 09 vehicle identification, calibration ID, and CVN via ELM327."""
        if not self.is_connected:
            return {"vin": "", "calibration_id": "", "cvn": ""}

        # Mode 09 PID 02: VIN
        raw_vin = await self._send_command("0902")
        clean_vin_resp = raw_vin.replace(" ", "").replace("\r", "").replace("\n", "")
        extracted_vin = ""

        # Scan for ASCII alphanumeric characters (0-9, A-Z) in hexadecimal byte stream
        if "4902" in clean_vin_resp:
            import re
            hex_pairs = re.findall(r"[0-9A-Fa-f]{2}", clean_vin_resp)
            chars = []
            for h in hex_pairs:
                val = int(h, 16)
                if (0x30 <= val <= 0x39) or (0x41 <= val <= 0x5A):
                    chars.append(chr(val))
            candidate = "".join(chars)
            # Standard VIN is exactly 17 characters
            if len(candidate) >= 17:
                extracted_vin = candidate[-17:]
            elif len(candidate) >= 11:
                extracted_vin = candidate

        # Mode 09 PID 04: Calibration ID
        raw_cal = await self._send_command("0904")
        cal_id = raw_cal.strip().replace("\r", "").replace("\n", "") if raw_cal else ""
        if "4904" in cal_id.replace(" ", ""):
            cal_id = cal_id.replace(" ", "")

        # Mode 09 PID 06: CVN
        raw_cvn = await self._send_command("0906")
        cvn = raw_cvn.strip().replace("\r", "").replace("\n", "") if raw_cvn else ""

        return {
            "vin": extracted_vin,
            "calibration_id": cal_id,
            "cvn": cvn,
        }

    async def check_vehicle_connected(self) -> bool:
        """Check if vehicle ECU is actively responding to Mode 01 queries.

        Sends Mode 01 PID 00. If the vehicle ignition is OFF or ECU is not responding,
        ELM327 returns 'UNABLE TO CONNECT', 'BUS INIT: ERROR', or 'NO DATA'.

        Returns:
            True if vehicle ECU answers with 41 00, False if disconnected or offline.
        """
        if not self.is_connected:
            return False
        resp = await self._send_command("0100")
        clean = resp.replace(" ", "").upper()
        if any(err in clean for err in ["UNABLE", "BUSINIT", "ERROR", "NODATA", "STOPPED", "TIMEOUT"]):
            return False
        return "4100" in clean or "41 00" in resp

