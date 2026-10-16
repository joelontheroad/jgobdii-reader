# SPDX-FileCopyrightText: 2026 [Author/Organization]
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Command-line interface implementation adhering to POSIX standards and stream discipline.

Enforces strict separation of streams:
- stdout: Machine data and structured JSON
- stderr: Informational logs, diagnostic banners, and error messages
"""

import argparse
import asyncio
import json
import os
import signal
import sys
from typing import List, Optional

import yaml

from app import __repository__, __version__
from app.adapters import get_adapter
from app.config import (
    list_presets,
    load_preset,
    reset_all_configuration,
)
from app.dtc import DtcDatabase
from app.manufacturer import Manufacturer, get_manufacturer_parameters, get_pinout_advisor
from app.protocol import calculate_vss_frequency, decode_pid, get_supported_protocols
from app.vehicles import get_vehicle_profile


def setup_signal_handlers() -> None:
    """Gracefully handle SIGINT and SIGTERM without dumping unhandled tracebacks."""
    def _sig_handler(signum, frame):
        sys.stderr.write("\n[jgobdii-reader] Process interrupted by user. Exiting.\n")
        sys.stderr.flush()
        sys.exit(130)

    signal.signal(signal.SIGINT, _sig_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _sig_handler)


def should_colorize() -> bool:
    """Determine whether terminal ANSI colors should be emitted.

    Checks for the NO_COLOR standard environment variable before verifying
    whether stdout is connected to an interactive TTY.

    Returns:
        True if colors are supported and allowed, False otherwise.
    """
    if "NO_COLOR" in os.environ:
        return False
    return sys.stdout.isatty()


def main(argv: Optional[List[str]] = None) -> int:
    """Execute the primary command-line interface entry point.

    Args:
        argv: Optional list of CLI argument strings. If None, sys.argv[1:] is parsed.

    Returns:
        Integer exit code: 0 for success, 1 for operational error, 2 for CLI syntax error.
    """
    setup_signal_handlers()

    common_parent = argparse.ArgumentParser(add_help=False)
    common_parent.add_argument(
        "--adapter",
        type=str,
        default=argparse.SUPPRESS,
        choices=["elm327", "j2534", "socketcan", "mock"],
        help="Diagnostic interface adapter type (default: from active preset).",
    )
    common_parent.add_argument(
        "--channel",
        type=str,
        default=argparse.SUPPRESS,
        help="SocketCAN interface name (e.g. can0, vcan0) or J2534 device identifier.",
    )
    common_parent.add_argument(
        "--host",
        type=str,
        default=argparse.SUPPRESS,
        help="ELM327 Wi-Fi host IP or hostname (default: 192.168.0.10).",
    )
    common_parent.add_argument(
        "--port",
        type=int,
        default=argparse.SUPPRESS,
        help="ELM327 Wi-Fi TCP port (default: 35000).",
    )
    common_parent.add_argument(
        "--preset",
        type=str,
        default=argparse.SUPPRESS,
        help="Name of YAML preset profile to load.",
    )
    common_parent.add_argument(
        "-q", "--quiet",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress all informational messages (errors and data output only).",
    )
    common_parent.add_argument(
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Enable verbose diagnostic output on stderr.",
    )
    common_parent.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Output structured results in machine-readable JSON format to stdout.",
    )

    proto_lines = "\n".join([f"  {p['id']:<26} {p['name']}" for p in get_supported_protocols()])
    parser = argparse.ArgumentParser(
        prog="jgobdii-reader",
        description="jgobdii-reader: An advanced diagnostic suite supporting SocketCAN, J2534, and ELM327.",
        epilog=f"Supported Communication Protocols (10 standards):\n{proto_lines}\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common_parent],
    )

    # Standard global flags
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__} (GNU AGPLv3)\nSource: {__repository__}",
        help="Show program version and license information.",
    )
    parser.add_argument(
        "--reset-config",
        action="store_true",
        help="Purge all user-saved presets and restore factory defaults.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # 'scan' subcommand
    subparsers.add_parser("scan", parents=[common_parent], help="Scan vehicle connection, protocol, and active DTCs.")

    # 'monitor' subcommand
    monitor_parser = subparsers.add_parser("monitor", parents=[common_parent], help="Stream live telemetry and derived Hz.")
    monitor_parser.add_argument(
        "--pids",
        type=str,
        default="0C,0D,05,11,10,14",
        help="Comma-separated list of Mode 01 PIDs to poll (default: 0C,0D,05,11,10,14).",
    )
    monitor_parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of telemetry poll cycles (default: 1; use 0 for infinite).",
    )

    # 'enhanced' subcommand
    enh_parser = subparsers.add_parser(
        "enhanced",
        parents=[common_parent],
        help="Query manufacturer-specific enhanced parameters (Toyota, Honda, GM, Ford).",
    )
    enh_parser.add_argument(
        "manufacturer",
        choices=["toyota", "honda", "gm", "ford"],
        help="Target manufacturer name.",
    )

    # 'can-monitor' subcommand
    can_parser = subparsers.add_parser("can-monitor", parents=[common_parent], help="Capture and monitor raw CAN bus frames.")
    can_parser.add_argument(
        "--filter",
        dest="can_filter",
        type=str,
        default=None,
        help="Target CAN ID filter in hexadecimal (e.g. 7E8 or 201).",
    )
    can_parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of CAN frames to capture (default: 5).",
    )

    # 'pins' subcommand
    pin_parser = subparsers.add_parser("pins", parents=[common_parent], help="Display 16-pin connector map and adapter guidance.")
    pin_parser.add_argument(
        "manufacturer",
        nargs="?",
        default=None,
        choices=["toyota", "honda", "gm", "ford"],
        help="Optional manufacturer for brand-specific pin notes.",
    )

    # 'dtc' subcommand
    dtc_parser = subparsers.add_parser("dtc", parents=[common_parent], help="Inspect and clear Diagnostic Trouble Codes.")
    dtc_sub = dtc_parser.add_subparsers(dest="dtc_action")
    dtc_list = dtc_sub.add_parser("list", parents=[common_parent], help="List confirmed and pending trouble codes.")
    dtc_list.add_argument(
        "--mode",
        choices=["03", "07", "0A"],
        default="03",
        help="Service mode: '03' (Stored), '07' (Pending), '0A' (Permanent).",
    )
    dtc_sub.add_parser("clear", parents=[common_parent], help="Clear DTCs, freeze frames, and reset monitors (Mode 04).")

    # 'preset' subcommand
    preset_parser = subparsers.add_parser("preset", parents=[common_parent], help="Inspect and manage local YAML presets.")
    preset_sub = preset_parser.add_subparsers(dest="preset_action")
    preset_sub.add_parser("list", parents=[common_parent], help="List all locally available presets.")
    show_preset = preset_sub.add_parser("show", parents=[common_parent], help="Display the active preset configuration.")
    show_preset.add_argument("name", nargs="?", default="default", help="Preset name.")

    # 'serve' subcommand
    serve_parser = subparsers.add_parser("serve", help="Launch the local web interface on localhost.")
    serve_parser.add_argument(
        "--port",
        dest="serve_port",
        type=int,
        default=8080,
        help="Port number to bind (default: 8080).",
    )
    serve_parser.add_argument(
        "--host",
        dest="serve_host",
        type=str,
        default="127.0.0.1",
        help="Host interface to bind. Defaults strictly to 127.0.0.1 (localhost).",
    )
    serve_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically launch web browser on startup.",
    )

    args = parser.parse_args(argv)
    args.adapter = getattr(args, "adapter", None)
    args.host = getattr(args, "host", None)
    args.port = getattr(args, "port", None)
    args.preset = getattr(args, "preset", "default")
    args.quiet = getattr(args, "quiet", False)
    args.verbose = getattr(args, "verbose", False)
    args.json = getattr(args, "json", False)
    args.reset_config = getattr(args, "reset_config", False)

    # Handle global reset
    if args.reset_config:
        reset_all_configuration()
        if not args.quiet:
            sys.stderr.write("[jgobdii-reader] Local configuration reset to factory defaults.\n")
        return 0

    if not args.subcommand:
        parser.print_help(sys.stderr)
        return 2

    # Load active preset
    try:
        preset = load_preset(args.preset)
    except Exception as exc:
        sys.stderr.write(f"[jgobdii-reader] Error loading preset: {exc}\n")
        return 1

    # Resolve adapter settings
    adapter_type = args.adapter or preset.adapter_type
    host = args.host or preset.adapter_host
    port = args.port or preset.adapter_port
    channel = getattr(args, "channel", None) or getattr(preset, "socketcan_channel", "can0")
    vehicle_prof = get_vehicle_profile(preset.vehicle_domain)

    # Handler: serve (Lazy import to maintain sub-200ms CLI startup latency)
    if args.subcommand == "serve":
        from app.server import run_local_server
        run_local_server(
            port=args.serve_port,
            host=args.serve_host,
            open_browser=not getattr(args, "no_browser", False),
            no_browser=getattr(args, "no_browser", False),
        )
        return 0

    # Handler: preset
    if args.subcommand == "preset":
        if args.preset_action == "list":
            preset_files = list_presets()
            if args.json:
                sys.stdout.write(json.dumps({"presets": preset_files}, indent=2) + "\n")
            else:
                for p in preset_files:
                    sys.stdout.write(f"- {p}\n")
            return 0

        if args.preset_action == "show":
            target_name = args.name or args.preset
            preset_obj = load_preset(target_name)
            if args.json:
                sys.stdout.write(json.dumps(preset_obj.model_dump(), indent=2) + "\n")
            else:
                sys.stdout.write(yaml.dump(preset_obj.model_dump(), sort_keys=False) + "\n")
            return 0

    # Handler: pins
    if args.subcommand == "pins":
        mfg_enum = Manufacturer(args.manufacturer) if args.manufacturer else None
        pin_data = get_pinout_advisor(mfg_enum)
        if args.json:
            sys.stdout.write(json.dumps({"pinout": pin_data}, indent=2) + "\n")
        else:
            sys.stdout.write("SAE J1962 16-Pin Connector Map & Adapter Guidance:\n")
            for p in pin_data:
                tag = "STANDARD" if p["is_standard"] else "VENDOR"
                sys.stdout.write(f"Pin {p['pin']:2d} [{tag:8s}] {p['name']:20s} - {p['description']}\n")
                if p["manufacturer_note"]:
                    sys.stdout.write(f"         Note: {p['manufacturer_note']}\n")
        return 0

    # Instantiate adapter
    adapter = get_adapter(
        adapter_type=adapter_type,
        host=host,
        port=port,
        protocol_cmd=vehicle_prof.protocol_cmd,
        device_name=channel,
    )

    async def _async_run() -> int:
        if not args.quiet:
            sys.stderr.write(
                f"[jgobdii-reader] Connecting via {adapter.get_capabilities().adapter_type}...\n"
            )

        connected = await adapter.connect()
        if not connected:
            sys.stderr.write(
                f"[jgobdii-reader] Failed to connect to diagnostic adapter ({adapter_type}).\n"
            )
            return 1

        try:
            db = DtcDatabase()

            # Command: scan
            if args.subcommand == "scan":
                status = adapter.get_status()
                capabilities = adapter.get_capabilities()
                stored_codes = await adapter.query_dtcs("03")
                pending_codes = await adapter.query_dtcs("07")

                enriched_stored = [db.lookup_dtc(c) for c in stored_codes]
                clusters = db.correlate_clusters(stored_codes + pending_codes)

                scan_result = {
                    "status": "success",
                    "adapter": status,
                    "capabilities": {
                        "can_high_speed": capabilities.can_high_speed,
                        "can_medium_speed": capabilities.can_medium_speed,
                        "single_wire_can": capabilities.single_wire_can,
                        "multi_channel": capabilities.multi_channel_parallel,
                    },
                    "vehicle_profile": vehicle_prof.display_name,
                    "stored_dtcs": [
                        {
                            "code": d.code,
                            "system": d.system,
                            "description": d.description,
                            "cluster": d.correlated_cluster,
                        }
                        for d in enriched_stored
                    ],
                    "pending_dtcs": pending_codes,
                    "failure_clusters": [c.get("name") for c in clusters],
                }

                if args.json:
                    sys.stdout.write(json.dumps(scan_result, indent=2) + "\n")
                else:
                    sys.stdout.write(f"Vehicle: {vehicle_prof.display_name}\n")
                    sys.stdout.write(f"Protocol: {status['protocol']}\n")
                    sys.stdout.write(f"Battery: {status['battery_voltage']}\n")
                    sys.stdout.write(f"Stored Fault Codes: {len(stored_codes)}\n")
                    for d in enriched_stored:
                        sys.stdout.write(f"  - {d.code}: {d.description} [{d.system}]\n")
                    if clusters:
                        sys.stdout.write("\nCorrelated Failure Clusters:\n")
                        for cl in clusters:
                            sys.stdout.write(f"  ! {cl.get('name')}: {cl.get('physics_and_symptoms')}\n")

                return 0

            # Command: monitor
            if args.subcommand == "monitor":
                pids = [p.strip().upper() for p in args.pids.split(",") if p.strip()]
                cycle = 0
                max_cycles = args.count

                while max_cycles == 0 or cycle < max_cycles:
                    telemetry = {}
                    for pid in pids:
                        data_bytes = await adapter.query_pid("01", pid)
                        val = decode_pid(pid, data_bytes) if data_bytes else None
                        telemetry[pid] = val

                    # Calculate derived VSS frequency
                    speed = telemetry.get("0D")
                    if speed is not None:
                        vss_hz = calculate_vss_frequency(float(speed), vehicle_prof.vss_pulses_per_mile)
                        telemetry["VSS_Hz"] = vss_hz

                    if args.json:
                        sys.stdout.write(json.dumps(telemetry) + "\n")
                        sys.stdout.flush()
                    else:
                        out_line = " | ".join(f"{k}: {v}" for k, v in telemetry.items())
                        sys.stdout.write(out_line + "\n")

                    cycle += 1
                    if max_cycles == 0 or cycle < max_cycles:
                        await asyncio.sleep(float(preset.poll_interval_ms) / 1000.0)

                return 0

            # Command: enhanced
            if args.subcommand == "enhanced":
                mfg_enum = Manufacturer(args.manufacturer)
                params = get_manufacturer_parameters(mfg_enum)
                results = []

                for param in params:
                    payload = await adapter.query_enhanced(param.header, param.service_mode, param.pid_hex)
                    decoded_val = param.decode(payload) if payload else None
                    results.append({
                        "id": param.id,
                        "name": param.name,
                        "header": param.header,
                        "value": decoded_val,
                        "unit": param.unit,
                        "description": param.description,
                    })

                if args.json:
                    sys.stdout.write(json.dumps({"manufacturer": args.manufacturer, "parameters": results}, indent=2) + "\n")
                else:
                    sys.stdout.write(f"Enhanced Telemetry for {args.manufacturer.upper()}:\n")
                    for r in results:
                        val_str = f"{r['value']} {r['unit']}" if r["value"] is not None else "N/A"
                        sys.stdout.write(f"  [{r['header']}] {r['name']:35s}: {val_str}\n")

                return 0

            # Command: can-monitor
            if args.subcommand == "can-monitor":
                if not args.quiet:
                    sys.stderr.write(f"[jgobdii-reader] Capturing {args.count} CAN frames...\n")

                frames = await adapter.capture_can_frames(
                    count=args.count,
                    filter_id=args.can_filter,
                )

                if args.json:
                    out = [f.to_dict() for f in frames]
                    sys.stdout.write(json.dumps({"frames": out}, indent=2) + "\n")
                else:
                    sys.stdout.write(f"{'CAN ID':8s} {'EXT':5s} {'DLC':4s} {'DATA (HEX)'}\n")
                    sys.stdout.write("-" * 50 + "\n")
                    for f in frames:
                        ext_str = "YES" if f.is_extended else "NO"
                        data_hex = " ".join(f"{b:02X}" for b in f.data)
                        sys.stdout.write(f"{f.can_id_hex:8s} {ext_str:5s} {f.dlc:4d} {data_hex}\n")

                return 0

            # Command: dtc
            if args.subcommand == "dtc":
                if args.dtc_action == "clear":
                    success = await adapter.clear_dtcs()
                    if success:
                        if args.json:
                            sys.stdout.write(json.dumps({"status": "cleared"}) + "\n")
                        else:
                            sys.stdout.write("Diagnostic Trouble Codes and readiness monitors cleared successfully.\n")
                        return 0
                    sys.stderr.write("[jgobdii-reader] Vehicle rejected DTC clear command.\n")
                    return 1

                # Default dtc list
                mode = getattr(args, "mode", "03")
                codes = await adapter.query_dtcs(mode)
                enriched = [db.lookup_dtc(c) for c in codes]
                clusters = db.correlate_clusters(codes)

                if args.json:
                    data = {
                        "mode": mode,
                        "count": len(codes),
                        "codes": [
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
                        "clusters": [c.get("name") for c in clusters],
                    }
                    sys.stdout.write(json.dumps(data, indent=2) + "\n")
                else:
                    sys.stdout.write(f"Mode {mode} DTCs Reported: {len(codes)}\n")
                    for d in enriched:
                        sys.stdout.write(f"- {d.code}: {d.description}\n")
                        sys.stdout.write(f"  System: {d.system}\n")
                        if d.correlated_cluster:
                            sys.stdout.write(f"  Cluster: {d.correlated_cluster}\n")

                return 0

            return 0
        finally:
            await adapter.disconnect()

    return asyncio.run(_async_run())


if __name__ == "__main__":
    sys.exit(main())
