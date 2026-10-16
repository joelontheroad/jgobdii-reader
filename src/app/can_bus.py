# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""CAN bus frame parsing, filtering, and passive monitoring engine.

Provides data structures and parsing functions for raw Controller Area Network
frames captured via ELM327 (AT MA / AT CRA) or J2534 Pass-Thru channels.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class CanFrame:
    """Decoded Controller Area Network (CAN) message frame."""

    timestamp: float
    can_id: int
    can_id_hex: str
    is_extended: bool
    dlc: int
    data: List[int] = field(default_factory=list)
    raw_ascii: str = ""

    def to_dict(self) -> dict:
        """Convert frame to serializable dictionary for JSON streams and Web UI."""
        return {
            "timestamp": self.timestamp,
            "can_id": self.can_id_hex,
            "is_extended": self.is_extended,
            "dlc": self.dlc,
            "data_hex": " ".join(f"{b:02X}" for b in self.data),
            "data_bytes": self.data,
            "raw": self.raw_ascii,
        }


def parse_can_frame(line: str) -> Optional[CanFrame]:
    """Parse a single raw ASCII line from an ELM327 or CAN adapter into a CanFrame.

    Supports both standard 11-bit (e.g. '7E8 04 41 0C 1A F8') and extended 29-bit
    (e.g. '18DA10F1 08 00 00 12 40 00 00 00 00') CAN frames.

    Args:
        line: Raw ASCII line emitted by adapter.

    Returns:
        Populated CanFrame instance, or None if the line does not match frame syntax.
    """
    clean = line.strip().replace("\r", "").replace("\n", "")
    if not clean or clean.startswith("?") or clean in ("OK", "NO DATA", "STOPPED", "BUFFER FULL"):
        return None

    tokens = clean.split()
    if len(tokens) < 2:
        return None

    # First token is the CAN ID
    id_str = tokens[0]
    try:
        can_id_val = int(id_str, 16)
    except ValueError:
        return None

    is_extended = len(id_str) > 3

    # Subsequent tokens represent data bytes or DLC + data
    remaining = tokens[1:]
    parsed_bytes = []
    for t in remaining:
        try:
            val = int(t, 16)
            parsed_bytes.append(val)
        except ValueError:
            break

    if not parsed_bytes:
        return None

    # If first data byte is <= 8 and matches the remaining length, treat as DLC
    if len(parsed_bytes) > 1 and parsed_bytes[0] == len(parsed_bytes) - 1:
        dlc = parsed_bytes[0]
        data_bytes = parsed_bytes[1:]
    else:
        dlc = len(parsed_bytes)
        data_bytes = parsed_bytes

    return CanFrame(
        timestamp=time.time(),
        can_id=can_id_val,
        can_id_hex=id_str.upper(),
        is_extended=is_extended,
        dlc=dlc,
        data=data_bytes,
        raw_ascii=clean,
    )


class CanFilter:
    """Hardware or software CAN frame identifier filter."""

    def __init__(self, filter_id: Optional[str] = None):
        """Initialize filter with optional hexadecimal CAN ID.

        Args:
            filter_id: Optional hex string to match (e.g. '7E8' or '201').
        """
        self.target_id: Optional[int] = int(filter_id, 16) if filter_id else None

    def matches(self, frame: CanFrame) -> bool:
        """Check if frame matches the configured filter rule."""
        if self.target_id is None:
            return True
        return frame.can_id == self.target_id
