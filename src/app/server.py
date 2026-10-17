# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Lightweight local web server adhering to localhost binding, W3C CSP, and launch token auth."""

import asyncio
import logging
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from app.adapters import get_adapter
from app.adapters.base import DiagnosticAdapterBase
from app.adapters.mock import MockDiagnosticAdapter
from app.config import ToolPreset, list_presets, load_preset, save_preset
from app.dtc import DtcDatabase
from app.hardware import detect_can_hardware
from app.manufacturer import Manufacturer, get_manufacturer_parameters, get_pinout_advisor
from app.protocol import (
    calculate_vss_frequency,
    decode_dtc_breakdown,
    decode_dtc_bytes,
    decode_im_readiness,
    decode_mode05_test,
    decode_pid,
    decode_vin,
    get_mode01_pid_catalog,
    get_supported_protocols,
    is_dtc_supported_by_vehicle,
)
from app.vehicles import get_vehicle_profile

logger = logging.getLogger(__name__)

_last_conn_probe_time: float = 0.0
_last_conn_connected: bool = False
_last_vehicle_detected: bool = False
_cached_vehicle_info: Optional[Dict[str, Any]] = None


async def _get_active_adapter(
    preset: ToolPreset,
    vehicle_prof: Optional[Any] = None,
    force_probe: bool = False,
) -> Tuple[DiagnosticAdapterBase, bool, bool]:
    """Retrieve and connect to the configured adapter without silent mock fallback.

    Args:
        preset: Active ToolPreset.
        vehicle_prof: Optional vehicle domain profile.
        force_probe: If True, bypasses negative probe cooldown cache.

    Returns:
        Tuple of (adapter_instance, is_connected, is_mock).
    """
    global _last_conn_probe_time, _last_conn_connected, _last_vehicle_detected, _cached_vehicle_info
    is_mock = preset.adapter_type == "mock"
    adapter = get_adapter(
        adapter_type=preset.adapter_type,
        host=preset.adapter_host,
        port=preset.adapter_port,
        device_name=getattr(preset, "socketcan_channel", "can0"),
        protocol_cmd=vehicle_prof.protocol_cmd if vehicle_prof else "ATSP0",
    )
    if is_mock:
        await adapter.connect()
        return adapter, True, True

    # Cooldown on failed network probes (1.5 seconds) to prevent blocking HTTP workers
    now = time.monotonic()
    if not force_probe and not _last_conn_connected and (now - _last_conn_probe_time) < 1.5:
        return adapter, False, False

    _last_conn_probe_time = now
    try:
        connected = await asyncio.wait_for(adapter.connect(), timeout=1.8)
    except Exception:
        connected = False

    _last_conn_connected = connected
    if not connected:
        _last_vehicle_detected = False
        _cached_vehicle_info = None

    return adapter, connected, False



class MockDtcRequest(BaseModel):
    """Payload model for injecting simulated DTCs into the mock adapter."""

    action: str = Field(default="set", description="Action to perform: 'set', 'add', 'clear', or 'reset'")
    stored: Optional[List[str]] = Field(default=None, description="List of Mode 03 confirmed DTC strings")
    pending: Optional[List[str]] = Field(default=None, description="List of Mode 07 pending DTC strings")
    permanent: Optional[List[str]] = Field(default=None, description="List of Mode 0A permanent DTC strings")
    code: Optional[str] = Field(default=None, description="Single trouble code for 'add' action")
    mode: str = Field(default="03", description="Diagnostic mode identifier for 'add' action")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforce W3C Content Security Policy and modern defense-in-depth browser headers."""

    async def dispatch(self, request: Request, call_next):
        """Inject strict security headers into every outbound HTTP response."""
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "object-src 'none'; frame-ancestors 'none';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


def create_app(auth_token: Optional[str] = None) -> FastAPI:
    """Create an authenticated, hardened local FastAPI application instance.

    Args:
        auth_token: Optional pre-shared 256-bit hexadecimal launch token.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="jgobdii-reader Local Server",
        description="Localhost-bound web server for jgobdii-reader",
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(SecurityHeadersMiddleware)

    server_token = auth_token or secrets.token_hex(32)
    app.state.auth_token = server_token

    def verify_auth(
        request: Request,
        token_query: Optional[str] = Query(None, alias="token"),
        authorization: Optional[str] = Header(None),
    ) -> str:
        """Verify the ephemeral launch token via query param, header, or cookie."""
        cookie_token = request.cookies.get("jgobdii-reader_session")
        bearer_token = None
        if authorization and authorization.startswith("Bearer "):
            bearer_token = authorization.split(" ")[1]

        candidate = token_query or bearer_token or cookie_token
        if not candidate or not secrets.compare_digest(candidate, app.state.auth_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Valid ephemeral launch token required."
            )
        return candidate

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, token: Optional[str] = Query(None)):
        """Serve the local single-page web interface upon successful authentication."""
        html_path = Path(__file__).parent / "web" / "index.html"
        content = html_path.read_text(encoding="utf-8")

        cookie_token = request.cookies.get("jgobdii-reader_session")
        active_token = None
        if token and secrets.compare_digest(token, app.state.auth_token):
            active_token = token
        elif cookie_token and secrets.compare_digest(cookie_token, app.state.auth_token):
            active_token = cookie_token
        else:
            return HTMLResponse(
                "<h3>401 Unauthorized</h3><p>Please open the authenticated link printed in your terminal.</p>",
                status_code=401,
            )

        resp = HTMLResponse(content=content)
        resp.set_cookie(
            key="jgobdii-reader_session",
            value=active_token,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
        )
        return resp

    @app.get("/api/connection-status")
    async def get_connection_status(
        force: bool = False,
        auth: str = Depends(verify_auth),
    ):
        """Retrieve authoritative two-tier adapter and vehicle ECU connection status."""
        global _last_vehicle_detected, _cached_vehicle_info
        preset = load_preset("default")
        vehicle_prof = get_vehicle_profile(preset.vehicle_domain)
        adapter, is_connected, is_mock = await _get_active_adapter(preset, vehicle_prof, force_probe=force)

        battery_voltage = None
        detected_protocol = None
        vehicle_detected = False
        vehicle_info = {
            "year": None,
            "make": None,
            "model": None,
            "vin": None,
            "display": "Vehicle: Not Detected",
        }

        if is_mock:
            status_state = "mock"
            status_text = "Mock Simulator (Offline)"
            status_msg = "Running built-in mock simulation mode."
            vehicle_detected = True
            vehicle_info = {
                "year": 2000,
                "make": "Toyota",
                "model": "Camry V6",
                "vin": "4T1BE32K0YU123456",
                "display": "2000 Toyota Camry V6 (Simulated)",
            }
        elif not is_connected:
            status_state = "disconnected"
            adapter_name = adapter.get_capabilities().adapter_type
            if preset.adapter_type == "elm327":
                status_text = "Disconnected (ELM327 Wi-Fi)"
                status_msg = f"Cannot reach ELM327 Wi-Fi adapter at {preset.adapter_host}:{preset.adapter_port}."
            elif preset.adapter_type == "socketcan":
                status_text = "Disconnected (SocketCAN)"
                status_msg = f"Cannot access CAN interface '{getattr(preset, 'socketcan_channel', 'can0')}'."
            else:
                status_text = f"Disconnected ({adapter_name})"
                status_msg = f"Could not connect to {adapter_name}."
        else:
            status_data = adapter.get_status()
            battery_voltage = status_data.get("battery_voltage")
            detected_protocol = status_data.get("protocol")

            try:
                vehicle_detected = await adapter.check_vehicle_connected()
            except Exception:
                vehicle_detected = False

            _last_vehicle_detected = vehicle_detected

            if vehicle_detected:
                status_state = "vehicle_connected"
                volt_str = f" - {battery_voltage}" if battery_voltage else ""
                status_text = f"Connected ({adapter.get_capabilities().adapter_type}{volt_str})"
                status_msg = f"Actively communicating with vehicle ECU via {detected_protocol or 'OBD-II'}."

                if _cached_vehicle_info and _cached_vehicle_info.get("valid"):
                    vehicle_info = _cached_vehicle_info
                else:
                    try:
                        vin_data = await adapter.query_vin()
                        decoded = decode_vin(vin_data.get("vin", ""))
                        if decoded.get("valid"):
                            _cached_vehicle_info = decoded
                            vehicle_info = decoded
                        else:
                            vehicle_info["display"] = f"Generic {vehicle_prof.display_name}"
                    except Exception:
                        vehicle_info["display"] = f"Generic {vehicle_prof.display_name}"
            else:
                status_state = "adapter_only"
                status_text = "Adapter Online (Vehicle Key OFF)"
                status_msg = (
                    "Adapter link established, but vehicle ECU is not responding. "
                    "Ensure vehicle ignition is turned to the ON (Run) position."
                )

        if is_connected:
            await adapter.disconnect()

        return {
            "configured_adapter": preset.adapter_type,
            "adapter_connected": is_connected,
            "vehicle_detected": vehicle_detected,
            "is_mock": is_mock,
            "battery_voltage": battery_voltage,
            "protocol": detected_protocol,
            "status_state": status_state,
            "status_text": status_text,
            "status_message": status_msg,
            "vehicle": vehicle_info,
        }

    @app.post("/api/adapter/switch")
    async def switch_adapter(
        adapter_type: str = Query("mock"),
        auth: str = Depends(verify_auth),
    ):
        """Switch active adapter type (e.g. 'mock', 'elm327', 'socketcan')."""
        global _last_conn_probe_time, _last_conn_connected, _cached_vehicle_info
        valid = ["elm327", "socketcan", "j2534", "mock"]
        clean_type = adapter_type.strip().lower()
        if clean_type not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid adapter type '{adapter_type}'. Must be one of {valid}")

        preset = load_preset("default")
        preset.adapter_type = clean_type
        save_preset(preset)

        _last_conn_probe_time = 0.0
        _last_conn_connected = False
        _cached_vehicle_info = None

        return {"status": "switched", "adapter_type": clean_type}

    @app.get("/api/status")
    async def get_status(auth: str = Depends(verify_auth)):
        """Retrieve connection health, detected protocol, and adapter capabilities."""
        preset = load_preset("default")
        vehicle_prof = get_vehicle_profile(preset.vehicle_domain)
        adapter, connected, is_mock = await _get_active_adapter(preset, vehicle_prof)
        try:
            caps = adapter.get_capabilities()
            status_data = adapter.get_status()
            status_data["connected"] = connected
            status_data["is_mock"] = is_mock
            return {
                "adapter": status_data,
                "capabilities": {
                    "adapter_type": caps.adapter_type,
                    "can_high_speed": caps.can_high_speed,
                    "can_medium_speed": caps.can_medium_speed,
                    "single_wire_can": caps.single_wire_can,
                    "multi_channel": caps.multi_channel_parallel,
                    "buffer_risk": caps.buffer_overflow_risk,
                    "max_sample_rate": caps.max_sample_rate_hz,
                },
                "vehicle_profile": {
                    "name": vehicle_prof.name,
                    "display": vehicle_prof.display_name,
                    "connector": vehicle_prof.connector_type,
                    "guidance": vehicle_prof.adapter_guidance,
                },
            }
        finally:
            if connected:
                await adapter.disconnect()

    @app.get("/api/telemetry")
    async def get_telemetry(auth: str = Depends(verify_auth)):
        """Retrieve real-time PID telemetry and derived frequency."""
        preset = load_preset("default")
        vehicle_prof = get_vehicle_profile(preset.vehicle_domain)
        adapter, connected, is_mock = await _get_active_adapter(preset, vehicle_prof)
        if not connected:
            return {
                "connected": False,
                "is_mock": False,
                "vehicle_detected": False,
                "telemetry": None,
                "0C": None,
                "0D": None,
                "05": None,
                "11": None,
                "10": None,
                "14": None,
                "04": None,
                "0F": None,
                "06": None,
                "07": None,
                "vss_hz": 0.0,
                "message": f"Adapter '{preset.adapter_type}' disconnected.",
            }

        try:
            pids = ["0C", "0D", "05", "11", "10", "14", "04", "0F", "06", "07"]
            telemetry: Dict[str, Any] = {
                "connected": True,
                "is_mock": is_mock,
                "vehicle_detected": True,
            }
            for pid in pids:
                data_bytes = await adapter.query_pid("01", pid)
                telemetry[pid] = decode_pid(pid, data_bytes) if data_bytes else 0.0

            speed = telemetry.get("0D", 0.0)
            telemetry["vss_hz"] = calculate_vss_frequency(float(speed or 0.0), vehicle_prof.vss_pulses_per_mile)
            return telemetry
        finally:
            await adapter.disconnect()

    @app.get("/api/enhanced")
    async def get_enhanced(mfg: str = "toyota", auth: str = Depends(verify_auth)):
        """Retrieve manufacturer-specific enhanced parameters."""
        try:
            mfg_enum = Manufacturer(mfg.lower())
        except ValueError:
            mfg_enum = Manufacturer.TOYOTA

        preset = load_preset("default")
        adapter, connected, is_mock = await _get_active_adapter(preset)
        if not connected:
            return {"manufacturer": mfg_enum.value, "parameters": [], "connected": False}

        try:
            params = get_manufacturer_parameters(mfg_enum)
            results = []
            for p in params:
                payload = await adapter.query_enhanced(p.header, p.service_mode, p.pid_hex)
                val = p.decode(payload) if payload else None
                results.append({
                    "id": p.id,
                    "name": p.name,
                    "header": p.header,
                    "value": val,
                    "unit": p.unit,
                    "description": p.description,
                })
            return {"manufacturer": mfg_enum.value, "parameters": results, "connected": True, "is_mock": is_mock}
        finally:
            await adapter.disconnect()

    @app.get("/api/can_frames")
    async def get_can_frames(
        count: int = 5,
        filter_id: Optional[str] = None,
        auth: str = Depends(verify_auth),
    ):
        """Capture and return raw CAN frames."""
        preset = load_preset("default")
        adapter, connected, is_mock = await _get_active_adapter(preset)
        if not connected:
            return {"frames": [], "connected": False}

        try:
            frames = await adapter.capture_can_frames(count=count, filter_id=filter_id)
            return {"frames": [f.to_dict() for f in frames], "connected": True, "is_mock": is_mock}
        finally:
            await adapter.disconnect()

    @app.get("/api/pins")
    async def get_pins(mfg: Optional[str] = None, auth: str = Depends(verify_auth)):
        """Retrieve OBD-II 16-pin connector map and hardware adapter guidance."""
        mfg_enum = Manufacturer(mfg.lower()) if mfg else None
        return {"pins": get_pinout_advisor(mfg_enum)}

    @app.get("/api/dtc")
    async def get_dtcs(mode: str = "03", auth: str = Depends(verify_auth)):
        """Retrieve diagnostic trouble codes and failure clusters."""
        preset = load_preset("default")
        adapter, connected, is_mock = await _get_active_adapter(preset)
        if not connected:
            return {"mode": mode, "count": 0, "dtcs": [], "clusters": {}, "connected": False}

        try:
            db = DtcDatabase()
            codes = await adapter.query_dtcs(mode)
            enriched = [db.lookup_dtc(c) for c in codes]
            clusters = db.correlate_clusters(codes)
            return {
                "mode": mode,
                "count": len(codes),
                "dtcs": [
                    {
                        "code": d.code,
                        "system": d.system,
                        "description": d.description,
                        "symptoms": d.symptoms,
                        "causes": d.causes,
                        "cluster": d.correlated_cluster,
                    }
                    for d in enriched
                ],
                "clusters": clusters,
                "connected": True,
                "is_mock": is_mock,
            }
        finally:
            await adapter.disconnect()

    @app.post("/api/dtc/clear")
    async def clear_dtcs(auth: str = Depends(verify_auth)):
        """Clear DTCs and reset readiness monitors."""
        preset = load_preset("default")
        adapter, connected, is_mock = await _get_active_adapter(preset)
        if not connected:
            return {"status": "disconnected", "success": False}

        try:
            success = await adapter.clear_dtcs()
            return {"status": "cleared" if success else "failed", "success": success}
        finally:
            await adapter.disconnect()

    @app.get("/api/presets")
    async def get_presets_list(auth: str = Depends(verify_auth)):
        """Retrieve list of all locally saved configuration presets."""
        available = list_presets()
        return {"presets": available, "active": "default"}

    @app.get("/api/preset", response_model=ToolPreset)
    async def get_active_preset(
        name: Optional[str] = Query(None),
        auth: str = Depends(verify_auth),
    ):
        """Retrieve a configuration preset by name (defaults to 'default')."""
        target = name.strip() if name and name.strip() else "default"
        try:
            return load_preset(target)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/preset")
    async def update_preset(preset: ToolPreset, auth: str = Depends(verify_auth)):
        """Update and persist configuration preset values to disk."""
        try:
            path = save_preset(preset)
            return {"status": "ok", "path": str(path), "name": preset.name}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/mock/dtc")
    async def get_mock_dtcs(auth: str = Depends(verify_auth)):
        """Retrieve currently active trouble codes in the mock adapter simulator."""
        return {"state": MockDiagnosticAdapter.get_all_dtcs()}

    @app.post("/api/mock/dtc")
    async def set_mock_dtcs(req: MockDtcRequest, auth: str = Depends(verify_auth)):
        """Inject or clear trouble codes in the in-memory mock diagnostic simulator."""
        action = req.action.lower().strip()
        if action == "clear":
            MockDiagnosticAdapter.set_dtcs(stored=[], pending=[], permanent=[])
        elif action == "reset":
            MockDiagnosticAdapter.reset_default_dtcs()
        elif action == "add" and req.code:
            MockDiagnosticAdapter.add_dtc(req.code, req.mode)
        elif action == "set":
            MockDiagnosticAdapter.set_dtcs(
                stored=req.stored,
                pending=req.pending,
                permanent=req.permanent,
            )
        return {
            "status": "ok",
            "action": action,
            "state": MockDiagnosticAdapter.get_all_dtcs(),
        }

    @app.get("/api/reference/dtc")
    async def get_reference_dtcs(
        search: Optional[str] = None,
        system: Optional[str] = None,
        supported_only: bool = False,
        limit: int = 500,
        auth: str = Depends(verify_auth),
    ):
        """Retrieve SAE J2012 standard DTC directory with vehicle compatibility attributes."""
        db = DtcDatabase()

        # Check vehicle capability bitmasks
        supported_pids: Set[str] = set()
        readiness_monitors: Dict[str, Any] = {}
        preset = load_preset("default")
        adapter, connected, is_mock = await _get_active_adapter(preset)
        if connected:
            try:
                supported_pids = await adapter.query_supported_pids()
                pid01 = await adapter.query_pid("01", "01")
                if pid01 and len(pid01) >= 4:
                    readiness_monitors = decode_im_readiness(pid01).get("monitors", {})
            except Exception as exc:
                logger.debug("Could not query adapter capabilities: %s", exc)
            finally:
                await adapter.disconnect()


        results = []
        supported_count = 0
        for code, entry in db.dtc_map.items():
            if search:
                s_lower = search.lower().strip()
                match = (
                    s_lower in code.lower()
                    or s_lower in entry.get("description", "").lower()
                    or any(s_lower in sym.lower() for sym in entry.get("symptoms", []))
                    or any(s_lower in c.lower() for c in entry.get("causes", []))
                )
                if not match:
                    continue
            if system:
                sys_lower = system.lower().strip()
                if sys_lower not in entry.get("system", "").lower() and sys_lower != code[0].lower():
                    continue

            is_supp = is_dtc_supported_by_vehicle(
                code,
                supported_pids=supported_pids,
                readiness_monitors=readiness_monitors,
            )
            if is_supp:
                supported_count += 1

            if supported_only and not is_supp:
                continue

            results.append({
                "code": code,
                "system": entry.get("system", "Powertrain"),
                "description": entry.get("description", ""),
                "symptoms": entry.get("symptoms", []),
                "causes": entry.get("causes", []),
                "is_supported": is_supp,
            })

        sorted_results = sorted(results, key=lambda x: x["code"])
        trimmed = sorted_results[:limit]
        return {
            "total_count": len(sorted_results),
            "count": len(trimmed),
            "supported_count": supported_count,
            "codes": trimmed,
            "dtcs": trimmed,
        }

    @app.get("/api/pids/catalog")
    async def get_pid_catalog_endpoint(auth: str = Depends(verify_auth)):
        """Retrieve full categorized catalog of standardized Mode 01 diagnostic PIDs."""
        catalog = get_mode01_pid_catalog()
        return {
            "total_pids": len(catalog),
            "catalog": catalog,
        }

    @app.get("/api/pids/supported")
    async def get_supported_pids_endpoint(auth: str = Depends(verify_auth)):
        """Discover live vehicle-supported Mode 01 PIDs using 32-bit bitmasks."""
        preset = load_preset("default")
        adapter, connected, is_mock = await _get_active_adapter(preset)
        if not connected:
            return {"supported_pids": [], "count": 0, "connected": False}

        try:
            pids = await adapter.query_supported_pids()
            return {
                "supported_pids": sorted(list(pids)),
                "count": len(pids),
                "connected": True,
                "is_mock": is_mock,
            }
        finally:
            await adapter.disconnect()

    @app.get("/api/mode05")
    async def get_mode05_endpoint(tid: int = 1, auth: str = Depends(verify_auth)):
        """Retrieve Mode 05 Oxygen Sensor Monitoring test results for legacy diagnostics."""
        preset = load_preset("default")
        adapter, connected, is_mock = await _get_active_adapter(preset)
        if not connected:
            return {"error": "Disconnected", "connected": False}

        try:
            res = await adapter.query_mode05(tid=tid)
            if not res and is_mock:
                res = decode_mode05_test(tid, [0x00, 0x5A])
            return res or {"error": "No data", "connected": True}
        finally:
            await adapter.disconnect()

    @app.get("/api/interfaces")
    async def get_interfaces(auth: str = Depends(verify_auth)):
        """Detect physical USB-to-CAN cables and Linux SocketCAN network interfaces."""
        hw = detect_can_hardware()
        summary = "No CAN hardware detected"
        if hw["is_ready"]:
            if hw["is_cable_connected"]:
                summary = "Physical USB-to-CAN cable connected"
            else:
                summary = "Virtual CAN (vcan) network active"
        return {
            "has_can_hardware": hw["is_ready"],
            "is_cable_connected": hw["is_cable_connected"],
            "vcan_active": hw["vcan_active"],
            "socketcan_supported": hw["socketcan_supported"],
            "interfaces": hw["interfaces"],
            "usb_cables": hw["cables_detected"],
            "summary": summary,
        }

    @app.get("/api/protocols")
    async def get_protocols_endpoint(auth: str = Depends(verify_auth)):
        """Retrieve directory of all 10 supported OBD-II and CAN bus protocols."""
        return {"protocols": get_supported_protocols()}

    @app.get("/api/im-readiness")
    async def get_im_readiness(auth: str = Depends(verify_auth)):
        """Retrieve Mode 01 PID 01 Inspection/Maintenance (I/M) Readiness monitor flags."""
        preset = load_preset("default")
        adapter, connected, is_mock = await _get_active_adapter(preset)
        if not connected:
            return {
                "overall_status": "DISCONNECTED",
                "mil_on": False,
                "dtc_count": 0,
                "monitors": {},
                "connected": False,
            }

        try:
            raw_bytes = await adapter.query_pid("01", "01")
            if not raw_bytes or len(raw_bytes) < 4:
                if is_mock:
                    raw_bytes = [0x82, 0x07, 0x65, 0x01]
                else:
                    return {
                        "overall_status": "NO_DATA",
                        "mil_on": False,
                        "dtc_count": 0,
                        "monitors": {},
                        "connected": True,
                    }
            result = decode_im_readiness(raw_bytes)
            result["connected"] = True
            result["is_mock"] = is_mock
            return result
        finally:
            await adapter.disconnect()

    @app.get("/api/freeze-frame")
    async def get_freeze_frame(auth: str = Depends(verify_auth)):
        """Retrieve Mode 02 Freeze Frame telemetry snapshot taken at time of fault."""
        preset = load_preset("default")
        adapter, connected, is_mock = await _get_active_adapter(preset)
        if not connected:
            return {"dtc": None, "frame_number": 0, "telemetry": {}, "connected": False}

        try:
            if hasattr(adapter, "query_freeze_frame"):
                data = await adapter.query_freeze_frame()
                data["connected"] = True
                data["is_mock"] = is_mock
                return data
            dtc_bytes = await adapter.query_pid("02", "02")
            dtc = decode_dtc_bytes(dtc_bytes[0], dtc_bytes[1]) if dtc_bytes and len(dtc_bytes) >= 2 else None
            rpm_bytes = await adapter.query_pid("02", "0C")
            speed_bytes = await adapter.query_pid("02", "0D")
            temp_bytes = await adapter.query_pid("02", "05")
            load_bytes = await adapter.query_pid("02", "04")
            return {
                "dtc": dtc,
                "frame_number": 0,
                "telemetry": {
                    "0C": decode_pid("0C", rpm_bytes) if rpm_bytes else 0.0,
                    "0D": decode_pid("0D", speed_bytes) if speed_bytes else 0.0,
                    "05": decode_pid("05", temp_bytes) if temp_bytes else 0.0,
                    "04": decode_pid("04", load_bytes) if load_bytes else 0.0,
                },
                "connected": True,
                "is_mock": is_mock,
            }
        finally:
            await adapter.disconnect()

    @app.get("/api/mode06")
    async def get_mode06(auth: str = Depends(verify_auth)):
        """Retrieve Mode 06 On-Board Diagnostic Component Monitoring test results."""
        preset = load_preset("default")
        adapter, connected, is_mock = await _get_active_adapter(preset)
        if not connected:
            return {"tests": [], "count": 0, "connected": False}

        try:
            if hasattr(adapter, "query_mode06"):
                results = await adapter.query_mode06()
            elif is_mock:
                mock_ad = get_adapter("mock")
                results = await mock_ad.query_mode06()
            else:
                results = []
            return {"tests": results, "count": len(results), "connected": True, "is_mock": is_mock}
        finally:
            await adapter.disconnect()

    @app.get("/api/vin")
    async def get_vin_endpoint(auth: str = Depends(verify_auth)):
        """Retrieve Mode 09 vehicle identification, calibration ID, and CVN."""
        preset = load_preset("default")
        adapter, connected, is_mock = await _get_active_adapter(preset)
        if not connected:
            return {
                "vin": "",
                "calibration_id": "",
                "cvn": "",
                "year": None,
                "make": None,
                "model": None,
                "country": None,
                "display": "Vehicle: Not Detected",
                "connected": False,
            }

        try:
            data = await adapter.query_vin() if hasattr(adapter, "query_vin") else {"vin": "", "calibration_id": "", "cvn": ""}
            decoded = decode_vin(data.get("vin", ""))
            return {
                "vin": data.get("vin", ""),
                "calibration_id": data.get("calibration_id", ""),
                "cvn": data.get("cvn", ""),
                "year": decoded.get("year"),
                "make": decoded.get("make"),
                "model": decoded.get("model"),
                "country": decoded.get("country"),
                "display": decoded.get("display") if decoded.get("valid") else "Vehicle: Unknown",
                "connected": True,
                "is_mock": is_mock,
            }
        finally:
            await adapter.disconnect()


    @app.get("/api/decode-dtc")
    async def get_decoded_dtc(code: str = Query("P0420"), auth: str = Depends(verify_auth)):
        """Deconstruct and explain the structural hierarchy of any OBD-II fault code."""
        breakdown = decode_dtc_breakdown(code)
        if breakdown.get("valid"):
            db = DtcDatabase()
            enriched = db.lookup_dtc(code)
            breakdown["known_description"] = enriched.description
            breakdown["symptoms"] = enriched.symptoms
            breakdown["causes"] = enriched.causes
        return breakdown

    @app.get("/api/reference/mfg-dtc")
    async def get_reference_mfg_dtcs(
        mfg: str = Query("toyota"),
        search: Optional[str] = None,
        supported_only: bool = False,
        auth: str = Depends(verify_auth),
    ):
        """Retrieve manufacturer-specific DTC reference definitions across 11 brands."""
        import json
        mfg_key = mfg.lower().strip()
        data_dir = Path(__file__).resolve().parent.parent.parent / "data"

        # Evaluate if this brand is supported by current vehicle profile
        is_brand_supported = mfg_key == "toyota"  # Default vehicle profile is Toyota/Lexus

        brand_meta = {
            "toyota": {"name": "Toyota / Lexus / Scion", "supported_pins": "Pins 6 & 14 (HS-CAN)", "protocols": "ISO 15765-4 (CAN 500k), ISO 14230-4", "ecm_header": "0x7E0", "baud_rate": "500 kbps"},
            "bmw": {"name": "BMW / Mini", "supported_pins": "Pins 6 & 14 (D-CAN) + Pin 8 (K-Line)", "protocols": "ISO 15765-4 (CAN 500k), KWP2000", "ecm_header": "0x7E0 / 0x6F1", "baud_rate": "500 kbps"},
            "volkswagen": {"name": "Volkswagen / Audi / SEAT / Skoda (VAG)", "supported_pins": "Pins 6 & 14 (CAN/UDS) + Pin 7 (K-Line)", "protocols": "ISO 15765-4 (CAN 500k), UDS", "ecm_header": "0x7E0", "baud_rate": "500 kbps"},
            "ford": {"name": "Ford / Lincoln / Mercury", "supported_pins": "Pins 6 & 14 (HS-CAN) + Pins 3 & 11 (MS-CAN)", "protocols": "ISO 15765-4 (CAN 500k), MS-CAN (250k), SAE J1850 PWM", "ecm_header": "0x7E0", "baud_rate": "500 kbps / 250 kbps"},
            "gm": {"name": "General Motors / Chevrolet / GMC / Cadillac", "supported_pins": "Pins 6 & 14 (HS-CAN) + Pin 1 (SW-CAN)", "protocols": "ISO 15765-4 (CAN 500k), Single-Wire CAN (33.3k), SAE J1850 VPW", "ecm_header": "0x7E0", "baud_rate": "500 kbps / 33.3 kbps"},
            "honda": {"name": "Honda / Acura", "supported_pins": "Pins 6 & 14 (H-CAN)", "protocols": "ISO 15765-4 (CAN 500k), ISO 9141-2", "ecm_header": "0x7E0", "baud_rate": "500 kbps"},
            "nissan": {"name": "Nissan / Infiniti", "supported_pins": "Pins 6 & 14 (CAN)", "protocols": "ISO 15765-4 (CAN 500k), Nissan Consult", "ecm_header": "0x7E0", "baud_rate": "500 kbps"},
            "chrysler": {"name": "Chrysler / Dodge / Jeep / Ram", "supported_pins": "Pins 6 & 14 (CAN C) + Pins 3 & 11 (CAN IHS)", "protocols": "ISO 15765-4 (CAN 500k), CAN-B", "ecm_header": "0x7E0", "baud_rate": "500 kbps / 125 kbps"},
            "mitsubishi": {"name": "Mitsubishi", "supported_pins": "Pins 6 & 14 (CAN) + Pin 1 (Flash)", "protocols": "ISO 15765-4 (CAN 500k), ISO 9141-2", "ecm_header": "0x7E0", "baud_rate": "500 kbps"},
            "fiat": {"name": "Fiat", "supported_pins": "Pins 6 & 14 (C-CAN) + Pins 1 & 9 (B-CAN)", "protocols": "ISO 15765-4 (CAN 500k), KWP2000", "ecm_header": "0x7E0", "baud_rate": "500 kbps / 50 kbps"},
            "alfaromeo": {"name": "Alfa Romeo", "supported_pins": "Pins 6 & 14 (C-CAN)", "protocols": "ISO 15765-4 (CAN 500k)", "ecm_header": "0x7E0", "baud_rate": "500 kbps"},
        }

        meta = brand_meta.get(mfg_key, {
            "name": mfg.title(),
            "supported_pins": "Pins 6 & 14 (HS-CAN)",
            "protocols": "ISO 15765-4 (CAN 500k)",
            "ecm_header": "0x7E0",
            "baud_rate": "500 kbps",
        })

        codes_list = []

        # Check local OEM database directory
        oem_file = data_dir / "manufacturer_dtcs" / f"{mfg_key}.json"
        if oem_file.exists():
            try:
                with open(oem_file, "r", encoding="utf-8") as f:
                    raw_dict = json.load(f)
                    for code_k, desc_v in raw_dict.items():
                        codes_list.append({
                            "code": code_k,
                            "system": f"{meta['name']} Subsystem",
                            "description": desc_v if isinstance(desc_v, str) else desc_v.get("description", ""),
                            "symptoms": ["Check Engine Light (MIL)"],
                            "causes": ["Component or sensor malfunction"],
                            "is_supported": is_brand_supported,
                        })
            except (json.JSONDecodeError, OSError):
                codes_list = []

        # Fallback/merge with manufacturer_dtc_database.json (e.g. for toyota)
        legacy_file = data_dir / "manufacturer_dtc_database.json"
        if legacy_file.exists() and not codes_list:
            try:
                with open(legacy_file, "r", encoding="utf-8") as f:
                    leg_data = json.load(f)
                    leg_mfg = leg_data.get("manufacturers", {}).get(mfg_key, {})
                    raw_legacy = leg_mfg.get("codes", [])
                    for item in raw_legacy:
                        codes_list.append({
                            "code": item.get("code", ""),
                            "system": item.get("system", f"{meta['name']} Subsystem"),
                            "description": item.get("description", ""),
                            "symptoms": item.get("symptoms", ["Check Engine Light (MIL)"]),
                            "causes": item.get("causes", ["Component or sensor malfunction"]),
                            "is_supported": is_brand_supported,
                        })
            except (json.JSONDecodeError, OSError):
                pass

        # Apply search filter if specified
        if search:
            q = search.lower().strip()
            codes_list = [
                c for c in codes_list
                if q in c.get("code", "").lower() or q in c.get("description", "").lower()
            ]

        if supported_only and not is_brand_supported:
            codes_list = []

        total_matching = len(codes_list)
        # Limit response to 500 items max to avoid overwhelming DOM
        trimmed_codes = codes_list[:500]

        return {
            "manufacturer": mfg_key,
            "name": meta["name"],
            "protocols": meta["protocols"],
            "primary_protocol": meta["protocols"],
            "supported_pins": meta["supported_pins"],
            "ecm_header": meta["ecm_header"],
            "baud_rate": meta["baud_rate"],
            "is_brand_supported": is_brand_supported,
            "total_count": total_matching,
            "count": len(trimmed_codes),
            "codes": trimmed_codes,
            "dtcs": trimmed_codes,
        }

    return app


def _launch_browser_silently(url: str) -> None:
    """Launch the default web browser cleanly without leaking terminal console noise.

    On Linux, xdg-open and browser launcher scripts frequently emit diagnostic warnings
    (such as 'Opening in existing browser session' and Chromium zygote broken pipe
    warnings) if child process file descriptors remain attached to the parent terminal.
    Decoupling the child process with standard streams redirected to DEVNULL prevents
    console clutter while ensuring the browser tab opens reliably.

    Args:
        url: Complete dashboard URL including authentication query token.
    """
    if sys.platform.startswith("linux"):
        xdg_bin = shutil.which("xdg-open")
        if xdg_bin:
            try:
                # SECURITY: CWE-78: Pass arguments as discrete arrays, avoid shell=True
                subprocess.Popen(  # noqa: S603 - Trusted command array with discrete arguments; url is locally formatted localhost token URL
                    [xdg_bin, url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return
            except Exception as exc:
                logger.debug("Silent xdg-open invocation failed: %s; falling back to webbrowser", exc)

    try:
        webbrowser.open(url)
    except Exception as exc:
        logger.debug("Failed to launch web browser via standard library: %s", exc)


def format_clickable_url(url: str, stream: Any = None) -> str:
    """Format a URL as an OSC 8 clickable link when supported by terminal and environment.

    Args:
        url: Destination URL to format.
        stream: Output stream to inspect for interactive TTY capabilities. Defaults to sys.stderr.

    Returns:
        OSC 8 formatted hyperlink string if on interactive TTY without NO_COLOR,
        otherwise the plain text URL.
    """
    target_stream = stream if stream is not None else sys.stderr
    no_color = os.environ.get("NO_COLOR", "") != ""
    is_tty = hasattr(target_stream, "isatty") and target_stream.isatty()
    if is_tty and not no_color:
        return f"\033]8;;{url}\033\\{url}\033]8;;\033\\"
    return url


def open_browser(url: str, no_browser: bool = False) -> bool:
    """Open the user's default browser window unless suppressed or running headless.

    Args:
        url: Local dashboard URL with authentication token.
        no_browser: Whether automatic launch was explicitly suppressed by user flag.

    Returns:
        True if browser launch was dispatched, False if suppressed or headless.
    """
    if no_browser:
        return False

    # Standard check: suppress auto-launch in CI environments
    if os.environ.get("CI", "").lower() == "true":
        return False

    # Check for headless Linux display server
    if sys.platform.startswith("linux"):
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return False

    _launch_browser_silently(url)
    return True


def run_local_server(
    port: int = 8080,
    host: str = "127.0.0.1",
    open_browser: bool = True,
    no_browser: bool = False,
) -> None:
    """Run the local uvicorn server strictly bound to localhost.

    Args:
        port: TCP port number to listen on. Defaults to 8080.
        host: IP interface to bind to. Defaults strictly to '127.0.0.1'.
        open_browser: Automatically open default web browser if True. Defaults to True.
        no_browser: Suppress automatic browser launch if True. Defaults to False.
    """
    if no_browser:
        open_browser = False

    import uvicorn
    token = secrets.token_hex(32)
    app = create_app(auth_token=token)
    url = f"http://{host}:{port}/?token={token}"

    clickable_link = format_clickable_url(url, stream=sys.stderr)

    sys.stderr.write("\n[jgobdii-reader] Local server running at:\n\n")
    sys.stderr.write(f"    {clickable_link}\n\n")
    sys.stderr.write("[jgobdii-reader] Bound strictly to localhost for privacy and security. Press Ctrl+C to exit.\n\n")
    sys.stderr.flush()

    if open_browser:
        threading.Timer(0.3, _launch_browser_silently, args=[url]).start()

    uvicorn.run(app, host=host, port=port, log_level="warning")
