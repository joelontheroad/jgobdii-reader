# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Diagnostic Trouble Code (DTC) database and failure cluster correlation engine.

Loads offline SAE J2012 definitions, symptoms, and potential causes, and maps
trouble codes to failure clusters from the diagnostic knowledge base.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DtcInfo:
    """Enriched diagnostic fault code information."""

    code: str
    system: str
    description: str
    symptoms: List[str] = field(default_factory=list)
    causes: List[str] = field(default_factory=list)
    severity: str = "Warning"
    correlated_cluster: Optional[str] = None


class DtcDatabase:
    """Offline DTC dictionary and failure cluster correlation engine."""

    def __init__(self, data_dir: Optional[Path] = None):
        """Initialize the database from local JSON repositories.

        Args:
            data_dir: Optional Path to directory containing dtc_database.json and
                diagnostic_knowledge_base.json. Defaults to project 'data/' folder.
        """
        if data_dir is None:
            # Resolved relative to this module: src/app/ -> ../../data
            data_dir = Path(__file__).resolve().parent.parent.parent / "data"

        self.data_dir = data_dir
        self.dtc_map: Dict[str, Dict[str, Any]] = {}
        self.clusters: List[Dict[str, Any]] = []
        self._load_databases()

    def _load_databases(self) -> None:
        """Safely load JSON databases from the local filesystem with UTF-8 encoding."""
        dtc_file = self.data_dir / "dtc_database.json"
        if dtc_file.exists():
            try:
                with open(dtc_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.dtc_map = data.get("codes", {})
            except (json.JSONDecodeError, OSError):
                self.dtc_map = {}

        kb_file = self.data_dir / "diagnostic_knowledge_base.json"
        if kb_file.exists():
            try:
                with open(kb_file, "r", encoding="utf-8") as f:
                    kb_data = json.load(f)
                    self.clusters = kb_data.get("failure_clusters", [])
            except (json.JSONDecodeError, OSError):
                self.clusters = []

    def lookup_dtc(self, code: str) -> DtcInfo:
        """Lookup diagnostic fault code and return enriched DtcInfo model.

        If the specific code is not present in the local database, generates a
        valid fallback entry based on the SAE J2012 system category prefix.

        Args:
            code: 5-character alphanumeric trouble code (e.g. 'P0420').

        Returns:
            Populated DtcInfo instance.
        """
        clean_code = code.upper().strip()

        # Check for correlated failure cluster
        matched_cluster_name = None
        for cl in self.clusters:
            if clean_code in cl.get("associated_codes", []):
                matched_cluster_name = cl.get("name")
                break

        if clean_code in self.dtc_map:
            entry = self.dtc_map[clean_code]
            return DtcInfo(
                code=clean_code,
                system=entry.get("system", "General Powertrain"),
                description=entry.get("description", "Manufacturer Diagnostic Code"),
                symptoms=entry.get("symptoms", []),
                causes=entry.get("causes", []),
                severity="Critical" if clean_code.startswith("P03") else "Warning",
                correlated_cluster=matched_cluster_name,
            )

        # Fallback system categorization per SAE J2012
        category_map = {
            "P": "Powertrain (Engine & Transmission)",
            "C": "Chassis (Braking, Steering, Suspension)",
            "B": "Body (Airbags, Climate, Lighting)",
            "U": "Network & Communication (CAN Bus)",
        }
        prefix = clean_code[0] if clean_code else "P"
        system_name = category_map.get(prefix, "Automotive Diagnostic Subsystem")

        return DtcInfo(
            code=clean_code,
            system=system_name,
            description="Diagnostic Trouble Code (Refer to service manual for exact OEM definition)",
            symptoms=["Check Engine Light / Malfunction Indicator Lamp (MIL) illuminated"],
            causes=["Sensor circuit out-of-range", "Component failure", "Wiring harness defect"],
            severity="Warning",
            correlated_cluster=matched_cluster_name,
        )

    def correlate_clusters(self, active_dtcs: List[str]) -> List[Dict[str, Any]]:
        """Identify multi-code failure clusters matching the active DTC set.

        Args:
            active_dtcs: List of 5-character DTC strings currently reported by ECU.

        Returns:
            List of matching cluster dictionaries with physics and diagnostic test steps.
        """
        matched = []
        codes_set = set(c.upper().strip() for c in active_dtcs)

        for cl in self.clusters:
            assoc = set(cl.get("associated_codes", []))
            # Match if at least one associated code is active
            if codes_set.intersection(assoc):
                matched.append(cl)

        return matched
