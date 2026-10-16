# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""OBD-II protocol encoding, PID decoding, and vehicle telemetry mathematics.

Provides stateless pure functions to parse and scale raw diagnostic byte streams
into engineering units according to SAE J1979 and SAE J2012 standards.
"""

from typing import Any, Dict, List, Optional, Set, Tuple


def parse_hex_bytes(payload_str: str) -> List[int]:
    """Parse a space-separated or concatenated hexadecimal string into integer bytes.

    Args:
        payload_str: Raw hexadecimal string (e.g. "41 0C 1A F8" or "410C1AF8").

    Returns:
        List of integer byte values (0-255).
    """
    clean = payload_str.strip().replace(" ", "").replace("\r", "").replace("\n", "")
    if len(clean) % 2 != 0:
        clean = clean[:-1]
    return [int(clean[i:i + 2], 16) for i in range(0, len(clean), 2)]


SUPPORTED_PROTOCOLS = [
    {
        "id": "AUTO",
        "name": "Automatic Protocol Detection",
        "description": "Auto-scans and negotiates CAN, K-Line, and Legacy OBD-II protocols.",
    },
    {
        "id": "ISO15765-4_CAN_11B_500K",
        "name": "ISO 15765-4 CAN (11-bit ID, 500 kbaud)",
        "description": "Standard high-speed CAN bus on modern US/EU/Asian vehicles (2008+).",
    },
    {
        "id": "ISO15765-4_CAN_29B_500K",
        "name": "ISO 15765-4 CAN (29-bit ID, 500 kbaud)",
        "description": "High-speed extended CAN bus used on commercial & select passenger vehicles.",
    },
    {
        "id": "ISO15765-4_CAN_11B_250K",
        "name": "ISO 15765-4 CAN (11-bit ID, 250 kbaud)",
        "description": "Medium-speed CAN bus used on Ford, GM, and industrial systems.",
    },
    {
        "id": "ISO15765-4_CAN_29B_250K",
        "name": "ISO 15765-4 CAN (29-bit ID, 250 kbaud)",
        "description": "Extended-ID 250 kbaud CAN bus protocol.",
    },
    {
        "id": "ISO14230-4_KWP_FAST",
        "name": "ISO 14230-4 KWP2000 (Fast Init, 10.4 kbaud)",
        "description": "K-Line fast initialization protocol common on 2000-2007 Asian/European vehicles.",
    },
    {
        "id": "ISO14230-4_KWP_5BAUD",
        "name": "ISO 14230-4 KWP2000 (5-baud Init, 10.4 kbaud)",
        "description": "K-Line 5-baud slow initialization protocol.",
    },
    {
        "id": "ISO9141-2",
        "name": "ISO 9141-2 (5-baud Init, 10.4 kbaud)",
        "description": "Classic OBD-II K-Line protocol on pre-2004 Chrysler, European, and Asian vehicles.",
    },
    {
        "id": "SAE_J1850_PWM",
        "name": "SAE J1850 PWM (41.6 kbaud)",
        "description": "Ford pulse-width modulated differential bus (OBD-II Pin 2 & 10).",
    },
    {
        "id": "SAE_J1850_VPW",
        "name": "SAE J1850 VPW (10.4 kbaud)",
        "description": "General Motors variable pulse-width single-wire bus (OBD-II Pin 2).",
    },
]


def get_supported_protocols() -> List[dict]:
    """Retrieve list of all 10 OBD-II and CAN bus communication protocols supported.

    Returns:
        List of dictionaries containing protocol ID, display name, and technical description.
    """
    return list(SUPPORTED_PROTOCOLS)


def decode_pid(pid_hex: str, data: List[int]) -> Optional[float]:
    """Decode scaled engineering values from standard SAE J1979 Mode 01 data bytes.

    Args:
        pid_hex: Two-character hexadecimal PID string (e.g. '0C' for Engine RPM).
        data: List of data payload bytes excluding Mode and PID bytes.

    Returns:
        Decoded floating point value, or None if the payload length is insufficient.
    """
    pid_clean = pid_hex.upper().strip()

    if pid_clean == "0C":  # Engine RPM (2 bytes: ((A * 256) + B) / 4)
        if len(data) < 2:
            return None
        return round(((data[0] * 256.0) + data[1]) / 4.0, 2)

    if pid_clean == "0D":  # Vehicle Speed (km/h) (1 byte: A)
        if not data:
            return None
        return float(data[0])

    if pid_clean == "05":  # Engine Coolant Temperature (°C) (1 byte: A - 40)
        if not data:
            return None
        return float(data[0] - 40)

    if pid_clean == "04":  # Calculated Engine Load (%) (1 byte: A * 100 / 255)
        if not data:
            return None
        return round((data[0] * 100.0) / 255.0, 2)

    if pid_clean == "11":  # Throttle Position (%) (1 byte: A * 100 / 255)
        if not data:
            return None
        return round((data[0] * 100.0) / 255.0, 2)

    if pid_clean == "10":  # Mass Air Flow (MAF) (g/s) (2 bytes: ((256*A) + B) / 100)
        if len(data) < 2:
            return None
        return round(((data[0] * 256.0) + data[1]) / 100.0, 2)

    # Oxygen Sensor Voltages (Bank 1/2, Sensors 1-4: PIDs 0x14 through 0x1B)
    if pid_clean in ("14", "15", "16", "17", "18", "19", "1A", "1B"):
        if not data:
            return None
        # Voltage = A / 200.0 (Range: 0.000V - 1.275V)
        return round(data[0] / 200.0, 3)

    if pid_clean == "0E":  # Timing Advance (degrees: (A / 2) - 64)
        if not data:
            return None
        return round((data[0] / 2.0) - 64.0, 2)

    if pid_clean == "0F":  # Intake Air Temperature (°C: A - 40)
        if not data:
            return None
        return float(data[0] - 40)

    if pid_clean in ("06", "07", "08", "09"):  # Fuel Trims (%: (A - 128) * 100 / 128)
        if not data:
            return None
        return round(((data[0] - 128.0) * 100.0) / 128.0, 2)

    if pid_clean == "0A":  # Fuel Pressure (gauge) (kPa: A * 3)
        if not data:
            return None
        return round(data[0] * 3.0, 2)

    if pid_clean == "0B":  # Intake Manifold Absolute Pressure (MAP) (kPa: A)
        if not data:
            return None
        return float(data[0])

    if pid_clean == "22":  # Fuel Rail Pressure (gauge) (kPa: ((256 * A) + B) * 0.079)
        if len(data) < 2:
            return None
        return round(((data[0] * 256.0) + data[1]) * 0.079, 2)

    if pid_clean == "23":  # Fuel Rail Gauge Pressure (direct inject diesel/gasoline) (kPa: ((256 * A) + B) * 10)
        if len(data) < 2:
            return None
        return round(((data[0] * 256.0) + data[1]) * 10.0, 2)

    if pid_clean == "2F":  # Fuel Tank Level Input (%: A * 100 / 255)
        if not data:
            return None
        return round((data[0] * 100.0) / 255.0, 2)

    if pid_clean == "44":  # Fuel-Air Commanded Equivalence Ratio (lambda: ((256 * A) + B) / 32768)
        if len(data) < 2:
            return None
        return round(((data[0] * 256.0) + data[1]) / 32768.0, 4)

    if pid_clean == "52":  # Ethanol Fuel % (%: A * 100 / 255)
        if not data:
            return None
        return round((data[0] * 100.0) / 255.0, 2)

    if pid_clean == "5B":  # Hybrid Battery Pack Remaining Life (%: A * 100 / 255)
        if not data:
            return None
        return round((data[0] * 100.0) / 255.0, 2)

    if pid_clean == "5C":  # Engine Oil Temperature (°C: A - 40)
        if not data:
            return None
        return float(data[0] - 40)

    if pid_clean == "5E":  # Engine Fuel Rate (L/h: ((256 * A) + B) * 0.05)
        if len(data) < 2:
            return None
        return round(((data[0] * 256.0) + data[1]) * 0.05, 2)

    if pid_clean == "1F":  # Run time since engine start (seconds: (256 * A) + B)
        if len(data) < 2:
            return None
        return float((data[0] * 256) + data[1])

    if pid_clean == "21":  # Distance traveled with MIL on (km: (256 * A) + B)
        if len(data) < 2:
            return None
        return float((data[0] * 256) + data[1])

    if pid_clean == "2C":  # Commanded EGR (%: A * 100 / 255)
        if not data:
            return None
        return round((data[0] * 100.0) / 255.0, 2)

    if pid_clean == "2D":  # EGR Error (%: (A - 128) * 100 / 128)
        if not data:
            return None
        return round(((data[0] - 128.0) * 100.0) / 128.0, 2)

    if pid_clean == "2E":  # Commanded Evaporative Purge (%: A * 100 / 255)
        if not data:
            return None
        return round((data[0] * 100.0) / 255.0, 2)

    if pid_clean == "31":  # Distance traveled since codes cleared (km: (256 * A) + B)
        if len(data) < 2:
            return None
        return float((data[0] * 256) + data[1])

    if pid_clean == "33":  # Absolute Barometric Pressure (kPa: A)
        if not data:
            return None
        return float(data[0])

    if pid_clean in ("3C", "3D", "3E", "3F"):  # Catalyst Temperature (°C: ((256*A)+B)/10 - 40)
        if len(data) < 2:
            return None
        return round((((data[0] * 256.0) + data[1]) / 10.0) - 40.0, 1)

    if pid_clean == "42":  # Control Module Voltage (V: ((256 * A) + B) / 1000)
        if len(data) < 2:
            return None
        return round(((data[0] * 256.0) + data[1]) / 1000.0, 3)

    if pid_clean == "43":  # Absolute Load Value (%: ((256 * A) + B) * 100 / 255)
        if len(data) < 2:
            return None
        return round(((data[0] * 256.0) + data[1]) * 100.0 / 255.0, 2)

    if pid_clean == "45":  # Relative Throttle Position (%: A * 100 / 255)
        if not data:
            return None
        return round((data[0] * 100.0) / 255.0, 2)

    if pid_clean == "46":  # Ambient Air Temperature (°C: A - 40)
        if not data:
            return None
        return float(data[0] - 40)

    if pid_clean == "4C":  # Commanded Throttle Actuator (%: A * 100 / 255)
        if not data:
            return None
        return round((data[0] * 100.0) / 255.0, 2)

    if pid_clean == "5D":  # Fuel Injection Timing (degrees: ((256 * A) + B) / 128 - 210)
        if len(data) < 2:
            return None
        return round((((data[0] * 256.0) + data[1]) / 128.0) - 210.0, 2)

    if pid_clean in ("61", "62"):  # Driver Demand / Actual Torque (%: A - 125)
        if not data:
            return None
        return float(data[0] - 125)

    if pid_clean == "63":  # Engine Reference Torque (Nm: (256 * A) + B)
        if len(data) < 2:
            return None
        return float((data[0] * 256) + data[1])

    return None


def calculate_vss_frequency(speed_kmh: float, pulses_per_mile: int = 4000) -> float:
    """Calculate the derived electrical frequency (in Hertz) for a Vehicle Speed Sensor (VSS).

    Standard vehicles (such as Toyota and GM) use a 4,000 pulses-per-mile reluctor wheel
    speedometer gear circuit.

    Formula:
        Speed (mph) = Speed (km/h) * 0.621371
        Frequency (Hz) = (Speed (mph) * pulses_per_mile) / 3600 seconds

    Args:
        speed_kmh: Vehicle speed in kilometers per hour.
        pulses_per_mile: Reluctor sensor calibration pulses per mile (default: 4000).

    Returns:
        Derived sensor frequency in Hertz (Hz) rounded to 2 decimal places.
    """
    if speed_kmh <= 0.0:
        return 0.0
    speed_mph = speed_kmh * 0.621371
    frequency_hz = (speed_mph * float(pulses_per_mile)) / 3600.0
    return round(frequency_hz, 2)


def decode_dtc_bytes(byte1: int, byte2: int) -> Optional[str]:
    """Decode two raw SAE J2012 hexadecimal bytes into a standard 5-character DTC string.

    Encoding structure:
        Byte 1, Bits 7-6: System Prefix (00 = P, 01 = C, 10 = B, 11 = U)
        Byte 1, Bits 5-4: First Digit (0, 1, 2, or 3)
        Byte 1, Bits 3-0: Second Digit (0-F)
        Byte 2, Bits 7-4: Third Digit (0-F)
        Byte 2, Bits 3-0: Fourth Digit (0-F)

    Args:
        byte1: First byte of the DTC word.
        byte2: Second byte of the DTC word.

    Returns:
        Standard 5-character alphanumeric DTC string (e.g. 'P0420'), or None if padding/zero.
    """
    if byte1 == 0 and byte2 == 0:
        return None

    prefix_map = {0: "P", 1: "C", 2: "B", 3: "U"}
    prefix_code = (byte1 & 0xC0) >> 6
    prefix = prefix_map.get(prefix_code, "P")

    first_digit = (byte1 & 0x30) >> 4
    second_digit = f"{(byte1 & 0x0F):X}"
    third_digit = f"{((byte2 & 0xF0) >> 4):X}"
    fourth_digit = f"{(byte2 & 0x0F):X}"

    return f"{prefix}{first_digit}{second_digit}{third_digit}{fourth_digit}"


def parse_dtc_response_payload(raw_payload: str) -> List[str]:
    """Parse a multi-code SAE J1979 Mode 03, 07, or 0A response payload into DTC strings.

    Args:
        raw_payload: Raw ASCII response line (e.g. '43 02 04 20 03 00' or multi-line frames).

    Returns:
        List of distinct 5-character DTC strings decoded from the payload.
    """
    dtcs = []
    lines = raw_payload.strip().split("\r")
    for line in lines:
        cleaned = line.strip().replace(" ", "")
        if not cleaned:
            continue

        bytes_list = parse_hex_bytes(cleaned)
        # Search for Mode indicator: 0x43 (Stored), 0x47 (Pending), 0x4A (Permanent)
        mode_idx = -1
        for idx, b in enumerate(bytes_list):
            if b in (0x43, 0x47, 0x4A):
                mode_idx = idx
                break

        if mode_idx == -1:
            continue

        # Remaining bytes after mode
        payload = bytes_list[mode_idx + 1:]
        if payload and payload[0] <= 16:  # DTC count byte
            payload = payload[1:]

        for i in range(0, len(payload) - 1, 2):
            code = decode_dtc_bytes(payload[i], payload[i + 1])
            if code and code not in dtcs:
                dtcs.append(code)

    return dtcs


def decode_im_readiness(data: List[int]) -> dict:
    """Decode SAE J1979 Mode 01 PID 01 Inspection/Maintenance (I/M) Readiness status.

    Args:
        data: Four data payload bytes [A, B, C, D] from PID 01 response.

    Returns:
        Structured dictionary indicating MIL lamp status, DTC count, and monitor readiness flags.
    """
    if len(data) < 4:
        return {
            "mil_on": False,
            "dtc_count": 0,
            "monitors": {},
        }

    byte_a, byte_b, byte_c, byte_d = data[0], data[1], data[2], data[3]

    mil_on = bool(byte_a & 0x80)
    dtc_count = byte_a & 0x7F

    def eval_status(available: bool, incomplete: bool) -> str:
        if not available:
            return "N/A"
        return "Not Ready" if incomplete else "Ready"

    monitors = {
        "misfire": {
            "name": "Misfire Monitor",
            "type": "Continuous",
            "available": bool(byte_b & 0x01),
            "status": eval_status(bool(byte_b & 0x01), bool(byte_b & 0x10)),
        },
        "fuel_system": {
            "name": "Fuel System Monitor",
            "type": "Continuous",
            "available": bool(byte_b & 0x02),
            "status": eval_status(bool(byte_b & 0x02), bool(byte_b & 0x20)),
        },
        "comprehensive_component": {
            "name": "Comprehensive Component Monitor",
            "type": "Continuous",
            "available": bool(byte_b & 0x04),
            "status": eval_status(bool(byte_b & 0x04), bool(byte_b & 0x40)),
        },
        "catalyst": {
            "name": "Catalyst Monitor",
            "type": "Non-Continuous",
            "available": bool(byte_c & 0x01),
            "status": eval_status(bool(byte_c & 0x01), bool(byte_d & 0x01)),
        },
        "heated_catalyst": {
            "name": "Heated Catalyst Monitor",
            "type": "Non-Continuous",
            "available": bool(byte_c & 0x02),
            "status": eval_status(bool(byte_c & 0x02), bool(byte_d & 0x02)),
        },
        "evaporative_system": {
            "name": "Evaporative (EVAP) System Monitor",
            "type": "Non-Continuous",
            "available": bool(byte_c & 0x04),
            "status": eval_status(bool(byte_c & 0x04), bool(byte_d & 0x04)),
        },
        "secondary_air": {
            "name": "Secondary Air Injection Monitor",
            "type": "Non-Continuous",
            "available": bool(byte_c & 0x08),
            "status": eval_status(bool(byte_c & 0x08), bool(byte_d & 0x08)),
        },
        "oxygen_sensor": {
            "name": "Oxygen (O2) Sensor Monitor",
            "type": "Non-Continuous",
            "available": bool(byte_c & 0x20),
            "status": eval_status(bool(byte_c & 0x20), bool(byte_d & 0x20)),
        },
        "oxygen_sensor_heater": {
            "name": "Oxygen (O2) Sensor Heater Monitor",
            "type": "Non-Continuous",
            "available": bool(byte_c & 0x40),
            "status": eval_status(bool(byte_c & 0x40), bool(byte_d & 0x40)),
        },
        "egr_system": {
            "name": "EGR / VVT System Monitor",
            "type": "Non-Continuous",
            "available": bool(byte_c & 0x80),
            "status": eval_status(bool(byte_c & 0x80), bool(byte_d & 0x80)),
        },
    }

    return {
        "mil_on": mil_on,
        "dtc_count": dtc_count,
        "monitors": monitors,
    }


def decode_dtc_breakdown(code_str: str) -> dict:
    """Analyze and decompose an OBD-II Diagnostic Trouble Code per SAE J2012 standards.

    Explains the structural hierarchy: System (1st char), Code Type (2nd char),
    Subsystem (3rd char), and Specific Fault Identifier (4th & 5th chars).

    Args:
        code_str: Standard 5-character alphanumeric trouble code (e.g. 'P0420').

    Returns:
        Dictionary containing breakdown of tokens, category definitions, and advice.
    """
    clean = code_str.upper().strip()
    if len(clean) != 5:
        return {
            "code": clean,
            "valid": False,
            "error": "DTC must be exactly 5 alphanumeric characters (e.g. P0420, C1234, U0100).",
        }

    c1, c2, c3, c45 = clean[0], clean[1], clean[2], clean[3:5]

    # System prefix (1st character)
    systems = {
        "P": {
            "name": "Powertrain",
            "description": "Engine, transmission, emissions, fuel delivery, and hybrid drive systems.",
        },
        "C": {
            "name": "Chassis",
            "description": "Mechanical & dynamic vehicle safety systems (ABS, traction control, steering, suspension, TPMS).",
        },
        "B": {
            "name": "Body",
            "description": "Passenger cabin comfort, safety, and electronic equipment (airbags, HVAC, power seats, lighting, locks).",
        },
        "U": {
            "name": "Network & Communication",
            "description": "Serial communication buses (CAN bus, LIN bus, MOST), gateway modules, and ECU-to-ECU data transfers.",
        },
    }
    sys_info = systems.get(c1, {"name": "Unknown System", "description": "Unrecognized category prefix."})

    # Code type (2nd character)
    types = {
        "0": {
            "name": "Standardized (SAE/ISO Generic)",
            "description": "Government-mandated standardized diagnostic code applicable across all OBD-II compliant vehicles.",
        },
        "1": {
            "name": "Manufacturer-Specific (OEM Defined)",
            "description": "Proprietary trouble code established by the vehicle manufacturer for unique components or software logic.",
        },
        "2": {
            "name": "SAE Generic / Manufacturer-Specific",
            "description": "SAE reserved generic powertrain extension, or manufacturer-specific chassis/body/network fault.",
        },
        "3": {
            "name": "SAE Reserved / Manufacturer-Specific",
            "description": "Reserved for future standardization, or manufacturer-specific fault identification.",
        },
    }
    type_info = types.get(c2, {"name": "Extended/Unknown", "description": "Proprietary code type."})

    # Subsystem (3rd character) - primarily for Powertrain P-codes
    powertrain_subsystems = {
        "1": "Fuel and Air Metering (Sensors, Airflow, Fuel Pressure, Injector Pulse)",
        "2": "Fuel and Air Metering - Injector Circuit Malfunction",
        "3": "Ignition System or Engine Cylinder Misfire Detection",
        "4": "Auxiliary Emission Controls (Catalyst, EVAP, Secondary Air, EGR)",
        "5": "Vehicle Speed, Idle Speed Control, and Auxiliary Input Circuits",
        "6": "Computer and Output Auxiliary Circuits (Internal PCM/ECM, Reference Voltage)",
        "7": "Transmission Controls & Gear Shift Solenoids",
        "8": "Transmission Controls (Hydraulic Pressure & Clutch Slippage)",
        "9": "Transmission Auxiliary Systems",
        "0": "Hybrid Propulsion & Auxiliary Systems",
    }

    if c1 == "P":
        subsystem_desc = powertrain_subsystems.get(c3, f"Powertrain Subsystem Category {c3}")
    elif c1 == "C":
        subsystem_desc = f"Chassis Subsystem Category {c3} (Brakes / Steering / Stability Control)"
    elif c1 == "B":
        subsystem_desc = f"Body Subsystem Category {c3} (Restraints / Lighting / Climate)"
    elif c1 == "U":
        subsystem_desc = f"Network Subsystem Category {c3} (CAN Bus Communication / Module Offline)"
    else:
        subsystem_desc = f"Subsystem Category {c3}"

    return {
        "code": clean,
        "valid": True,
        "system": {
            "letter": c1,
            "name": sys_info["name"],
            "description": sys_info["description"],
        },
        "code_type": {
            "digit": c2,
            "name": type_info["name"],
            "description": type_info["description"],
        },
        "subsystem": {
            "digit": c3,
            "description": subsystem_desc,
        },
        "fault_id": {
            "id": c45,
            "description": f"Specific component or fault identification number ({c45}).",
        },
    }


# Comprehensive Mode 01 Standard PIDs Catalog
MODE01_PID_CATALOG: Dict[str, Dict[str, Any]] = {
    "04": {"name": "Calculated Engine Load", "category": "Engine", "unit": "%", "min": 0, "max": 100, "desc": "Current percentage of peak available engine torque."},
    "05": {"name": "Engine Coolant Temperature", "category": "Temperatures", "unit": "°C", "min": -40, "max": 215, "desc": "Temperature of engine cylinder head coolant circuit."},
    "06": {"name": "Short Term Fuel Trim - Bank 1", "category": "Fuel & Air", "unit": "%", "min": -100, "max": 99.2, "desc": "Instantaneous closed-loop fuel correction on Bank 1."},
    "07": {"name": "Long Term Fuel Trim - Bank 1", "category": "Fuel & Air", "unit": "%", "min": -100, "max": 99.2, "desc": "Learned adaptive fuel trim correction on Bank 1."},
    "08": {"name": "Short Term Fuel Trim - Bank 2", "category": "Fuel & Air", "unit": "%", "min": -100, "max": 99.2, "desc": "Instantaneous closed-loop fuel correction on Bank 2."},
    "09": {"name": "Long Term Fuel Trim - Bank 2", "category": "Fuel & Air", "unit": "%", "min": -100, "max": 99.2, "desc": "Learned adaptive fuel trim correction on Bank 2."},
    "0A": {"name": "Fuel Pressure (Gauge)", "category": "Fuel & Air", "unit": "kPa", "min": 0, "max": 765, "desc": "Low-pressure supply line fuel delivery pressure."},
    "0B": {"name": "Intake Manifold Absolute Pressure (MAP)", "category": "Fuel & Air", "unit": "kPa", "min": 0, "max": 255, "desc": "Air pressure inside the engine intake plenum."},
    "0C": {"name": "Engine Speed (RPM)", "category": "Engine", "unit": "rpm", "min": 0, "max": 16383, "desc": "Rotational speed of engine crankshaft."},
    "0D": {"name": "Vehicle Speed (VSS)", "category": "Speed & Timing", "unit": "km/h", "min": 0, "max": 255, "desc": "Vehicle road speed reported by transmission reluctor sensor."},
    "0E": {"name": "Timing Advance", "category": "Speed & Timing", "unit": "°", "min": -64, "max": 63.5, "desc": "Spark ignition timing advance relative to Cylinder 1 TDC."},
    "0F": {"name": "Intake Air Temperature (IAT)", "category": "Temperatures", "unit": "°C", "min": -40, "max": 215, "desc": "Temperature of incoming fresh charge air."},
    "10": {"name": "Mass Air Flow (MAF)", "category": "Fuel & Air", "unit": "g/s", "min": 0, "max": 655.35, "desc": "Mass flow rate of air entering the engine intake."},
    "11": {"name": "Throttle Position", "category": "Engine", "unit": "%", "min": 0, "max": 100, "desc": "Primary throttle plate angular opening percentage."},
    "12": {"name": "Commanded Secondary Air Status", "category": "Electrical & Emissions", "unit": "bit", "min": 0, "max": 255, "desc": "Secondary air injection pump and diverter valve state."},
    "14": {"name": "O2 Sensor 1 Voltage (B1S1)", "category": "Oxygen Sensors", "unit": "V", "min": 0, "max": 1.275, "desc": "Upstream oxygen sensor voltage on Bank 1."},
    "15": {"name": "O2 Sensor 2 Voltage (B1S2)", "category": "Oxygen Sensors", "unit": "V", "min": 0, "max": 1.275, "desc": "Downstream catalyst monitor oxygen sensor voltage on Bank 1."},
    "16": {"name": "O2 Sensor 3 Voltage (B1S3)", "category": "Oxygen Sensors", "unit": "V", "min": 0, "max": 1.275, "desc": "Bank 1 Sensor 3 voltage."},
    "17": {"name": "O2 Sensor 4 Voltage (B1S4)", "category": "Oxygen Sensors", "unit": "V", "min": 0, "max": 1.275, "desc": "Bank 1 Sensor 4 voltage."},
    "18": {"name": "O2 Sensor 5 Voltage (B2S1)", "category": "Oxygen Sensors", "unit": "V", "min": 0, "max": 1.275, "desc": "Upstream oxygen sensor voltage on Bank 2."},
    "19": {"name": "O2 Sensor 6 Voltage (B2S2)", "category": "Oxygen Sensors", "unit": "V", "min": 0, "max": 1.275, "desc": "Downstream catalyst monitor oxygen sensor voltage on Bank 2."},
    "1F": {"name": "Run Time Since Engine Start", "category": "Engine", "unit": "s", "min": 0, "max": 65535, "desc": "Continuous elapsed time since engine ignition start."},
    "21": {"name": "Distance Traveled with MIL On", "category": "Electrical & Emissions", "unit": "km", "min": 0, "max": 65535, "desc": "Odometer distance accumulated while Check Engine Light is active."},
    "22": {"name": "Fuel Rail Pressure (Manifold)", "category": "Fuel & Air", "unit": "kPa", "min": 0, "max": 5177.2, "desc": "Fuel rail injection pressure relative to manifold vacuum."},
    "23": {"name": "Fuel Rail Gauge Pressure (GDI/Diesel)", "category": "Fuel & Air", "unit": "kPa", "min": 0, "max": 655350, "desc": "High-pressure direct injection common rail pressure."},
    "24": {"name": "O2S1 Commanded Equivalence Ratio", "category": "Oxygen Sensors", "unit": "λ", "min": 0, "max": 2.0, "desc": "Wideband air-fuel ratio equivalence (Lambda)."},
    "25": {"name": "O2S2 Commanded Equivalence Ratio", "category": "Oxygen Sensors", "unit": "λ", "min": 0, "max": 2.0, "desc": "Wideband air-fuel ratio equivalence (Lambda)."},
    "2C": {"name": "Commanded EGR", "category": "Electrical & Emissions", "unit": "%", "min": 0, "max": 100, "desc": "Commanded exhaust gas recirculation valve duty cycle."},
    "2D": {"name": "EGR Error", "category": "Electrical & Emissions", "unit": "%", "min": -100, "max": 99.2, "desc": "Deviation between commanded and actual EGR valve position."},
    "2E": {"name": "Commanded Evaporative Purge", "category": "Electrical & Emissions", "unit": "%", "min": 0, "max": 100, "desc": "Evaporative canister purge solenoid duty cycle."},
    "2F": {"name": "Fuel Tank Level Input", "category": "Fuel & Air", "unit": "%", "min": 0, "max": 100, "desc": "Liquid fuel volume remaining in the fuel tank."},
    "31": {"name": "Distance Since Codes Cleared", "category": "Electrical & Emissions", "unit": "km", "min": 0, "max": 65535, "desc": "Distance driven since last diagnostic reset (Mode 04)."},
    "33": {"name": "Absolute Barometric Pressure", "category": "Fuel & Air", "unit": "kPa", "min": 0, "max": 255, "desc": "Ambient atmospheric barometric pressure."},
    "3C": {"name": "Catalyst Temperature (B1S1)", "category": "Temperatures", "unit": "°C", "min": -40, "max": 6513.5, "desc": "Calculated or sensed catalyst temperature on Bank 1 Sensor 1."},
    "3D": {"name": "Catalyst Temperature (B2S1)", "category": "Temperatures", "unit": "°C", "min": -40, "max": 6513.5, "desc": "Calculated or sensed catalyst temperature on Bank 2 Sensor 1."},
    "3E": {"name": "Catalyst Temperature (B1S2)", "category": "Temperatures", "unit": "°C", "min": -40, "max": 6513.5, "desc": "Calculated or sensed catalyst temperature on Bank 1 Sensor 2."},
    "3F": {"name": "Catalyst Temperature (B2S2)", "category": "Temperatures", "unit": "°C", "min": -40, "max": 6513.5, "desc": "Calculated or sensed catalyst temperature on Bank 2 Sensor 2."},
    "42": {"name": "Control Module Voltage", "category": "Electrical & Emissions", "unit": "V", "min": 0, "max": 65.535, "desc": "DC supply battery voltage delivered to vehicle ECM."},
    "43": {"name": "Absolute Load Value", "category": "Engine", "unit": "%", "min": 0, "max": 25700, "desc": "Normalized air mass intake per cylinder stroke."},
    "44": {"name": "Fuel-Air Commanded Ratio", "category": "Fuel & Air", "unit": "λ", "min": 0, "max": 2.0, "desc": "Target air-fuel stoichiometry commanded by ECM."},
    "45": {"name": "Relative Throttle Position", "category": "Engine", "unit": "%", "min": 0, "max": 100, "desc": "Throttle angle above closed idle position stop."},
    "46": {"name": "Ambient Air Temperature", "category": "Temperatures", "unit": "°C", "min": -40, "max": 215, "desc": "Outside ambient atmospheric air temperature."},
    "4C": {"name": "Commanded Throttle Actuator", "category": "Engine", "unit": "%", "min": 0, "max": 100, "desc": "Drive-by-wire electronic throttle motor commanded target."},
    "52": {"name": "Ethanol Fuel Percentage", "category": "Fuel & Air", "unit": "%", "min": 0, "max": 100, "desc": "Ethanol alcohol blend percentage (Flex-Fuel)."},
    "5B": {"name": "Hybrid Battery Remaining Life", "category": "Electrical & Emissions", "unit": "%", "min": 0, "max": 100, "desc": "High-voltage traction battery pack State of Charge (SoC)."},
    "5C": {"name": "Engine Oil Temperature", "category": "Temperatures", "unit": "°C", "min": -40, "max": 210, "desc": "Engine sump lubricating oil temperature."},
    "5D": {"name": "Fuel Injection Timing", "category": "Speed & Timing", "unit": "°", "min": -210, "max": 302, "desc": "Start of fuel injection pulse relative to TDC."},
    "5E": {"name": "Engine Fuel Rate", "category": "Fuel & Air", "unit": "L/h", "min": 0, "max": 3276.75, "desc": "Instantaneous volumetric fuel consumption rate."},
    "61": {"name": "Driver Demand Engine Torque", "category": "Engine", "unit": "%", "min": -125, "max": 130, "desc": "Driver requested torque based on accelerator pedal."},
    "62": {"name": "Actual Engine Torque", "category": "Engine", "unit": "%", "min": -125, "max": 130, "desc": "Actual engine output torque delivered by powertrain."},
    "63": {"name": "Engine Reference Torque", "category": "Engine", "unit": "Nm", "min": 0, "max": 65535, "desc": "Reference baseline maximum engine torque rating."},
}


def get_mode01_pid_catalog() -> Dict[str, Dict[str, Any]]:
    """Retrieve catalog of all standardized SAE J1979 Mode 01 diagnostic parameters.

    Returns:
        Dictionary mapping 2-character hex PID to name, category, unit, min, max, and description.
    """
    return dict(MODE01_PID_CATALOG)


def decode_supported_pids_bitmap(base_pid: int, data: List[int]) -> Tuple[List[str], bool]:
    """Decode 32-bit SAE J1979 support bitmap into supported PID hex strings.

    Args:
        base_pid: Starting PID offset (e.g., 0x00, 0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0).
        data: Four data payload bytes [A, B, C, D] returned from the ECU.

    Returns:
        Tuple containing:
            - List of 2-character uppercase hex strings for supported PIDs in this block.
            - Boolean indicating if the subsequent 32-PID block is supported (bit 0 / 32nd bit).
    """
    if len(data) < 4:
        return [], False

    dword = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]
    supported: List[str] = []

    # Bits 31 down to 1 correspond to base_pid + 1 up to base_pid + 31
    for i in range(31):
        if (dword >> (31 - i)) & 1:
            pid_int = base_pid + i + 1
            supported.append(f"{pid_int:02X}")

    # Bit 0 (LSB) indicates if the next 32 PIDs (base_pid + 0x20) are supported
    next_block_supported = bool(dword & 1)
    return supported, next_block_supported


def decode_mode05_test(tid: int, data: List[int]) -> Dict[str, Any]:
    """Decode legacy SAE J1979 Mode 05 Oxygen Sensor Monitoring test result.

    Args:
        tid: Test Identifier (TID, e.g. 0x01 to 0x0A).
        data: Test data bytes [A, B] from ECU response.

    Returns:
        Dictionary containing test name, scaled value, unit, and status.
    """
    tid_descriptions = {
        0x01: ("Rich to Lean sensor threshold voltage", "V", 0.005),
        0x02: ("Lean to Rich sensor threshold voltage", "V", 0.005),
        0x03: ("Low sensor voltage for switch time calculation", "V", 0.005),
        0x04: ("High sensor voltage for switch time calculation", "V", 0.005),
        0x05: ("Rich to Lean sensor switch time", "s", 0.004),
        0x06: ("Lean to Rich sensor switch time", "s", 0.004),
        0x07: ("Minimum sensor voltage for test cycle", "V", 0.005),
        0x08: ("Maximum sensor voltage for test cycle", "V", 0.005),
        0x09: ("Time between sensor transitions", "s", 0.004),
        0x0A: ("Sensor period", "s", 0.004),
    }

    test_meta = tid_descriptions.get(tid, (f"Oxygen Sensor Test {tid:02X}", "", 1.0))
    desc, unit, scale = test_meta

    val = None
    if len(data) >= 2:
        raw_val = (data[0] << 8) | data[1]
        val = round(raw_val * scale, 3)
    elif len(data) == 1:
        val = round(data[0] * scale, 3)

    return {
        "tid": f"{tid:02X}",
        "name": desc,
        "value": val,
        "unit": unit,
        "status": "PASS" if val is not None else "N/A",
    }


def is_dtc_supported_by_vehicle(
    code: str,
    supported_pids: Optional[Set[str]] = None,
    readiness_monitors: Optional[Dict[str, Any]] = None,
    vehicle_mfg: Optional[str] = None,
) -> bool:
    """Evaluate whether a specific trouble code applies to the connected vehicle.

    Correlates the fault's subsystem and monitored component with the active
    PID 0x00/0x20 support bitmasks and OBD-II readiness monitor availability.

    Args:
        code: 5-character alphanumeric trouble code (e.g. 'P0100').
        supported_pids: Optional set of hex PIDs supported by the connected ECU.
        readiness_monitors: Optional dictionary of readiness monitors from Mode 01 PID 01.
        vehicle_mfg: Optional detected vehicle manufacturer key (e.g. 'toyota').

    Returns:
        True if the code's required sensor/system is supported or standard, False if absent.
    """
    clean = code.upper().strip()
    if not clean or len(clean) < 5:
        return False

    prefix = clean[0]
    digit2 = clean[1]

    # If no specific vehicle bitmask is supplied, all standard codes default to supported
    if supported_pids is None and readiness_monitors is None:
        return True

    pids = supported_pids or set()
    monitors = readiness_monitors or {}

    # Manufacturer-specific codes (e.g. P1xxx, P3xxx, B1xxx, C1xxx, U1xxx)
    if digit2 in ("1", "3"):
        if vehicle_mfg:
            return True
        return False

    def _mon_available(key: str, default_if_none: bool = False) -> bool:
        if readiness_monitors is None:
            return True
        mon = monitors.get(key)
        if not mon:
            return default_if_none
        if "available" in mon:
            return bool(mon["available"])
        if "status" in mon:
            return mon["status"] in ("Ready", "Not Ready")
        return default_if_none

    # Standard Powertrain (P0xxx, P2xxx) component checks
    if prefix == "P":
        # MAF sensor codes (P0100 - P0104)
        if clean.startswith(("P0100", "P0101", "P0102", "P0103", "P0104")):
            return "10" in pids or not pids

        # MAP sensor codes (P0105 - P0109)
        if clean.startswith(("P0105", "P0106", "P0107", "P0108", "P0109")):
            return "0B" in pids or not pids

        # Intake Air Temperature codes (P0110 - P0114)
        if clean.startswith(("P0110", "P0111", "P0112", "P0113", "P0114")):
            return "0F" in pids or not pids

        # Coolant Temperature codes (P0115 - P0119)
        if clean.startswith(("P0115", "P0116", "P0117", "P0118", "P0119")):
            return "05" in pids or not pids

        # Throttle Position codes (P0120 - P0124)
        if clean.startswith(("P0120", "P0121", "P0122", "P0123", "P0124")):
            return "11" in pids or "45" in pids or not pids

        # O2 sensor codes (P0130 - P0167)
        if clean.startswith(("P013", "P014", "P015", "P016")):
            has_o2 = any(p in pids for p in ("14", "15", "16", "17", "18", "19", "1A", "1B", "24", "25"))
            return has_o2 or _mon_available("oxygen_sensor", default_if_none=False)

        # Catalyst efficiency codes (P0420 - P0439)
        if clean.startswith(("P042", "P043")):
            return _mon_available("catalyst", default_if_none=False)

        # EVAP system codes (P0440 - P0457)
        if clean.startswith(("P044", "P045")):
            return "2E" in pids or _mon_available("evaporative_system", default_if_none=False)

        # Secondary air codes (P0410 - P0419)
        if clean.startswith("P041"):
            return "12" in pids or _mon_available("secondary_air", default_if_none=False)

        # EGR codes (P0400 - P0409)
        if clean.startswith("P040"):
            return "2C" in pids or "2D" in pids or _mon_available("egr_system", default_if_none=False)

        # Hybrid powertrain codes (P0A00 - P0AFF)
        if clean.startswith("P0A"):
            return "5B" in pids

        # Generic misfire and fuel trim apply to all combustion engines
        return True

    # Body (B), Chassis (C), and Network (U) standard codes apply on vehicles with relevant ECUs
    return True
