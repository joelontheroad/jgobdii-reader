# SPDX-FileCopyrightText: 2026 Joel G
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Hardware discovery and interface detection for Controller Area Network (CAN) adapters.

Scans the Linux sysfs hierarchy (/sys/class/net and /sys/bus/usb/devices) to discover
active SocketCAN network devices (can0, vcan0, slcan0) and connected physical USB-to-CAN
hardware controllers (CANable, Candlelight, PEAK PCAN, Kvaser, InnoMaker).
"""

import socket
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Known USB-to-CAN hardware vendor and product ID signatures (VID:PID)
KNOWN_CAN_USB_DEVICES = {
    ("1d50", "606f"): "CANable / Candlelight (gs_usb firmware)",
    ("0c72", "000c"): "PEAK-System PCAN-USB",
    ("0c72", "0014"): "PEAK-System PCAN-USB FD",
    ("0c72", "0011"): "PEAK-System PCAN-USB Pro FD",
    ("0bfd", "0004"): "Kvaser Leaf Light v2",
    ("0bfd", "0100"): "Kvaser Leaf Pro HS v2",
    ("1a86", "7523"): "InnoMaker USB2CAN / WCH CH340 Bridge",
    ("0403", "6001"): "FTDI Serial CAN Bridge (slcan)",
    ("0403", "6015"): "FTDI X-Series CAN Bridge (slcan)",
}


def scan_network_can_interfaces(base_path: Optional[Path] = None) -> List[str]:
    """Discover available CAN network interfaces from the Linux network class.

    Args:
        base_path: Optional root directory path to scan (defaults to /sys/class/net).

    Returns:
        List of network interface names that support the CAN protocol.
    """
    interfaces: List[str] = []
    if sys.platform != "linux":
        return interfaces

    net_path = base_path if base_path is not None else Path("/sys/class/net")
    if not net_path.exists():
        return interfaces

    try:
        for iface_dir in net_path.iterdir():
            name = iface_dir.name
            type_file = iface_dir / "type"
            # Linux ARPHRD_CAN is 280 (0x118)
            if type_file.exists():
                try:
                    dev_type = type_file.read_text(encoding="utf-8").strip()
                    if dev_type == "280" or name.startswith(("can", "vcan", "slcan")):
                        interfaces.append(name)
                except OSError:
                    pass
            elif name.startswith(("can", "vcan", "slcan")):
                interfaces.append(name)
    except OSError:
        pass

    return sorted(interfaces)


def scan_usb_can_cables(base_path: Optional[Path] = None) -> List[Dict[str, str]]:
    """Inspect the Linux USB subsystem to detect connected physical CAN hardware.

    Args:
        base_path: Optional root directory path to scan (defaults to /sys/bus/usb/devices).

    Returns:
        List of dictionaries with device name, vendor ID, product ID, and device path.
    """
    cables: List[Dict[str, str]] = []
    if sys.platform != "linux":
        return cables

    usb_path = base_path if base_path is not None else Path("/sys/bus/usb/devices")
    if not usb_path.exists():
        return cables

    try:
        for dev_dir in usb_path.iterdir():
            vid_file = dev_dir / "idVendor"
            pid_file = dev_dir / "idProduct"
            if vid_file.exists() and pid_file.exists():
                try:
                    vid = vid_file.read_text(encoding="utf-8").strip().lower()
                    pid = pid_file.read_text(encoding="utf-8").strip().lower()

                    # Match exact VID:PID or wildcard PID
                    device_name = KNOWN_CAN_USB_DEVICES.get((vid, pid))
                    if not device_name:
                        for (k_vid, k_pid), name in KNOWN_CAN_USB_DEVICES.items():
                            if k_vid == vid and k_pid == "*":
                                device_name = name
                                break

                    if device_name:
                        cables.append({
                            "name": device_name,
                            "vendor_id": vid,
                            "product_id": pid,
                            "sys_path": str(dev_dir),
                        })
                except OSError:
                    pass
    except OSError:
        pass

    return cables


def detect_can_hardware(
    net_base: Optional[Path] = None,
    usb_base: Optional[Path] = None,
) -> Dict[str, Any]:
    """Comprehensive system-level detection of CAN interfaces and connected cables.

    Args:
        net_base: Optional sysfs network base path for dependency injection.
        usb_base: Optional sysfs USB base path for dependency injection.

    Returns:
        Dictionary summarizing SocketCAN availability, connected cables, and network interfaces.
    """
    is_linux = sys.platform == "linux"
    has_af_can = hasattr(socket, "AF_CAN")
    interfaces = scan_network_can_interfaces(base_path=net_base)
    cables = scan_usb_can_cables(base_path=usb_base)

    # Active if a physical USB cable is detected or if an active CAN interface exists
    cable_connected = len(cables) > 0 or any(iface.startswith(("can", "slcan")) for iface in interfaces)
    vcan_active = any(iface.startswith("vcan") for iface in interfaces)

    return {
        "is_linux": is_linux,
        "has_af_can": has_af_can,
        "socketcan_supported": is_linux and has_af_can,
        "interfaces": interfaces,
        "cables_detected": cables,
        "is_cable_connected": cable_connected,
        "vcan_active": vcan_active,
        "is_ready": (is_linux and has_af_can) and (cable_connected or vcan_active),
    }
