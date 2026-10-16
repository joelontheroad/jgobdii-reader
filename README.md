# jgobdii-reader

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Standards: 12-Category](https://img.shields.io/badge/Standards-Compliant-emerald.svg)](https://github.com/joelontheroad/Software-standards)

**jgOBDII-Reader** is a computer-based OBD-II telemetry and diagnostic reader supporting **ELM327 Wi-Fi** dongles, **J2534 Pass-Thru USB** cables, and offline simulation. It provides standard OBD-II PID telemetry, manufacturer-enhanced parameters (Toyota/Lexus, Honda/Acura, GM, Ford), raw CAN bus sniffing, and physical 16-pin connector guidance across cars, light trucks, motorcycles, boats, and ATVs.

This project strictly adheres to all 12 Open Source Software Standards:
- **Zero Telemetry & Local Data**: Presets saved locally in `$XDG_CONFIG_HOME/jgobdii-reader/` as human-readable YAML.
- **GNU AGPL-3.0-or-later**: Free and open source software with Section 13 notice in CLI and Web UI.
- **Strict Localhost Security**: Web servers default strictly to `127.0.0.1` with ephemeral token authentication and W3C CSP headers.
- **Stream Separation**: Machine-readable data/JSON on `stdout`, diagnostics and status logs on `stderr`.
- **Zero External CDNs**: Web dashboard bundles all assets locally with zero external network requests.

---

## 3-Step Quickstart

Run these commands from the root directory of this project:

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies in editable mode
pip install -e ".[dev,web]"

# 3. Run vehicle diagnostic scan (using live adapter or offline mock)
jgobdii-reader scan --adapter mock
```

---

## How to Run the Program

All commands should be executed from the project root directory (`/mnt/joelg-docs/Personal/Software Projects/ODBDII Reader`).

### Activating the Virtual Environment

Before running `jgobdii-reader` commands, activate the Python virtual environment:

#### Linux & macOS (bash / zsh)
```bash
source .venv/bin/activate
```

#### Windows (PowerShell)
```powershell
.venv\Scripts\Activate.ps1
```

#### Windows (Command Prompt `cmd.exe`)
```cmd
.venv\Scripts\activate.bat
```

> **How to verify it is active:**  
> Once activated, your terminal prompt will display the `(.venv)` prefix:  
> `(.venv) joelg@pop-os:/mnt/joelg-docs/.../ODBDII Reader$ `  
>
> **If the virtual environment does not exist yet:**  
> Create it first with `python3 -m venv .venv` and install dependencies with `pip install -e ".[dev,web]"`.  
>
> **To exit the virtual environment when finished:**  
> Simply type `deactivate`.  
>
> **Alternative (run directly without activation):**  
> You can also invoke the virtual environment's binary directly without activating:  
> `./.venv/bin/jgobdii-reader serve --port 8080`

### 1. Running the Interactive Web Dashboard (Recommended)

To start the local web application with the digital oscilloscope, multi-channel waveforms, interactive 16-pin connector map, OEM diagnostics, fault injector, and reference hub:

```bash
# With virtual environment activated:
jgobdii-reader serve --port 8080

# Or via Python module directly:
python3 -m app.cli serve --port 8080
```

> **Automatic Browser Launch**: When started, the server automatically opens your default web browser to the secure local dashboard.
> **Clickable Terminal URL**: The terminal displays a clickable link with your one-time cryptographically random authentication launch token:
> ```text
> [*] Open dashboard in browser:
>     http://127.0.0.1:8080/?token=0123456789abcdef0123456789abcdef...
> ```

### 2. Running CLI Diagnostic Commands

`jgobdii-reader` provides full-featured command-line diagnostics:

```bash
# Run full ECU vehicle scan (offline mock simulator)
jgobdii-reader scan --adapter mock

# Run ECU vehicle scan via ELM327 Wi-Fi dongle (default: 192.168.0.10:35000)
jgobdii-reader scan --adapter elm327 --host 192.168.0.10 --port 35000

# Stream live PID telemetry (RPM, Speed, Coolant, Throttle)
jgobdii-reader monitor --adapter mock --pids 0C,0D,05,11 --count 20

# Query manufacturer-specific enhanced parameters (toyota, honda, gm, ford)
jgobdii-reader enhanced toyota --adapter mock

# Sniff live high-speed CAN bus packets (ISO 15765-4)
jgobdii-reader can-monitor --adapter mock --filter 7E8 --count 15

# Inspect active Diagnostic Trouble Codes (Mode 03 confirmed faults)
jgobdii-reader dtc list --adapter mock --mode 03

# Clear trouble codes, freeze frames, and reset monitors (Mode 04)
jgobdii-reader dtc clear --adapter mock

# Output machine-readable JSON to stdout (logs diverted to stderr)
jgobdii-reader scan --adapter mock --json
```

### 3. Running Directly Without Installation (Development Mode)

If you haven't run `pip install -e .` yet or wish to run directly against the source code, set `PYTHONPATH=src`:

```bash
# Run web server directly from source
PYTHONPATH=src python3 -m app.cli serve

# Run diagnostic scan directly from source
PYTHONPATH=src python3 -m app.cli scan --adapter mock
```

> **Troubleshooting `ModuleNotFoundError: No module named 'app'`**:  
> If you encounter this error, either activate the virtual environment where the package is installed (`source .venv/bin/activate`), or prepend `PYTHONPATH=src` to your command so Python can resolve the source directory.

---

## Supported Interfaces & Adapters

- **Linux SocketCAN**: Native Linux kernel network sockets (`AF_CAN`) interfacing with physical USB-to-CAN hardware (`can0`, `slcan0`) or virtual loopback devices (`vcan0`) at wire-speed without UART buffer overflow risks.
- **J2534 Pass-Thru USB Cables**: Multi-channel access, automated pin-multiplexing (Ford MS-CAN, GM SWCAN), and high-throughput logging.
- **ELM327 Wi-Fi Dongles**: Standard TCP socket communication (`192.168.0.10:35000` or local `127.0.0.1:35000`).
- **In-Memory Mock Adapter**: Deterministic, offline simulation for test suites and development.

### Recommended SocketCAN Hardware

For users seeking high-performance, real-time CAN bus telemetry and raw packet sniffing, the following hardware adapters are recommended:

| Tier | Hardware Device | Approximate Price | Linux Driver / Protocol | Notes & Recommendations |
|---|---|---|---|---|
| **Best Budget / Open Source** | **CANable 2.0 / Candlelight** | $15 – $25 | Native Linux `gs_usb` | **Top recommendation.** 100% open-source hardware. Flashed with Candlelight firmware, it registers directly as native `can0` in Linux without vendor drivers. |
| **Budget Serial Bridge** | **InnoMaker USB2CAN / slcan** | $30 – $40 | `slcan` / kernel serial | USB-to-CAN bridge supporting 10 kbps to 1 Mbps. Configured via `slcand` daemon. |
| **Professional / Industrial** | **PEAK-System PCAN-USB (or FD)** | $200 – $250 | Native Linux `peak_usb` | The industry standard for automotive Tier-1 engineering. Opto-isolated, rock-solid kernel support. |
| **Commercial Enterprise** | **Kvaser Leaf Light v2** | $300+ | Native Linux `kvaser_usb` | High-precision diagnostic adapter widely used in OEM calibration suites. |
| **Embedded / Raspberry Pi** | **Waveshare 2-CH CAN HAT** | $15 – $20 | SPI `mcp251x` | Dual-channel MCP2515/MCP2518 controller HAT for Raspberry Pi diagnostic setups. |

#### Zero-Hardware Testing with Virtual CAN (`vcan0`)

You can test SocketCAN functionality without physical cables using Linux's built-in virtual CAN kernel module:

```bash
# Load vcan kernel module
sudo modprobe vcan

# Create and bring up virtual CAN interface vcan0
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0

# Verify interface is active
ip link show vcan0
```

---

## Supported Diagnostic Protocols (10 Standards)

`jgobdii-reader` automatically detects and supports 10 automotive communication protocols:

1. **Automatic Protocol Detection (`AUTO`)**: Auto-negotiates the optimal vehicle bus protocol.
2. **ISO 15765-4 CAN (11-bit ID, 500 kbaud)**: High-speed emissions CAN bus on all 2008+ modern vehicles.
3. **ISO 15765-4 CAN (29-bit ID, 500 kbaud)**: Extended-ID CAN bus on commercial & select passenger vehicles.
4. **ISO 15765-4 CAN (11-bit ID, 250 kbaud)**: Medium-speed bus common on Ford and GM platforms.
5. **ISO 15765-4 CAN (29-bit ID, 250 kbaud)**: Extended-ID 250 kbaud bus for heavy equipment and marine craft.
6. **ISO 14230-4 KWP2000 (Fast Init, 10.4 kbaud)**: K-Line fast init on 2000-2007 European & Asian models.
7. **ISO 14230-4 KWP2000 (5-baud Init, 10.4 kbaud)**: K-Line 5-baud initialization protocol.
8. **ISO 9141-2 (5-baud Init, 10.4 kbaud)**: Legacy K-Line protocol on pre-2004 Chrysler and European vehicles.
9. **SAE J1850 PWM (41.6 kbaud)**: Ford pulse-width modulated differential bus (Pins 2 & 10).
10. **SAE J1850 VPW (10.4 kbaud)**: General Motors variable pulse-width single-wire bus (Pin 2).

---

## CLI Subcommands Reference

| Subcommand | Description | Example |
|---|---|---|
| `scan` | Detect vehicle protocol, battery voltage, active DTCs, and failure clusters | `jgobdii-reader scan --adapter socketcan --channel can0` |
| `monitor` | Stream live telemetry and calculate derived VSS frequency (Hz) | `jgobdii-reader monitor --pids 0C,0D,05 --count 5` |
| `enhanced` | Query OEM-enhanced parameters (Toyota, Honda, GM, Ford) | `jgobdii-reader enhanced toyota` |
| `can-monitor` | Sniff and filter raw CAN bus frames (`ID`, `DLC`, `DATA`) | `jgobdii-reader can-monitor --adapter socketcan --count 10` |
| `pins` | Display SAE J1962 16-pin connector map and OEM pin notes | `jgobdii-reader pins ford` |
| `dtc list` | Inspect confirmed, pending, or permanent diagnostic trouble codes | `jgobdii-reader dtc list --mode 03 --json` |
| `dtc clear` | Clear DTCs, freeze frames, and reset readiness monitors | `jgobdii-reader dtc clear` |
| `preset show` | Display active YAML configuration preset | `jgobdii-reader preset show --json` |
| `serve` | Launch local web interface on `127.0.0.1:8080` with launch token | `jgobdii-reader serve --port 8080` |

### Global Flags

- `--adapter {elm327,j2534,socketcan,mock}`: Select diagnostic interface adapter.
- `--channel <INTERFACE>`: SocketCAN network interface name (default: `can0`) or J2534 device identifier.
- `--host <IP>`: Specify network adapter host address (default: `192.168.0.10`).
- `--port <PORT>`: Specify network adapter TCP port (default: `35000`).
- `--preset <NAME>`: Load a saved YAML configuration preset.
- `--json`: Output machine-readable JSON to `stdout` (diverting logs to `stderr`).
- `-q, --quiet`: Suppress diagnostic messages.
- `--verbose`: Emit detailed communication logs to `stderr`.
- `--reset-config`: Purge local configuration and restore factory defaults.

---

## Web Dashboard & Digital Oscilloscope

Launch the authenticated web dashboard:
```bash
jgobdii-reader serve
```
The terminal prints a one-time launch token link:
```text
http://127.0.0.1:8080/?token=abc123...
```

Features included in the web interface:
- **Live Data & Multi-Channel Oscilloscopes (Mode 01)**:
  - *Searchable Categorized Sensor Palette Modal*: Browse 50+ Mode 01 diagnostic parameters with instant typeahead search, category filter pills (`All`, `⭐ Supported Only`, `Engine`, `Fuel/Air`, `Temperatures`, `Speed/Timing`, `Oxygen Sensors`, `Electrical`), live vehicle support badges (`🟢 Supported` / `⚪ Unsupported`), and one-click assignment to any oscilloscope channel or the live dashboard.
  - *Multi-Channel Digital Oscilloscopes*: Simultaneously render up to 5 live signal oscilloscopes with independent sweeps, distinct traces, and 60 FPS Canvas rendering.
  - *Customizable Dashboard Gauge Cards*: Select and toggle which telemetry cards are displayed from all standardized Mode 01 PIDs with quick presets.
- **Diagnostic Trouble Codes & Complete OBD-II Modes**:
  - *I/M Readiness Monitors (Mode 01 PID 01)*: Live inspection badges for MIL lamp status, Misfire, Fuel System, Comprehensive Components, Catalyst, Heated Catalyst, EVAP, Secondary Air, Oxygen Sensor, and EGR/VVT.
  - *Freeze Frame Snapshot & Live Delta Comparison (Mode 02)*: Diagnostic telemetry frozen at the exact millisecond a fault code was recorded compared side-by-side with current live telemetry values.
  - *Stored & Pending Fault Codes (Modes 03 & 07)*: Confirmed emissions DTC readouts and current drive-cycle pending codes with correlated failure clusters.
  - *Safe DTC Erasure (Mode 04)*: Clear DTCs and reset monitors with an accessible confirmation safety modal explaining emissions drive-cycle reset implications.
  - *Oxygen Sensor Monitoring Test Results (Mode 05)*: Query pre-CAN diagnostic test IDs (TID 01–0A) for sensor switch thresholds, reaction times, and min/max voltages.
  - *On-Board Component Monitoring (Mode 06)*: Test results for catalytic converter oxygen storage, O2 sensor switch times, and EVAP vacuum decay.
  - *Vehicle Identification & Calibration (Mode 09)*: Readout of 17-character VIN, Calibration ID (CALID), and CVN.
- **Mock Simulator Fault Injection Console**: Dynamically inject custom trouble codes or realistic failure clusters (System Lean & Misfire, Catalyst, MAF Sensor, EVAP Gross Leak) into Mode 03, 07, or 0A to thoroughly test ECU fault detection, cluster correlation, and clearing.
- **Reference Hub**:
  - *Standard SAE J2012 DTC Directory*: Comprehensive 9,417 trouble code database with Powertrain (P), Chassis (C), Body (B), and Network (U) system filters, live vehicle support badges, and a `Show Only Currently Supported DTCs` toggle. Default active tab.
  - *Manufacturer-Specific DTCs*: 31,272 OEM fault code definitions and protocol architecture notes across 11 major automakers (Toyota/Lexus, BMW/Mini, Volkswagen/Audi, Ford, GM, Honda/Acura, Nissan/Infiniti, Chrysler/Jeep, Mitsubishi, Fiat, Alfa Romeo) with live make-matching support filters.
  - *CAN Bus Technical Architecture*: Complete physical layer voltage specs, bus topologies, classical frame anatomy, and ISO 15765-4 diagnostic addressing.
  - *Interactive DTC Decoder*: Deconstruct any 5-character fault code into its 4 structural tokens (System, Code Type, Subsystem, Fault Index) with educational guide based on `obd-codes.com`.
  - *16-Pin Connector Map*: Interactive SVG diagram with pin-by-pin hardware & adapter guidance (positioned on the far right).
- **Hardware Cable & Interface Detection**: Automatic detection of USB-to-CAN cables (CANable, PEAK, Kvaser) and network interfaces, dynamically greying out SocketCAN choices when hardware is disconnected.
- **Settings & Presets**: Load saved presets from a disk dropdown, detect unsaved changes visually (`* Unsaved modifications`), and import/export preset files using standard system file dialogs.

---

## Configuration & Presets

Configuration and presets reside strictly on the local filesystem using XDG base directories:
- **Linux/macOS**: `~/.config/jgobdii-reader/default.yaml`
- **Windows**: `%APPDATA%\jgobdii-reader\default.yaml`

Example preset (`~/.config/jgobdii-reader/default.yaml`):
```yaml
name: default
theme: auto
max_items: 50
enable_cache: true
adapter_type: elm327
adapter_host: 192.168.0.10
adapter_port: 35000
vehicle_domain: car
manufacturer: generic
vss_pulses_per_mile: 4000
poll_interval_ms: 200
```

---

## Security Policy

See [`SECURITY.md`](SECURITY.md) for private vulnerability reporting.

---

## License

Licensed under the **GNU Affero General Public License v3.0 or later** (see [`LICENSE`](LICENSE)).
Source repository: [https://github.com/joelontheroad/jgobdii-reader](https://github.com/joelontheroad/jgobdii-reader)
