# SPDX-FileCopyrightText: 2026 Joel G
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests for Linux sysfs hardware and cable detection routines."""

from pathlib import Path
from unittest.mock import patch

from app.hardware import (
    detect_can_hardware,
    scan_network_can_interfaces,
    scan_usb_can_cables,
)


def test_scan_network_can_interfaces_mocked(tmp_path: Path):
    """Verify that scan_network_can_interfaces parses sysfs net devices."""
    can0_dir = tmp_path / "can0"
    can0_dir.mkdir()
    (can0_dir / "type").write_text("280\n", encoding="utf-8")

    eth0_dir = tmp_path / "eth0"
    eth0_dir.mkdir()
    (eth0_dir / "type").write_text("1\n", encoding="utf-8")

    with patch("sys.platform", "linux"):
        interfaces = scan_network_can_interfaces(base_path=tmp_path)
        assert "can0" in interfaces
        assert "eth0" not in interfaces


def test_scan_usb_can_cables_mocked(tmp_path: Path):
    """Verify detection of known physical USB-to-CAN controllers via sysfs descriptors."""
    canable_dir = tmp_path / "1-2"
    canable_dir.mkdir()
    (canable_dir / "idVendor").write_text("1d50\n", encoding="utf-8")
    (canable_dir / "idProduct").write_text("606f\n", encoding="utf-8")

    mouse_dir = tmp_path / "1-3"
    mouse_dir.mkdir()
    (mouse_dir / "idVendor").write_text("046d\n", encoding="utf-8")
    (mouse_dir / "idProduct").write_text("c077\n", encoding="utf-8")

    with patch("sys.platform", "linux"):
        cables = scan_usb_can_cables(base_path=tmp_path)
        assert len(cables) == 1
        assert "CANable" in cables[0]["name"]
        assert cables[0]["vendor_id"] == "1d50"
        assert cables[0]["product_id"] == "606f"


def test_detect_can_hardware():
    """Verify that detect_can_hardware aggregates cable and interface state."""
    with patch("app.hardware.scan_network_can_interfaces", return_value=["can0"]), \
         patch("app.hardware.scan_usb_can_cables", return_value=[{"name": "CANable"}]):
        res = detect_can_hardware()
        assert res["socketcan_supported"] is True
        assert res["is_cable_connected"] is True
        assert res["is_ready"] is True
        assert "can0" in res["interfaces"]
