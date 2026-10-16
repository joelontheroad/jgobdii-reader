# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Unit tests verifying DTC database lookup, fallback generation, and failure clusters."""

from app.dtc import DtcDatabase, DtcInfo


def test_dtc_database_lookup_known_code():
    """Verify lookup of known standard DTC (P0420)."""
    db = DtcDatabase()
    info = db.lookup_dtc("P0420")
    assert isinstance(info, DtcInfo)
    assert info.code == "P0420"
    assert "Catalyst" in info.description
    assert len(info.symptoms) > 0
    assert len(info.causes) > 0
    assert info.correlated_cluster == "Catalytic Converter Degradation Cluster"


def test_dtc_database_lookup_fallback_code():
    """Verify graceful fallback for unknown/proprietary code."""
    db = DtcDatabase()
    info = db.lookup_dtc("P1999")
    assert info.code == "P1999"
    assert "Powertrain" in info.system
    assert len(info.symptoms) > 0


def test_failure_cluster_correlation():
    """Verify multi-code failure cluster matching."""
    db = DtcDatabase()
    # P0171 and P0174 should correlate to Vacuum Leak cluster
    clusters = db.correlate_clusters(["P0171", "P0174"])
    cluster_names = [c["name"] for c in clusters]
    assert any("Vacuum Leak" in name for name in cluster_names)
