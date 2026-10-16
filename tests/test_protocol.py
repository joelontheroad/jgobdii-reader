# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests verifying OBD-II protocol formulas, PID decoding, and vehicle mathematics."""

from app.protocol import (
    calculate_vss_frequency,
    decode_dtc_bytes,
    decode_pid,
    parse_dtc_response_payload,
    parse_hex_bytes,
)


def test_parse_hex_bytes():
    """Verify parsing space-delimited and concatenated hex strings."""
    assert parse_hex_bytes("41 0C 1A F8") == [0x41, 0x0C, 0x1A, 0xF8]
    assert parse_hex_bytes("410C1AF8") == [0x41, 0x0C, 0x1A, 0xF8]
    assert parse_hex_bytes("") == []


def test_decode_pid_rpm():
    """Verify Engine RPM decoding formula (((A * 256) + B) / 4)."""
    # 0x0C, 0x80 -> ((12 * 256) + 128) / 4 = 3200 / 4 = 800.0 RPM
    assert decode_pid("0C", [0x0C, 0x80]) == 800.0
    # Boundary: insufficient bytes
    assert decode_pid("0C", [0x0C]) is None


def test_decode_pid_speed():
    """Verify Vehicle Speed decoding in km/h."""
    assert decode_pid("0D", [60]) == 60.0
    assert decode_pid("0D", [0]) == 0.0
    assert decode_pid("0D", []) is None


def test_decode_pid_coolant():
    """Verify Coolant Temperature decoding (A - 40)."""
    # 125 - 40 = 85 °C
    assert decode_pid("05", [125]) == 85.0
    # 40 - 40 = 0 °C
    assert decode_pid("05", [40]) == 0.0
    # 0 - 40 = -40 °C
    assert decode_pid("05", [0]) == -40.0


def test_decode_pid_throttle_and_load():
    """Verify Throttle and Calculated Load percentage decoding."""
    # 128 / 255 * 100 ~ 50.2%
    assert decode_pid("11", [128]) == 50.2
    assert decode_pid("04", [255]) == 100.0


def test_decode_pid_maf():
    """Verify Mass Air Flow decoding (((256*A) + B) / 100)."""
    # 0x01, 0x5E -> (256 + 94) / 100 = 3.5 g/s
    assert decode_pid("10", [0x01, 0x5E]) == 3.5


def test_decode_pid_o2_voltage():
    """Verify Oxygen Sensor Narrowband Voltage decoding (A / 200)."""
    # 90 / 200 = 0.45 V
    assert decode_pid("14", [90]) == 0.45
    # 200 / 200 = 1.0 V
    assert decode_pid("14", [200]) == 1.0


def test_calculate_vss_frequency():
    """Verify derived vehicle speed sensor electrical frequency (Hz)."""
    # 0 km/h -> 0 Hz
    assert calculate_vss_frequency(0.0) == 0.0
    # 60 mph ~ 96.56 km/h. At 4000 pulses/mile, 60 mph * 4000 / 3600 = 66.67 Hz
    hz_60mph = calculate_vss_frequency(96.56, pulses_per_mile=4000)
    assert 66.0 <= hz_60mph <= 67.0


def test_decode_dtc_bytes():
    """Verify SAE J2012 two-byte DTC decoding."""
    # P0420: P (0x00), 0x04, 0x20
    assert decode_dtc_bytes(0x04, 0x20) == "P0420"
    # P0300: P (0x00), 0x03, 0x00
    assert decode_dtc_bytes(0x03, 0x00) == "P0300"
    # C0100: C prefix (0x40)
    assert decode_dtc_bytes(0x41, 0x00) == "C0100"
    # B1234: B prefix (0x80)
    assert decode_dtc_bytes(0x92, 0x34) == "B1234"
    # U0100: U prefix (0xC0)
    assert decode_dtc_bytes(0xC1, 0x00) == "U0100"
    # Zero padding
    assert decode_dtc_bytes(0x00, 0x00) is None


def test_parse_dtc_response_payload():
    """Verify parsing multi-DTC response payload string."""
    # Stored DTCs: P0420 and P0300
    payload = "43 02 04 20 03 00"
    codes = parse_dtc_response_payload(payload)
    assert "P0420" in codes
    assert "P0300" in codes
    assert len(codes) == 2
