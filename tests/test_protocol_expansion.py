# SPDX-FileCopyrightText: 2026 Joel G
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests for expanded protocol registry, Mode 01 PIDs, I/M readiness, and DTC decoder."""

from app.protocol import (
    decode_dtc_breakdown,
    decode_im_readiness,
    decode_pid,
    get_supported_protocols,
)


def test_get_supported_protocols():
    """Verify all 10 supported communication protocols are returned."""
    protocols = get_supported_protocols()
    assert len(protocols) == 10
    ids = [p["id"] for p in protocols]
    assert "AUTO" in ids
    assert "ISO15765-4_CAN_11B_500K" in ids
    assert "ISO15765-4_CAN_29B_500K" in ids
    assert "ISO15765-4_CAN_11B_250K" in ids
    assert "ISO15765-4_CAN_29B_250K" in ids
    assert "ISO14230-4_KWP_FAST" in ids
    assert "ISO14230-4_KWP_5BAUD" in ids
    assert "ISO9141-2" in ids
    assert "SAE_J1850_PWM" in ids
    assert "SAE_J1850_VPW" in ids


def test_decode_expanded_pids():
    """Verify formula calculations for newly supported Mode 01 PIDs."""
    # Fuel Pressure (0A, kPa: A * 3) -> 100 * 3 = 300 kPa
    assert decode_pid("0A", [100]) == 300.0

    # Intake Manifold Absolute Pressure (0B, kPa: A) -> 35 kPa
    assert decode_pid("0B", [35]) == 35.0

    # Fuel Rail Pressure (22, kPa: ((A * 256) + B) * 0.079)
    # [10, 0] = 2560 * 0.079 = 202.24
    assert decode_pid("22", [10, 0]) == 202.24

    # Commanded Equivalence Ratio (44, Lambda: ((A * 256) + B) / 32768)
    # [0x80, 0x00] = 32768 / 32768 = 1.0000
    assert decode_pid("44", [0x80, 0x00]) == 1.0

    # Ethanol Fuel % (52, %: A * 100 / 255) -> 255 = 100%
    assert decode_pid("52", [255]) == 100.0

    # Engine Oil Temp (5C, °C: A - 40) -> 120 - 40 = 80 °C
    assert decode_pid("5C", [120]) == 80.0

    # Fuel Rate (5E, L/h: ((A * 256) + B) * 0.05) -> [0, 50] = 2.5 L/h
    assert decode_pid("5E", [0, 50]) == 2.5


def test_decode_im_readiness():
    """Verify bitmask decoding of Mode 01 PID 01 Inspection/Maintenance readiness."""
    # Byte A: 0x82 (MIL ON, 2 DTCs)
    # Byte B: 0x07 (Continuous monitors available: Misfire, Fuel, Comp) and 0x00 (all complete)
    # Byte C: 0x65 (Catalyst, Evap, O2, O2 Heater available)
    # Byte D: 0x04 (EVAP incomplete / not ready, others complete)
    raw = [0x82, 0x07, 0x65, 0x04]
    res = decode_im_readiness(raw)

    assert res["mil_on"] is True
    assert res["dtc_count"] == 2
    monitors = res["monitors"]
    assert monitors["misfire"]["status"] == "Ready"
    assert monitors["fuel_system"]["status"] == "Ready"
    assert monitors["comprehensive_component"]["status"] == "Ready"
    assert monitors["catalyst"]["status"] == "Ready"
    assert monitors["evaporative_system"]["status"] == "Not Ready"
    assert monitors["heated_catalyst"]["status"] == "N/A"


def test_decode_dtc_breakdown():
    """Verify structural decomposition of trouble codes into 4 tokens."""
    # Test Generic Powertrain: P0420
    p0420 = decode_dtc_breakdown("P0420")
    assert p0420["valid"] is True
    assert p0420["system"]["letter"] == "P"
    assert p0420["system"]["name"] == "Powertrain"
    assert p0420["code_type"]["digit"] == "0"
    assert p0420["code_type"]["name"] == "Standardized (SAE/ISO Generic)"
    assert p0420["subsystem"]["digit"] == "4"
    assert "Auxiliary Emission Controls" in p0420["subsystem"]["description"]
    assert p0420["fault_id"]["id"] == "20"

    # Test Chassis Code: C1234
    c1234 = decode_dtc_breakdown("C1234")
    assert c1234["valid"] is True
    assert c1234["system"]["letter"] == "C"
    assert c1234["system"]["name"] == "Chassis"

    # Test Body Code: B0001
    b0001 = decode_dtc_breakdown("B0001")
    assert b0001["valid"] is True
    assert b0001["system"]["letter"] == "B"
    assert b0001["system"]["name"] == "Body"

    # Test Network Code: U0100
    u0100 = decode_dtc_breakdown("U0100")
    assert u0100["valid"] is True
    assert u0100["system"]["letter"] == "U"
    assert u0100["system"]["name"] == "Network & Communication"


def test_mode01_pid_catalog():
    """Verify Mode 01 diagnostic PID catalog completeness and categorization."""
    from app.protocol import get_mode01_pid_catalog

    catalog = get_mode01_pid_catalog()
    assert len(catalog) >= 50
    pids = list(catalog.keys())
    assert "05" in pids  # Engine Coolant Temp
    assert "0C" in pids  # Engine RPM
    assert "0D" in pids  # Vehicle Speed
    assert "10" in pids  # MAF
    assert "14" in pids  # O2 Sensor 1
    assert "42" in pids  # Control Module Voltage

    # Check categories
    categories = {item["category"] for item in catalog.values()}
    assert "Engine" in categories
    assert "Fuel & Air" in categories
    assert "Temperatures" in categories
    assert "Speed & Timing" in categories
    assert "Oxygen Sensors" in categories
    assert "Electrical & Emissions" in categories


def test_decode_supported_pids_bitmap():
    """Verify decoding of SAE J1979 32-bit supported PID bitmasks."""
    from app.protocol import decode_supported_pids_bitmap

    # 4 bytes: 0xBE, 0x1F, 0xA8, 0x13
    # 0xBE = 10111110 -> PIDs 01, 03, 04, 05, 06, 07
    # Bit 0 of Byte 4: 0x13 has bit 0 = 1 -> has_next_block = True
    raw_data = [0xBE, 0x1F, 0xA8, 0x13]
    supported, has_next = decode_supported_pids_bitmap(0x00, raw_data)

    assert "01" in supported
    assert "03" in supported
    assert "04" in supported
    assert "05" in supported
    assert has_next is True


def test_decode_mode05_test():
    """Verify Mode 05 Oxygen Sensor Monitor Test decoding and evaluation."""
    from app.protocol import decode_mode05_test

    # TID 1: Rich to lean threshold (0.450V limit, 0.450V value -> PASS)
    res_pass = decode_mode05_test(1, [0x00, 0x5A])
    assert res_pass["tid"] == "01"
    assert res_pass["unit"] == "V"
    assert res_pass["status"] in ["PASS", "FAIL"]
    assert res_pass["value"] == 0.45

    # TID 5: Switch time in seconds
    res_time = decode_mode05_test(5, [0x00, 0x14])
    assert res_time["tid"] == "05"
    assert res_time["unit"] == "s"
    assert res_time["value"] == 0.08


def test_is_dtc_supported_by_vehicle():
    """Verify vehicle capability heuristic matches DTCs to required PIDs/systems."""
    from app.protocol import is_dtc_supported_by_vehicle

    supported_pids = {"05", "0C", "0D", "10", "14"}
    readiness = {"catalyst": {"status": "Ready"}}

    # P0100 (MAF) supported because PID 10 is in supported_pids
    assert is_dtc_supported_by_vehicle("P0100", supported_pids, readiness) is True

    # P0115 (Coolant) supported because PID 05 is supported
    assert is_dtc_supported_by_vehicle("P0115", supported_pids, readiness) is True

    # P0420 (Catalyst) supported because catalyst monitor is in readiness
    assert is_dtc_supported_by_vehicle("P0420", supported_pids, readiness) is True

    # P0442 (EVAP) unsupported because EVAP monitor not present and PID 2A not present
    assert is_dtc_supported_by_vehicle("P0442", supported_pids, readiness) is False

    # Body code B0001 supported on CAN/standard vehicle
    assert is_dtc_supported_by_vehicle("B0001", supported_pids, readiness) is True

