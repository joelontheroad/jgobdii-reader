# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Vehicle domain profiles, connector mappings, and driveline calibration models.

Supports passenger cars, light/medium trucks, Euro 4/5 motorcycles, marine craft,
and powersports ATVs/UTVs.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class VehicleDomain(str, Enum):
    """Categorical domain for vehicle and engine diagnostics."""

    CAR = "car"
    TRUCK = "truck"
    MOTORCYCLE = "motorcycle"
    BOAT = "boat"
    ATV = "atv"


@dataclass(frozen=True)
class VehicleProfile:
    """Configuration profile for a specific vehicle domain and electrical interface."""

    domain: VehicleDomain
    name: str
    display_name: str
    protocol_cmd: str
    protocol_name: str
    connector_type: str
    adapter_guidance: str
    vss_pulses_per_mile: int = 4000
    default_pids: List[str] = field(default_factory=lambda: ["0C", "0D", "05", "11", "10", "14"])


VEHICLE_PROFILES: Dict[str, VehicleProfile] = {
    "car": VehicleProfile(
        domain=VehicleDomain.CAR,
        name="car",
        display_name="Passenger Car (CAN 500k / ISO 9141-2)",
        protocol_cmd="ATSP0",
        protocol_name="Automatic Protocol / ISO 15765-4 CAN",
        connector_type="SAE J1962 16-Pin (Type A)",
        adapter_guidance="Standard in-cabin 16-pin diagnostic port. Direct plug-and-play.",
        vss_pulses_per_mile=4000,
        default_pids=["0C", "0D", "05", "11", "10", "14"],
    ),
    "truck": VehicleProfile(
        domain=VehicleDomain.TRUCK,
        name="truck",
        display_name="Light & Medium Truck (CAN 500k / J1939)",
        protocol_cmd="ATSP6",
        protocol_name="ISO 15765-4 CAN 11/500 (or J1939)",
        connector_type="SAE J1962 16-Pin / Deutsch 9-Pin",
        adapter_guidance="Standard 16-pin port under dash, or Deutsch 9-pin on medium-duty cabs.",
        vss_pulses_per_mile=4000,
        default_pids=["0C", "0D", "05", "04", "10"],
    ),
    "motorcycle": VehicleProfile(
        domain=VehicleDomain.MOTORCYCLE,
        name="motorcycle",
        display_name="Motorcycle (Euro 4/5 - ISO 19689)",
        protocol_cmd="ATSP6",
        protocol_name="ISO 15765-4 (CAN 11-bit, 500 kbps)",
        connector_type="ISO 19689 6-Pin Weatherproof",
        adapter_guidance=(
            "Requires an ISO 19689 6-pin to SAE J1962 16-pin passive adapter cable. "
            "Located under passenger seat or side battery cowl."
        ),
        vss_pulses_per_mile=4000,
        default_pids=["0C", "0D", "05", "11", "14"],
    ),
    "boat": VehicleProfile(
        domain=VehicleDomain.BOAT,
        name="boat",
        display_name="Marine Craft (Inboard/Sterndrive J1939 / NMEA 2000)",
        protocol_cmd="ATSPA",
        protocol_name="SAE J1939 (29-bit CAN, 250 kbps)",
        connector_type="Deutsch 6-Pin (DT06-6S) / M12 Micro-C 5-Pin",
        adapter_guidance=(
            "EPA Part 1045 mandate requires SAE J1939-05. Connect via Deutsch 6-pin "
            "or NMEA 2000 M12 drop cable. Set protocol to ATSPA (250 kbps 29-bit CAN)."
        ),
        vss_pulses_per_mile=0,  # Marine speed measured via GPS or paddlewheel
        default_pids=["0C", "05", "04"],
    ),
    "atv": VehicleProfile(
        domain=VehicleDomain.ATV,
        name="atv",
        display_name="ATV / UTV / Powersports (Side-by-Side)",
        protocol_cmd="ATSP6",
        protocol_name="CAN 500k / 250k Proprietary",
        connector_type="Polaris 8-Pin Delphi / Can-Am 6-Pin Deutsch DTM",
        adapter_guidance=(
            "No federal OBD-II mandate. Requires manufacturer adapter harness "
            "(Polaris 8-pin or Can-Am 6-pin). Direct diagnostic query may require manufacturer DIDs."
        ),
        vss_pulses_per_mile=4000,
        default_pids=["0C", "0D", "05", "11"],
    ),
}


def get_vehicle_profile(name: str = "car") -> VehicleProfile:
    """Retrieve the vehicle profile by identifier string, defaulting to passenger car.

    Args:
        name: Profile key (e.g. 'car', 'motorcycle', 'boat', 'truck', 'atv').

    Returns:
        Configured VehicleProfile instance.
    """
    clean = name.lower().strip()
    return VEHICLE_PROFILES.get(clean, VEHICLE_PROFILES["car"])
