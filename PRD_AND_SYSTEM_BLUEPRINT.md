# Product Requirements Document (PRD) & Systems Engineering Blueprint
**Project:** Autonomous OBD-II Diagnostic Tool & Telemetry Engine  
**Document Version:** 1.0.0  
**Target Platform:** Linux / macOS / Windows (Python 3.11+ Core Engine + WebSocket Telemetry UI)  
**Author:** AI Systems Architect (Reporting to Product Manager)

---

## 1. Executive Summary & Goals

This document establishes the functional requirements, system architecture, open-source data assets, sensor telemetry boundaries, and software simulation framework for an OBD-II diagnostic application connecting via an ELM327 Wi-Fi adapter.

### Primary Objectives
1. **Diagnostic Trouble Code (DTC) Engine:** Automated scanning, decoding, severity categorization, and clearing of SAE J2012 DTCs (Modes `03`, `07`, `0A`) enriched by an open-source database of fault definitions, symptoms, and potential causes.
2. **Live Telemetry & Digital Oscilloscope Dashboard:** Real-time polling, decoding, and oscilloscope-style waveform visualization for critical engine and vehicle sensors (O2 sensor voltages, MAF, RPM, Throttle, Coolant, and Vehicle Speed Sensor derived frequency).
3. **Hardware-Accurate Software Simulator:** Embedded Wi-Fi TCP simulator listening on `0.0.0.0:35000` (or `127.0.0.1:35000` / `192.168.0.10:35000`) emulating both modern CAN and legacy ISO 9141-2 vehicle profiles (specifically targeting a 2000 Toyota Camry V6).

---

## 2. Sensor Troubleshooting: Physical vs. OBD-II Boundary Analysis

The Product Manager requested the ability to troubleshoot sensors (e.g., Vehicle Speed Sensor generating 0–5V pulses) and view their frequency in Hertz (Hz) in an oscilloscope-style interface. 

It is vital to distinguish between **Physical Electrical Probing** and **OBD-II Protocol Telemetry**:

```
+---------------------------------------------------------------------------------------------------+
| PHYSICAL VEHICLE LAYER (Under the Hood / Transmission)                                            |
| [ VSS Sensor ] ===== (Analog Pulse Train: 0-5V AC/Square Wave, 0-250 Hz) =====> [ Vehicle ECU ]   |
|         |                                                                               |         |
|         x--- [Hardware Lab Scope (PicoScope/Hantek/ADC)]                                |         |
|              (Measures raw microsecond electrical pulses directly from copper wire)     |         |
+-----------------------------------------------------------------------------------------|---------+
                                                                                          | Digitize
+-----------------------------------------------------------------------------------------v---------+
| DIAGNOSTIC SERIAL BUS (SAE J1962 Port / Pin 7 K-Line or Pins 6/14 CAN)                            |
| [ Vehicle ECU ] ===== (Mode 01 PID 0D: e.g. "41 0D 3C" = 60 km/h) =====> [ ELM327 Wi-Fi Adapter ]|
|                                                                                         |         |
+-----------------------------------------------------------------------------------------|---------+
                                                                                          | TCP:35000
+-----------------------------------------------------------------------------------------v---------+
| CLIENT APPLICATION (Our Software)                                                                 |
| [ Software Oscilloscope ]: Plots sampled PID telemetry + Calculates Derived Sensor Frequency (Hz) |
+---------------------------------------------------------------------------------------------------+
```

### 2.1 The Two Scope Modes in Automotive Diagnostics
1. **Physical Lab Oscilloscope (Hardware Probe):**
   * *How it works:* Connects physical probes directly across the sensor signal wire and ground.
   * *Resolution:* Mega-samples per second (MS/s), true 0–5V analog waveform, detects faulty ground reference, clipping, damaged reluctor wheel teeth, or noise spikes.
   * *OBD-II Limitation:* The ELM327 is plugged into the OBD-II port under the steering column. It has **no electrical wire connection** to the raw VSS sensor; it only communicates with the ECU over digital serial lines.
2. **OBD-II Digital Scope & Derived Frequency Analyzer (Our Application):**
   * *How it works:* Our software polls digital sensor PIDs from the ECU, renders them on a high-speed time-series oscilloscope display (voltage, sweep time, trigger line, cursors), and **calculates the derived sensor frequency (Hz)** using vehicle driveline mathematics.
   * *Toyota VSS Formula:* A standard Toyota Vehicle Speed Sensor generates 4 pulses per revolution of the speedometer driven gear (or 4,000 pulses per mile).
     $$\text{Speed (mph)} = \text{Speed (km/h)} \times 0.621371$$
     $$\text{Frequency (Hz)} = \frac{\text{Speed (mph)} \times 4000 \text{ pulses/mile}}{3600 \text{ seconds/hour}} \approx \text{Speed (mph)} \times 1.111 \text{ Hz}$$
     *At 30 mph: $\approx 33.3 \text{ Hz}$ | At 60 mph: $\approx 66.7 \text{ Hz}$*
   * *True Voltage Sensors via OBD-II:* Oxygen Sensors (Mode 01, PIDs `0x14`–`0x1B`) report real, measured analog voltages ($0.000\text{V} - 1.275\text{V}$) directly digitized by the ECU's internal ADC, making them ideal for oscilloscope-style waveform analysis!

---

## 3. Target Vehicle Profile: 2000 Toyota Camry V6 (1MZ-FE)

| Vehicle Attribute | Specification | Engineering Impact |
|:---|:---|:---|
| **Engine** | 3.0L V6 24V DOHC (1MZ-FE) | Toyota Denso Engine Control Unit |
| **OBD-II Protocol** | **ISO 9141-2** (Slow 5-baud init) | **Does NOT use CAN bus.** Do not issue `ATSP6`. Use `ATSP3` or `ATSP0` (Auto). |
| **Physical Pinout** | Pins 4 & 5 (Gnd), Pin 7 (K-Line), Pin 16 (+12V) | Pins 6 and 14 (CAN) are unpopulated in the connector. |
| **Bus Baud Rate** | 10.4 kbps | Querying each PID takes ~100–180ms. Maximum polling throughput is ~6–9 samples/sec. |
| **Supported PIDs** | PIDs `0x00`, `0x01`, `0x03`, `0x04`, `0x05`, `0x06`, `0x07`, `0x0C`, `0x0D`, `0x0E`, `0x0F`, `0x11`, `0x13`, `0x14`, `0x15` | Core emissions telemetry available (RPM, Speed, Coolant, Load, Timing, O2 Volts). |

---

## 4. Open-Source Data Repositories & Reference Frameworks

### 4.1 Diagnostic Trouble Code (DTC) Databases

| Repository / Project | License | Format | Content & Strengths |
|:---|:---|:---|:---|
| **[`mytrile/obd-trouble-codes`](https://github.com/mytrile/obd-trouble-codes)** | MIT | JSON, CSV, SQLite | 5,000+ SAE J2012 codes (Powertrain, Body, Chassis, Network). Includes human descriptions, common failure symptoms, and repair causes. |
| **[`todrobbins/dtcdb`](https://github.com/todrobbins/dtcdb)** | CC0 / Public Domain | CSV | Clean normalized CSV schemas of generic SAE J2012 DTCs and parameter IDs. |
| **[`Automotive-9/dtc-codes`](https://github.com/Automotive-9/dtc-codes)** | Open Source | JSON | Manufacturer-specific DTCs (Toyota, Lexus, Ford, GM) for proprietary P1xxx codes. |
| **[`open-obd/db`](https://github.com/open-obd/db)** | Apache-2.0 | YAML / JSON | Community repository for parameter scaling formulas and multi-lingual fault descriptions. |

### 4.2 OBD-II Simulators & Reference Implementations

| Project | Language | Architecture | Relevance to Our Project |
|:---|:---|:---|:---|
| **[`Ircama/ELM327-emulator`](https://github.com/Ircama/ELM327-emulator)** | Python 3 | Async / Multi-ECU / TCP | Reference for handling complex ELM327 edge cases, multi-frame ISO-TP, and AT timing quirks. |
| **[`obdgpslogger / obdsim`](https://github.com/obdgpslogger/obdgpslogger)** | C | POSIX / Socket | Classic benchmark OBD simulator with mathematical sensor generators. |
| **[`brendan-w/python-OBD`](https://github.com/brendan-w/python-OBD)** | Python | Sync / Async | Comprehensive catalog of OBD-II PIDs, bitmasks, and formula decoding engines. |

---

## 5. Software Architecture & System Design

To satisfy both the Diagnostic Tool and the High-Speed Oscilloscope Dashboard, the system is partitioned into decoupled layers:

```
+-------------------------------------------------------------------------------------------------+
|                                    PRESENTATION LAYER                                           |
|  [ Web UI / HTML5 Canvas Oscilloscope ]     [ Diagnostic DTC Manager ]     [ PID Dashboard ]    |
|  - 60 FPS Sweep-chart waveform              - Confirmed / Pending DTCs    - Digital gauges      |
|  - Cursors & derived Hz measurement         - Freeze-frame inspector      - Min/Max/Avg metrics |
+-------------------------------------------------------------------------------------------------+
                                               |
                                     WebSocket / JSON API
                                               v
+-------------------------------------------------------------------------------------------------+
|                                    APPLICATION ENGINE LAYER                                     |
|  [ DTC Engine & Lookup ]                     [ Telemetry Streamer ]       [ Vehicle Math ]      |
|  - Query Modes 03, 07, 0A                    - Round-robin PID scheduler  - Sensor frequency    |
|  - Match against offline JSON DB             - Decodes scaled engineering   calculator (Hz)     |
|  - Mode 04 Clear execution                     units (RPM, km/h, Volts)   - Unit conversions    |
+-------------------------------------------------------------------------------------------------+
                                               |
                                         Internal Queue
                                               v
+-------------------------------------------------------------------------------------------------+
|                                  ELM327 PROTOCOL SESSION LAYER                                  |
|  - State Machine: DISCONNECTED -> CONNECTING -> INITIALIZING -> READY -> BUS_ERROR              |
|  - AT Command Sequencer: ATZ -> ATE0 -> ATL0 -> ATS0 -> ATH0 -> ATSP0                           |
|  - Prompt Parser: Non-blocking ASCII chunk collector terminating on '>'                         |
|  - Transport Switch: Physical Wi-Fi Socket vs. Local Simulation Socket                          |
+-------------------------------------------------------------------------------------------------+
                                               |
                                        Async TCP Socket
                                               v
+-------------------------------------------------------------------------------------------------+
|                                     TRANSPORT / HARDWARE LAYER                                  |
|     Physical Adapter (192.168.0.10:35000)      OR      Local Simulator (127.0.0.1:35000)        |
+-------------------------------------------------------------------------------------------------+
```

---

## 6. Coding Standards & Agent Guidelines

For any software agents implementing this repository, the following standards are mandatory:

1. **Language & Environment:** Modern Python (3.11+) with full static typing (`mypy` compliant).
2. **Asynchronous I/O:** All network sockets and serial communications MUST use `asyncio` streams (`asyncio.open_connection`) to prevent blocking the UI or telemetry scheduler.
3. **Decoupled Business Logic:**
   * PID parsing functions must be pure, stateless functions taking hex strings or raw bytes and returning typed domain dataclasses.
   * DTC lookup must fall back gracefully to raw hexadecimal representations if a specific proprietary code is missing from the database.
4. **Resilient Network Handling:**
   * Handshake timeouts, vehicle power drops, and adapter disconnects must trigger automated exponential backoff reconnect routines.
   * Support an environment flag or configuration switch: `OBD_HOST` (default `192.168.0.10`), `OBD_PORT` (default `35000`), `SIMULATION_MODE` (default `False`).
5. **Testing & Test Coverage:**
   * All PID decoders, DTC parsers, and command encoders must have 100% unit test coverage via `pytest`.
   * Integration tests must execute against the built-in mock simulator without requiring live vehicle hardware.
