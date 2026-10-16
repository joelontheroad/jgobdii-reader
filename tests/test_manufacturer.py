# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests verifying manufacturer enhanced parameters and pinout advisory."""

from app.manufacturer import (
    Manufacturer,
    get_manufacturer_parameters,
    get_pinout_advisor,
)


def test_toyota_parameters():
    """Verify Toyota / Lexus enhanced parameters and decoding formulas."""
    params = get_manufacturer_parameters(Manufacturer.TOYOTA)
    assert len(params) >= 3

    # Test ATF temp (A - 40)
    atf = next(p for p in params if p.id == "toyota_atf_temp")
    assert atf.header == "7E1"
    # 114 - 40 = 74 °C
    assert atf.decode([114]) == 74.0

    # Test Hybrid Battery SOC
    soc = next(p for p in params if p.id == "toyota_hybrid_soc")
    # 128 / 255 * 100 ~ 50.2 %
    assert soc.decode([128]) == 50.2


def test_honda_parameters():
    """Verify Honda / Acura enhanced parameters and decoding formulas."""
    params = get_manufacturer_parameters(Manufacturer.HONDA)
    assert len(params) >= 3

    vtec = next(p for p in params if p.id == "honda_vtec_status")
    assert vtec.decode([1]) == "Engaged"
    assert vtec.decode([0]) == "Disengaged"


def test_gm_parameters():
    """Verify GM enhanced parameters and decoding formulas."""
    params = get_manufacturer_parameters(Manufacturer.GM)
    assert len(params) >= 4

    # Test GM Trans Temp (A - 40)
    trans = next(p for p in params if p.id == "gm_trans_temp")
    assert trans.header == "7E1"
    assert trans.decode([115]) == 75.0

    # Test GM Misfire counter
    cyl1 = next(p for p in params if p.id == "gm_cyl1_misfire")
    assert cyl1.decode([0, 5]) == 5


def test_ford_parameters():
    """Verify Ford enhanced parameters and decoding formulas."""
    params = get_manufacturer_parameters(Manufacturer.FORD)
    assert len(params) >= 3

    # Test Ford CHT (A - 40)
    cht = next(p for p in params if p.id == "ford_cht")
    assert cht.decode([136]) == 96.0

    # Test Ford Turbo Boost (PSI)
    boost = next(p for p in params if p.id == "ford_turbo_boost")
    assert boost.decode([100]) == 14.5


def test_pinout_advisor():
    """Verify OBD-II 16-pin connector advisor reports 16 pins with standard/vendor markings."""
    pins = get_pinout_advisor(Manufacturer.FORD)
    assert len(pins) == 16

    # Verify Pins 6 & 14 are standard CAN
    pin6 = next(p for p in pins if p["pin"] == 6)
    assert pin6["is_standard"] is True
    assert "CAN High" in pin6["name"]

    # Verify Pin 3 is vendor discretionary with Ford MS-CAN note
    pin3 = next(p for p in pins if p["pin"] == 3)
    assert pin3["is_standard"] is False
    assert "MS-CAN" in pin3["manufacturer_note"]
