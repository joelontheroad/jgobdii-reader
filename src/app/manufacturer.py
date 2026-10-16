# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Manufacturer-specific diagnostic parameters, UDS DIDs, and pinout advisory.

Covers enhanced physical module addressing (AT SH) and proprietary parameter
decoding for Toyota/Lexus, Honda/Acura, General Motors, and Ford.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class Manufacturer(str, Enum):
    """Supported vehicle manufacturers with enhanced diagnostic profiles."""

    TOYOTA = "toyota"
    HONDA = "honda"
    GM = "gm"
    FORD = "ford"
    GENERIC = "generic"


@dataclass(frozen=True)
class EnhancedParameter:
    """Definition of an enhanced manufacturer-specific diagnostic parameter."""

    id: str
    name: str
    manufacturer: Manufacturer
    header: str
    service_mode: str
    pid_hex: str
    unit: str
    description: str
    decoder: Callable[[List[int]], Any]

    def decode(self, payload: List[int]) -> Optional[Any]:
        """Decode raw byte payload into formatted engineering value."""
        if not payload:
            return None
        try:
            return self.decoder(payload)
        except (IndexError, ValueError, TypeError):
            return None


@dataclass(frozen=True)
class PinDefinition:
    """OBD-II 16-pin connector pin role and electrical assignment."""

    pin_number: int
    name: str
    is_standard: bool
    function_description: str
    mfg_notes: Dict[str, str]


# Reference catalog of SAE J1962 16-pin assignments
OBD2_PINS: List[PinDefinition] = [
    PinDefinition(1, "Vendor / SWCAN", False, "Single-Wire CAN (GM GMLAN 33.3k) or ignition sense", {
        "gm": "Single-Wire CAN (GMLAN 33.3 kbps) for Body/HVAC/Radio. Requires J2534 or SWCAN transceiver.",
        "ford": "Ignition status or MS-CAN+ on select transitional models.",
        "toyota": "Unpopulated on most North American models.",
        "honda": "Unpopulated."
    }),
    PinDefinition(2, "J1850 Bus (+)", True, "SAE J1850 PWM (+) or VPW (GM Class 2 10.4k)", {
        "gm": "GM Class 2 serial bus on pre-2007 vehicles.",
        "ford": "J1850 PWM high line on pre-2004 vehicles."
    }),
    PinDefinition(3, "Vendor / MS-CAN-H", False, "Medium-Speed CAN High (Ford MS-CAN 125k)", {
        "ford": "MS-CAN High (125 kbps) for Body, Cluster, HVAC. Requires J2534 or ELM327 toggle switch.",
        "gm": "Secondary vendor discretionary link.",
        "toyota": "Unpopulated.",
        "honda": "Unpopulated."
    }),
    PinDefinition(4, "Chassis Ground", True, "Chassis metal reference ground", {}),
    PinDefinition(5, "Signal Ground", True, "Isolated clean electronic logic ground", {}),
    PinDefinition(6, "CAN High (HS-CAN)", True, "ISO 15765-4 High-Speed CAN High (500 kbps, 2.5V-3.5V)", {
        "all": "Primary Powertrain & Emissions bus used by standard ELM327 and J2534."
    }),
    PinDefinition(7, "K-Line", True, "ISO 9141-2 / ISO 14230-4 K-Line asynchronous serial", {
        "toyota": "Used on 2000-2004 Camry/Corolla (ISO 9141-2 slow 5-baud init).",
        "honda": "Used on pre-2006 Honda/Acura K-Line diagnostics."
    }),
    PinDefinition(8, "Vendor Discretionary", False, "Ignition detect or secondary K-Line", {
        "toyota": "Unpopulated.",
        "honda": "Unpopulated.",
        "gm": "Unpopulated."
    }),
    PinDefinition(9, "Vendor Discretionary", False, "Tachometer speed pulse or diagnostic check", {
        "toyota": "Engine tachometer pulse output on older models.",
        "honda": "SCS (Service Check Signal); grounding triggers manual flash codes."
    }),
    PinDefinition(10, "J1850 Bus (-)", True, "SAE J1850 PWM (-) complementary low line", {
        "ford": "J1850 PWM low line on pre-2004 vehicles."
    }),
    PinDefinition(11, "Vendor / MS-CAN-L", False, "Medium-Speed CAN Low (Ford MS-CAN 125k)", {
        "ford": "MS-CAN Low (125 kbps). Paired with Pin 3. Requires J2534 or switched ELM327."
    }),
    PinDefinition(12, "Vendor Discretionary", False, "Manufacturer programming or chassis link", {}),
    PinDefinition(13, "Vendor / FEPS", False, "Flash programming voltage (Ford FEPS 18V) or TC terminal", {
        "ford": "FEPS (18V) programming voltage line for PCM reflashing via J2534.",
        "toyota": "TC (Timing Check) terminal; bridge to Pin 4 Ground for ABS/airbag blink codes."
    }),
    PinDefinition(14, "CAN Low (HS-CAN)", True, "ISO 15765-4 High-Speed CAN Low (500 kbps, 2.5V-1.5V)", {
        "all": "Primary Powertrain & Emissions bus paired with Pin 6."
    }),
    PinDefinition(15, "L-Line", True, "ISO 9141-2 / ISO 14230-4 optional slow init low line", {}),
    PinDefinition(16, "Battery Power", True, "Unswitched permanent +12V battery power", {}),
]


# Enhanced Parameter Definitions for Toyota / Lexus
TOYOTA_PARAMETERS: List[EnhancedParameter] = [
    EnhancedParameter(
        id="toyota_atf_temp",
        name="Transmission Fluid Temperature (ATF)",
        manufacturer=Manufacturer.TOYOTA,
        header="7E1",
        service_mode="21",
        pid_hex="82",
        unit="°C",
        description="Automatic transmission pan fluid temperature.",
        decoder=lambda d: round(float(d[0] - 40), 1),
    ),
    EnhancedParameter(
        id="toyota_hybrid_soc",
        name="Hybrid Battery State of Charge (SOC)",
        manufacturer=Manufacturer.TOYOTA,
        header="7E2",
        service_mode="21",
        pid_hex="01",
        unit="%",
        description="High-voltage traction battery charge percentage.",
        decoder=lambda d: round(float(d[0] * 100.0 / 255.0), 1),
    ),
    EnhancedParameter(
        id="toyota_hybrid_block_01",
        name="Hybrid Battery Block 01 Voltage",
        manufacturer=Manufacturer.TOYOTA,
        header="7E2",
        service_mode="21",
        pid_hex="C3",
        unit="V",
        description="Voltage across NiMH or Li-Ion cell block 1.",
        decoder=lambda d: round(((d[0] * 256.0) + d[1]) / 100.0, 2) if len(d) >= 2 else None,
    ),
    EnhancedParameter(
        id="toyota_inverter_temp",
        name="Hybrid Inverter Temperature",
        manufacturer=Manufacturer.TOYOTA,
        header="7E2",
        service_mode="22",
        pid_hex="1001",
        unit="°C",
        description="Motor generator power electronics inverter temperature.",
        decoder=lambda d: round(float(d[0] - 40), 1),
    ),
]

# Enhanced Parameter Definitions for Honda / Acura
HONDA_PARAMETERS: List[EnhancedParameter] = [
    EnhancedParameter(
        id="honda_vtec_status",
        name="VTEC Spool Solenoid Status",
        manufacturer=Manufacturer.HONDA,
        header="7E0",
        service_mode="22",
        pid_hex="1101",
        unit="State",
        description="Variable Valve Timing & Lift Electronic Control engagement.",
        decoder=lambda d: "Engaged" if d[0] > 0 else "Disengaged",
    ),
    EnhancedParameter(
        id="honda_at_slip_rpm",
        name="Torque Converter Clutch Slip",
        manufacturer=Manufacturer.HONDA,
        header="7E1",
        service_mode="22",
        pid_hex="1120",
        unit="RPM",
        description="Speed differential across torque converter impeller and turbine.",
        decoder=lambda d: round(((d[0] * 256.0) + d[1]) / 4.0, 1) if len(d) >= 2 else None,
    ),
    EnhancedParameter(
        id="honda_fl_wheel_speed",
        name="Front-Left Wheel Speed (ABS)",
        manufacturer=Manufacturer.HONDA,
        header="7A0",
        service_mode="22",
        pid_hex="1130",
        unit="km/h",
        description="Individual wheel speed reading from ABS/VSA speed sensor.",
        decoder=lambda d: float(d[0]),
    ),
    EnhancedParameter(
        id="honda_ima_soc",
        name="IMA Hybrid Battery State of Charge",
        manufacturer=Manufacturer.HONDA,
        header="7E2",
        service_mode="22",
        pid_hex="1140",
        unit="%",
        description="Integrated Motor Assist traction battery usable capacity.",
        decoder=lambda d: round(float(d[0]) / 2.0, 1),
    ),
]

# Enhanced Parameter Definitions for General Motors (GM)
GM_PARAMETERS: List[EnhancedParameter] = [
    EnhancedParameter(
        id="gm_trans_temp",
        name="Transmission Fluid Temperature",
        manufacturer=Manufacturer.GM,
        header="7E1",
        service_mode="22",
        pid_hex="1940",
        unit="°C",
        description="Automatic transmission fluid sump temperature.",
        decoder=lambda d: round(float(d[0] - 40), 1),
    ),
    EnhancedParameter(
        id="gm_cyl1_misfire",
        name="Cylinder 1 Misfire Current Count",
        manufacturer=Manufacturer.GM,
        header="7E0",
        service_mode="22",
        pid_hex="1201",
        unit="Counts",
        description="Current trip real-time misfire count for cylinder 1.",
        decoder=lambda d: int((d[0] * 256) + d[1]) if len(d) >= 2 else int(d[0]),
    ),
    EnhancedParameter(
        id="gm_cyl2_misfire",
        name="Cylinder 2 Misfire Current Count",
        manufacturer=Manufacturer.GM,
        header="7E0",
        service_mode="22",
        pid_hex="1202",
        unit="Counts",
        description="Current trip real-time misfire count for cylinder 2.",
        decoder=lambda d: int((d[0] * 256) + d[1]) if len(d) >= 2 else int(d[0]),
    ),
    EnhancedParameter(
        id="gm_knock_retard",
        name="Knock Spark Retard",
        manufacturer=Manufacturer.GM,
        header="7E0",
        service_mode="22",
        pid_hex="11A6",
        unit="°",
        description="Ignition timing retard commanded by knock sensor feedback.",
        decoder=lambda d: round(float(d[0]) * 0.35, 1),
    ),
    EnhancedParameter(
        id="gm_ethanol_pct",
        name="FlexFuel Ethanol Content",
        manufacturer=Manufacturer.GM,
        header="7E0",
        service_mode="22",
        pid_hex="0052",
        unit="%",
        description="Measured percentage of ethanol in vehicle fuel tank.",
        decoder=lambda d: float(d[0]),
    ),
]

# Enhanced Parameter Definitions for Ford
FORD_PARAMETERS: List[EnhancedParameter] = [
    EnhancedParameter(
        id="ford_cht",
        name="Cylinder Head Temperature (CHT)",
        manufacturer=Manufacturer.FORD,
        header="7E0",
        service_mode="22",
        pid_hex="1624",
        unit="°C",
        description="Metal cylinder head temperature sensor reading.",
        decoder=lambda d: round(float(d[0] - 40), 1),
    ),
    EnhancedParameter(
        id="ford_trans_temp",
        name="Transmission Fluid Temperature (TFT)",
        manufacturer=Manufacturer.FORD,
        header="7E0",
        service_mode="22",
        pid_hex="1E1C",
        unit="°C",
        description="Transmission sump fluid temperature.",
        decoder=lambda d: round(((d[0] * 256.0) + d[1]) / 16.0 - 40.0, 1) if len(d) >= 2 else None,
    ),
    EnhancedParameter(
        id="ford_turbo_boost",
        name="Turbocharger Boost Pressure",
        manufacturer=Manufacturer.FORD,
        header="7E0",
        service_mode="22",
        pid_hex="0462",
        unit="PSI",
        description="Manifold gauge boost pressure above atmospheric.",
        decoder=lambda d: round(float(d[0]) * 0.145, 1),
    ),
    EnhancedParameter(
        id="ford_cyl1_misfire",
        name="Cylinder 1 Misfire Total Counter",
        manufacturer=Manufacturer.FORD,
        header="7E0",
        service_mode="22",
        pid_hex="160E",
        unit="Counts",
        description="Cumulative misfire cycle counter for cylinder 1.",
        decoder=lambda d: int((d[0] * 256) + d[1]) if len(d) >= 2 else int(d[0]),
    ),
]


def get_manufacturer_parameters(mfg: Manufacturer) -> List[EnhancedParameter]:
    """Retrieve the list of enhanced parameters for a designated manufacturer.

    Args:
        mfg: Target vehicle manufacturer.

    Returns:
        List of EnhancedParameter definitions for the manufacturer.
    """
    if mfg == Manufacturer.TOYOTA:
        return TOYOTA_PARAMETERS
    if mfg == Manufacturer.HONDA:
        return HONDA_PARAMETERS
    if mfg == Manufacturer.GM:
        return GM_PARAMETERS
    if mfg == Manufacturer.FORD:
        return FORD_PARAMETERS
    return []


def get_pinout_advisor(mfg: Optional[Manufacturer] = None) -> List[Dict[str, Any]]:
    """Return structured OBD-II 16-pin connector map and hardware adapter requirements.

    Args:
        mfg: Optional manufacturer filter for brand-specific pin notes.

    Returns:
        List of pin status dictionaries including number, standard status, and notes.
    """
    result = []
    mfg_key = mfg.value if mfg else "all"
    for p in OBD2_PINS:
        note = p.mfg_notes.get(mfg_key, p.mfg_notes.get("all", ""))
        result.append({
            "pin": p.pin_number,
            "name": p.name,
            "is_standard": p.is_standard,
            "description": p.function_description,
            "manufacturer_note": note,
        })
    return result
