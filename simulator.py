# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""ELM327 Wi-Fi TCP Socket Simulator.

Emulates an ELM327 Wi-Fi OBD-II diagnostic adapter connected to a vehicle ECU.
Listens on TCP port 35000 (default 127.0.0.1:35000 or 0.0.0.0:35000).

Supports:
- Standard ELM327 AT command set (ATZ, ATE0, ATL0, ATS0, ATH0, ATSP, ATRV, ATSH, ATCRA, etc.)
- Diagnostic Mode 01: Real-time sensor telemetry with dynamic physical simulation
  (Engine RPM, Speed, Coolant Temp, Throttle, MAF, and fluctuating O2 sensor voltages)
- Diagnostic Mode 03: Reading stored Diagnostic Trouble Codes (DTCs)
- Diagnostic Mode 04: Clearing Diagnostic Trouble Codes and reset
- Diagnostic Mode 07: Reading pending DTCs
- Diagnostic Mode 09: Vehicle Identification Number (VIN) lookup
- Diagnostic Mode 21: Enhanced Toyota/Honda PIDs (Hybrid battery, ATF temp)
- Diagnostic Mode 22: Enhanced Ford/GM UDS DIDs (Trans temp, misfires, CHT, boost)
- Raw CAN Bus Monitoring (AT MA, AT CRA)
- Vehicle Profiles: "camry" (2000 Toyota Camry V6, ISO 9141-2) and "can" (ISO 15765-4)
"""

import argparse
import asyncio
import logging
import math
import sys
import time
from typing import Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [ELM327-SIM] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ELM327Simulator")


class VehicleState:
    """Simulates dynamic vehicle physical parameters for sensor telemetry."""

    def __init__(self, profile: str = "camry"):
        self.profile = profile.lower()
        self.start_time = time.time()
        self.dtcs_cleared = False

        if self.profile == "camry":
            self.protocol_num = "3"
            self.protocol_name = "ISO 9141-2"
            self.vin = "4T1BF28K9YU123456"  # Valid 2000 Toyota Camry VIN format
            self.stored_dtcs = ["P0420", "P0300"]  # Cat efficiency & Random misfire
            self.pending_dtcs = ["P0171"]  # System too lean (Bank 1)
        else:
            self.protocol_num = "6"
            self.protocol_name = "ISO 15765-4 (CAN 11/500)"
            self.vin = "1HGCR2F83HA001234"
            self.stored_dtcs = ["P0301", "P0135"]
            self.pending_dtcs = []

    def get_rpm(self) -> float:
        """Simulate dynamic RPM (idle oscillating between 700 and 2400 RPM)."""
        elapsed = time.time() - self.start_time
        base_idle = 750.0
        wave = 500.0 * (1.0 + math.sin(elapsed * 0.3)) + 400.0 * math.sin(elapsed * 0.8)
        return max(650.0, base_idle + wave)

    def get_speed_kmh(self) -> float:
        """Simulate dynamic speed (0 to 95 km/h)."""
        elapsed = time.time() - self.start_time
        speed = 45.0 + 35.0 * math.sin(elapsed * 0.15)
        return max(0.0, speed)

    def get_coolant_temp_c(self) -> float:
        """Simulate engine warm-up up to 88°C."""
        elapsed = time.time() - self.start_time
        return min(88.0, 35.0 + (elapsed * 1.5))

    def get_throttle_pct(self) -> float:
        """Simulate throttle position (14% idle to 55%)."""
        elapsed = time.time() - self.start_time
        return 15.0 + 15.0 * (1.0 + math.sin(elapsed * 0.3))

    def get_engine_load_pct(self) -> float:
        """Simulate engine load percentage."""
        elapsed = time.time() - self.start_time
        return 25.0 + 20.0 * (1.0 + math.sin(elapsed * 0.25))

    def get_maf_gps(self) -> float:
        """Mass Air Flow in grams/second."""
        rpm = self.get_rpm()
        return (rpm / 750.0) * 3.8

    def get_o2_voltage(self) -> float:
        """
        Simulate oscillating O2 narrowband oxygen sensor voltage (0.1V lean to 0.9V rich).
        Switches at ~1.2 Hz, perfect for testing oscilloscope graphing!
        """
        elapsed = time.time() - self.start_time
        return 0.45 + 0.40 * math.sin(elapsed * 2.5 * math.pi)

    def get_battery_voltage(self) -> str:
        """Battery voltage in volts."""
        elapsed = time.time() - self.start_time
        v = 13.9 + 0.15 * math.sin(elapsed * 0.5)
        return f"{v:.1f}V"


def encode_dtc_to_hex(dtc: str) -> Tuple[int, int]:
    """Encodes a standard 5-character DTC (e.g., 'P0420') into 2 hex bytes per SAE J2012."""
    type_char = dtc[0].upper()
    prefix_map = {"P": 0x00, "C": 0x40, "B": 0x80, "U": 0xC0}
    prefix_val = prefix_map.get(type_char, 0x00)

    d1 = int(dtc[1], 16)
    d2 = int(dtc[2], 16)
    d3 = int(dtc[3], 16)
    d4 = int(dtc[4], 16)

    byte1 = prefix_val | (d1 << 4) | d2
    byte2 = (d3 << 4) | d4
    return byte1, byte2


class ELM327ClientSession:
    """Handles an individual client connection to the ELM327 Wi-Fi adapter."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        vehicle: VehicleState,
    ):
        self.reader = reader
        self.writer = writer
        self.vehicle = vehicle

        # ELM327 configuration registers
        self.echo: bool = True
        self.linefeeds: bool = True
        self.spaces: bool = True
        self.headers: bool = False
        self.protocol: str = vehicle.protocol_num
        self.header: str = "7DF"
        self.filter_id: Optional[str] = None

    async def run(self) -> None:
        peer = self.writer.get_extra_info("peername")
        logger.info(f"Client connected from {peer}")

        # Send initial ELM327 prompt on connection
        await self.send_prompt()

        buffer = ""
        try:
            while not self.reader.at_eof():
                chunk = await self.reader.read(256)
                if not chunk:
                    break
                text = chunk.decode("ascii", errors="ignore")
                buffer += text

                while "\r" in buffer:
                    cmd_line, buffer = buffer.split("\r", 1)
                    cmd = cmd_line.strip()
                    if cmd:
                        logger.info(f"Received command: '{cmd}'")
                        response = self.process_command(cmd)
                        await self.send_response(cmd, response)
                    else:
                        await self.send_prompt()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error handling client {peer}: {e}")
        finally:
            logger.info(f"Client {peer} disconnected")
            self.writer.close()
            await self.writer.wait_closed()

    def process_command(self, cmd: str) -> str:
        """Processes incoming ASCII commands and returns the simulated response."""
        normalized = cmd.upper().replace(" ", "")

        # 1. AT Commands
        if normalized.startswith("AT"):
            return self.handle_at_command(normalized)

        # 2. Mode 01: Current Telemetry Data
        if normalized.startswith("01"):
            return self.handle_mode_01(normalized)

        # 3. Mode 03: Request Stored DTCs
        if normalized == "03":
            return self.handle_mode_03()

        # 4. Mode 04: Clear DTCs
        if normalized == "04":
            return self.handle_mode_04()

        # 5. Mode 07: Request Pending DTCs
        if normalized == "07":
            return self.handle_mode_07()

        # 6. Mode 09: Vehicle Information (VIN)
        if normalized.startswith("09"):
            return self.handle_mode_09(normalized)

        # 7. Mode 21: Enhanced Toyota / Honda Data
        if normalized.startswith("21"):
            return self.handle_mode_21(normalized)

        # 8. Mode 22: Enhanced Ford / GM UDS Data
        if normalized.startswith("22"):
            return self.handle_mode_22(normalized)

        return "?"

    def handle_at_command(self, cmd: str) -> str:
        """Handles ELM327 AT configuration commands."""
        if cmd in ("ATZ", "ATWS"):
            # Reset / Warm start
            return "\r\nELM327 v1.5\r\n"
        if cmd == "ATI":
            return "ELM327 v1.5"
        if cmd == "ATE0":
            self.echo = False
            return "OK"
        if cmd == "ATE1":
            self.echo = True
            return "OK"
        if cmd == "ATL0":
            self.linefeeds = False
            return "OK"
        if cmd == "ATL1":
            self.linefeeds = True
            return "OK"
        if cmd == "ATS0":
            self.spaces = False
            return "OK"
        if cmd == "ATS1":
            self.spaces = True
            return "OK"
        if cmd == "ATH0":
            self.headers = False
            return "OK"
        if cmd == "ATH1":
            self.headers = True
            return "OK"
        if cmd == "ATRV":
            return self.vehicle.get_battery_voltage()
        if cmd.startswith("ATSP"):
            prot = cmd[4:]
            if prot in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A"):
                self.protocol = prot if prot != "0" else self.vehicle.protocol_num
                return "OK"
            return "?"
        if cmd == "ATDP":
            return self.vehicle.protocol_name
        if cmd == "ATDPN":
            return self.protocol
        if cmd.startswith("ATSH"):
            self.header = cmd[4:]
            return "OK"
        if cmd.startswith("ATCRA"):
            self.filter_id = cmd[5:] if len(cmd) > 5 else None
            return "OK"
        if cmd == "ATMA":
            f_id = self.filter_id or "201"
            return f"{f_id} 08 00 00 12 40 00 00 00 00\r7E8 04 41 0C 1A F8"
        if cmd in ("ATCAF0", "ATCAF1", "ATCFC0", "ATCFC1"):
            return "OK"
        if cmd.startswith("ATCF") or cmd.startswith("ATCM"):
            return "OK"
        if cmd == "AT":
            return "OK"
        return "OK"

    def handle_mode_21(self, cmd: str) -> str:
        """Handles Mode 21 enhanced queries (Toyota/Honda)."""
        pid = cmd[2:]
        if pid == "C3":
            return self.format_hex_response("61 C3 0F 12 0F 14 0F 12 0F 10")
        if pid == "82":
            return self.format_hex_response("61 82 70")
        if pid == "01":
            return self.format_hex_response("61 01 08 20 54 28")
        return self.format_hex_response(f"61 {pid} 00 00")

    def handle_mode_22(self, cmd: str) -> str:
        """Handles Mode 22 enhanced queries (Ford/GM/UDS)."""
        pid = cmd[2:]
        if pid == "1940":
            return self.format_hex_response("62 19 40 73")
        if pid == "1624":
            return self.format_hex_response("62 16 24 5C")
        if pid == "0462":
            return self.format_hex_response("62 04 62 0F")
        if pid.startswith("120"):
            return self.format_hex_response(f"62 {pid} 00 00")
        if pid == "0052":
            return self.format_hex_response("62 00 52 0F")
        if pid == "11A6":
            return self.format_hex_response("62 11 A6 00")
        if pid == "1101":
            return self.format_hex_response("62 11 01 01")
        return self.format_hex_response(f"62 {pid} 00")

    def handle_mode_01(self, cmd: str) -> str:
        """Handles Mode 01 Parameter ID (PID) telemetry queries."""
        if len(cmd) < 4:
            return "NO DATA"
        pid = cmd[2:4]

        # PID 00: Supported PIDs [01-20] (Bitmap)
        if pid == "00":
            # Supported: 01, 03, 04, 05, 06, 07, 0C, 0D, 0E, 0F, 10, 11, 13, 14, 15
            return self.format_hex_response("41 00 BE 3E B8 11")

        # PID 01: Monitor status since DTCs cleared
        if pid == "01":
            # MIL on/off, DTC count
            dtc_count = len(self.vehicle.stored_dtcs) if not self.vehicle.dtcs_cleared else 0
            mil_byte = 0x80 | dtc_count if dtc_count > 0 else 0x00
            return self.format_hex_response(f"41 01 {mil_byte:02X} 07 E5 00")

        # PID 04: Calculated Engine Load (%)
        if pid == "04":
            load_pct = self.vehicle.get_engine_load_pct()
            raw_a = int((load_pct * 255.0) / 100.0)
            return self.format_hex_response(f"41 04 {raw_a:02X}")

        # PID 05: Engine Coolant Temperature (°C)
        if pid == "05":
            temp_c = self.vehicle.get_coolant_temp_c()
            raw_a = int(temp_c + 40.0)
            return self.format_hex_response(f"41 05 {raw_a:02X}")

        # PID 0C: Engine RPM
        if pid == "0C":
            rpm = self.vehicle.get_rpm()
            raw = int(rpm * 4.0)
            raw_a = (raw >> 8) & 0xFF
            raw_b = raw & 0xFF
            return self.format_hex_response(f"41 0C {raw_a:02X} {raw_b:02X}")

        # PID 0D: Vehicle Speed (km/h)
        if pid == "0D":
            speed_kmh = int(self.vehicle.get_speed_kmh())
            return self.format_hex_response(f"41 0D {speed_kmh:02X}")

        # PID 10: Mass Air Flow (MAF) (g/s)
        if pid == "10":
            maf = self.vehicle.get_maf_gps()
            raw = int(maf * 100.0)
            raw_a = (raw >> 8) & 0xFF
            raw_b = raw & 0xFF
            return self.format_hex_response(f"41 10 {raw_a:02X} {raw_b:02X}")

        # PID 11: Throttle Position (%)
        if pid == "11":
            throttle = self.vehicle.get_throttle_pct()
            raw_a = int((throttle * 255.0) / 100.0)
            return self.format_hex_response(f"41 11 {raw_a:02X}")

        # PID 14: Oxygen Sensor 1 Bank 1 Voltage (V) & Short Term Fuel Trim
        if pid == "14":
            v = self.vehicle.get_o2_voltage()
            raw_a = min(255, max(0, int(v / 0.005)))
            raw_b = 0x80  # 0% fuel trim
            return self.format_hex_response(f"41 14 {raw_a:02X} {raw_b:02X}")

        # PID 20: Supported PIDs [21-40]
        if pid == "20":
            return self.format_hex_response("41 20 80 00 00 01")

        return "NO DATA"

    def handle_mode_03(self) -> str:
        """Handles Mode 03 request for confirmed stored DTCs."""
        if self.vehicle.dtcs_cleared or not self.vehicle.stored_dtcs:
            return self.format_hex_response("43 00")

        bytes_list = []
        for dtc in self.vehicle.stored_dtcs:
            b1, b2 = encode_dtc_to_hex(dtc)
            bytes_list.append(f"{b1:02X} {b2:02X}")

        count_byte = f"{len(self.vehicle.stored_dtcs):02X}"
        payload = f"43 {count_byte} " + " ".join(bytes_list)
        return self.format_hex_response(payload)

    def handle_mode_04(self) -> str:
        """Handles Mode 04 request to clear all emissions diagnostic data & DTCs."""
        self.vehicle.dtcs_cleared = True
        self.vehicle.stored_dtcs.clear()
        self.vehicle.pending_dtcs.clear()
        return self.format_hex_response("44")

    def handle_mode_07(self) -> str:
        """Handles Mode 07 request for pending DTCs."""
        if self.vehicle.dtcs_cleared or not self.vehicle.pending_dtcs:
            return self.format_hex_response("47 00")

        bytes_list = []
        for dtc in self.vehicle.pending_dtcs:
            b1, b2 = encode_dtc_to_hex(dtc)
            bytes_list.append(f"{b1:02X} {b2:02X}")

        count_byte = f"{len(self.vehicle.pending_dtcs):02X}"
        payload = f"47 {count_byte} " + " ".join(bytes_list)
        return self.format_hex_response(payload)

    def handle_mode_09(self, cmd: str) -> str:
        """Handles Mode 09 vehicle info (VIN)."""
        if len(cmd) < 4:
            return "NO DATA"
        infotype = cmd[2:4]

        # InfoType 02: VIN
        if infotype == "02":
            vin_ascii = self.vehicle.vin
            vin_hex = " ".join(f"{ord(c):02X}" for c in vin_ascii)
            # Response header 49 02 01 <bytes>
            return self.format_hex_response(f"49 02 01 {vin_hex}")

        return "NO DATA"

    def format_hex_response(self, text: str) -> str:
        """Applies space filtering according to ATS0 / ATS1."""
        if not self.spaces:
            return text.replace(" ", "")
        return text

    async def send_response(self, original_cmd: str, response: str) -> None:
        """Formats and transmits response followed by the '>' prompt."""
        output = ""
        if self.echo:
            output += original_cmd + "\r"
        if response:
            output += response + "\r"
        if self.linefeeds:
            output = output.replace("\r", "\r\n")

        output += ">"
        self.writer.write(output.encode("ascii"))
        await self.writer.drain()

    async def send_prompt(self) -> None:
        """Sends lone prompt character."""
        self.writer.write(b">")
        await self.writer.drain()


async def start_simulator_server(host: str, port: int, profile: str) -> None:
    vehicle = VehicleState(profile=profile)
    server = await asyncio.start_server(
        lambda r, w: ELM327ClientSession(r, w, vehicle).run(),
        host=host,
        port=port,
        reuse_address=True,
    )
    logger.info(f"ELM327 Wi-Fi Simulator active on {host}:{port}")
    logger.info(f"Loaded Vehicle Profile: '{profile.upper()}' (Protocol: {vehicle.protocol_name})")
    logger.info(f"Simulating VIN: {vehicle.vin} | Injected Stored DTCs: {vehicle.stored_dtcs}")
    logger.info("Ready for client connections from OBD-II software...")

    async with server:
        await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="ELM327 Wi-Fi OBD-II TCP Simulator")
    parser.add_argument("--host", default="127.0.0.1", help="Listening IP (default: 127.0.0.1; use 0.0.0.0 or 192.168.0.10 for network exposure)")
    parser.add_argument("--port", type=int, default=35000, help="Listening TCP port (default: 35000)")
    parser.add_argument("--profile", default="camry", choices=["camry", "can"], help="Vehicle profile: camry (ISO 9141-2) or can (ISO 15765-4)")
    args = parser.parse_args()

    try:
        asyncio.run(start_simulator_server(args.host, args.port, args.profile))
    except KeyboardInterrupt:
        logger.info("Simulator terminated by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
