# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests verifying Controller Area Network (CAN) frame parsing and filtering."""

from app.can_bus import CanFilter, parse_can_frame


def test_parse_can_frame_11bit():
    """Verify parsing standard 11-bit CAN frame."""
    line = "7E8 04 41 0C 1A F8"
    frame = parse_can_frame(line)
    assert frame is not None
    assert frame.can_id == 0x7E8
    assert frame.can_id_hex == "7E8"
    assert frame.is_extended is False
    assert frame.dlc == 4
    assert frame.data == [0x41, 0x0C, 0x1A, 0xF8]


def test_parse_can_frame_29bit_extended():
    """Verify parsing extended 29-bit CAN frame."""
    line = "18DA10F1 08 00 00 12 40 00 00 00 00"
    frame = parse_can_frame(line)
    assert frame is not None
    assert frame.can_id == 0x18DA10F1
    assert frame.is_extended is True
    assert frame.dlc == 8
    assert len(frame.data) == 8


def test_parse_can_frame_invalid_lines():
    """Verify non-frame ASCII adapter lines return None."""
    assert parse_can_frame("?") is None
    assert parse_can_frame("OK") is None
    assert parse_can_frame("NO DATA") is None
    assert parse_can_frame("BUFFER FULL") is None
    assert parse_can_frame("") is None


def test_can_filter():
    """Verify hardware/software CAN identifier filtering."""
    frame_7e8 = parse_can_frame("7E8 04 41 0C 1A F8")
    frame_201 = parse_can_frame("201 08 00 00 12 40 00 00 00 00")

    # Unfiltered
    filter_all = CanFilter(None)
    assert filter_all.matches(frame_7e8) is True
    assert filter_all.matches(frame_201) is True

    # Filtered by 7E8
    filter_7e8 = CanFilter("7E8")
    assert filter_7e8.matches(frame_7e8) is True
    assert filter_7e8.matches(frame_201) is False
