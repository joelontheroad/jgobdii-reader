# OBD-II & ELM327 Wi-Fi Architecture & Technical Specification
**Document ID:** SPEC-OBD2-ELM327-001  
**Version:** 1.0.0  
**Target Audience:** Autonomous Software Engineering Agents & Systems Architects  
**Purpose:** Machine- and human-ingestible technical baseline for implementing an OBD-II diagnostic reader over ELM327 Wi-Fi.

---

## 1. Regulatory Context & Legal Foundations

### 1.1 United States OBD-II Mandate
* **Statutory Basis:** United States Clean Air Act Amendments (CAAA) of 1990 (42 U.S.C. § 7521).
* **Federal Regulation:** EPA Regulations codified in **40 CFR Part 86, Subpart S** (specifically 40 CFR § 86.1806-01 through § 86.1806-17).
* **California State Regulation:** California Air Resources Board (CARB) OBD-II Regulations codified in **Title 13, California Code of Regulations (CCR) § 1968.1 and § 1968.2**.
* **Effective Date:** Required on all light-duty passenger cars and light-duty trucks sold in the United States starting in **Model Year 1996 (MY1996)**.
* **CAN Mandate:** Starting in **Model Year 2008**, EPA and CARB mandated that all light-duty vehicles sold in the US must implement the Controller Area Network (CAN) bus standard (**ISO 15765-4**) as the universal diagnostic protocol (40 CFR § 86.1806-05).

---

## 2. Core OBD-II Standards Hierarchy

The OBD-II ecosystem is defined by joint standards from the Society of Automotive Engineers (**SAE**) and the International Organization for Standardization (**ISO**):

```
+-------------------------------------------------------------------------------+
|                       Application Layer: Diagnostic Services                  |
|          SAE J1979 / ISO 15031-5 (Classic OBD)  |  SAE J1979-2 (OBD on UDS)   |
|          SAE J2012 / ISO 15031-6 (Diagnostic Trouble Codes - DTCs)            |
+-------------------------------------------------------------------------------+
|                     Transport & Network Layer (Fragmentation/Flow)            |
|          ISO 15765-2 (ISO-TP: CAN transport protocol, single/multi-frame)     |
|          ISO 14230-2 (KWP2000 Data Link Layer)                                |
+-------------------------------------------------------------------------------+
|                        Data Link & Signaling Protocols                        |
|  ISO 15765-4 (CAN Diagnostics)  |  SAE J1850 PWM (41.6k) |  SAE J1850 VPW (10.4k) |
|  ISO 9141-2 (K-Line / Async)    |  ISO 14230-4 (KWP2000) |  ISO 11898 (CAN Core) |
+-------------------------------------------------------------------------------+
|                        Physical Connector & Pinout                            |
|             SAE J1962 / ISO 15031-3 (16-pin connector Type A & Type B)        |
+-------------------------------------------------------------------------------+
```

### 2.1 Formal Standards Specifications & References
1. **SAE J1962 / ISO 15031-3:** *Diagnostic Connector Equivalent to ISO/DIS 15031-3*. Specifies physical mating dimensions, electrical contact points, keying differences (12V Type A vs 24V Type B), and pin assignments.
   * *Reference:* SAE International, Standard J1962_201607; ISO 15031-3:2016.
2. **SAE J1978 / ISO 15031-4:** *OBD-II Scan Tool*. Outlines mandatory software functional capabilities, protocol auto-detection mechanisms, timeout handling, and user displays.
   * *Reference:* SAE International, Standard J1978_200204; ISO 15031-4:2014.
3. **SAE J1979 / ISO 15031-5:** *E/E Diagnostic Test Modes*. Defines diagnostic service modes (01 to 0A) and standard Parameter IDs (PIDs).
   * *Reference:* SAE International, Standard J1979_201702; ISO 15031-5:2015.
4. **SAE J1979-2:** *E/E Diagnostic Test Modes: OBDonUDS*. The modern evolution establishing emission-related diagnostics over ISO 14229-1 (Unified Diagnostic Services).
   * *Reference:* SAE International, Standard J1979-2_202104 / 2023.
5. **SAE J2012 / ISO 15031-6:** *Diagnostic Trouble Code Definitions*. Defines 5-character alphanumeric DTC formatting (P0xxx, B0xxx, C0xxx, U0xxx).
   * *Reference:* SAE International, Standard J2012_201612; ISO 15031-6:2015.
6. **ISO 15765-4:** *Road vehicles — Diagnostic communication over Controller Area Network (DoCAN) — Part 4: Requirements for emissions-related systems*. Specifies 11-bit and 29-bit CAN identifiers, 250 kbps and 500 kbps bit rates, and initialization timing.
   * *Reference:* ISO Standard 15765-4:2021.
7. **ISO 11898-1 & ISO 11898-2:** *Controller Area Network (CAN) — Data link layer and physical signaling / High-speed medium access unit*.
   * *Reference:* ISO 11898-1:2015, ISO 11898-2:2016.
8. **ISO 14229-1:** *Unified diagnostic services (UDS) — Part 1: Application layer*.
   * *Reference:* ISO 14229-1:2020.
9. **SAE J1850:** *Class B Data Communication Network Interface*. Defines pulse-width modulation (PWM 41.6 kbps, differential) and variable pulse width (VPW 10.4 kbps, single-wire).
   * *Reference:* SAE International, Standard J1850_200606.
10. **ISO 9141-2 / ISO 14230-4:** *Road vehicles — Diagnostic systems — CARB requirements for interchange of digital information* / *Keyword Protocol 2000 (KWP2000)*. Asynchronous serial communication on the K-line (10.4 kbps) with 5-baud or fast initialization.
    * *Reference:* ISO 9141-2:1994, ISO 14230-4:2000.

---

## 3. OBD-II Diagnostic Services (SAE J1979 / ISO 15031-5)

Requests are formatted as Hexadecimal Service IDs (SID). Responses echo `SID + 0x40`.

| Mode (Hex) | Service Name | Technical Purpose | Typical Response Format |
| :---: | :--- | :--- | :--- |
| **01** | Show Current Data | Real-time sensor telemetry (RPM, Speed, Coolant Temp, MAF, O2, Fuel Trims). | `41 <PID> <Data Bytes>` |
| **02** | Show Freeze Frame Data | Operating parameters recorded at the instant an emission fault (DTC) was registered. | `42 <PID> <Frame#> <Data Bytes>` |
| **03** | Stored Diagnostic Trouble Codes | Confirmed emissions-related DTCs that illuminated the Malfunction Indicator Lamp (MIL). | `43 <Count> <DTC1_High> <DTC1_Low> ...` |
| **04** | Clear/Reset Diagnostic Info | Clears DTCs, resets Freeze Frames, clears readiness monitor flags (forces readiness re-evaluation). | `44` |
| **05** | Oxygen Sensor Monitoring (Legacy) | Test results for O2 sensors (used on pre-CAN legacy protocols; replaced by Mode 06 on CAN). | `45 <TestID> <Data>` |
| **06** | On-Board Monitoring Test Results | Test results for non-continuously monitored systems (Catalyst, Evap, EGR, VVT, secondary air). | `46 <MID> <TID> <Val> <Min> <Max>` |
| **07** | Pending DTCs | Faults detected during current or previous drive cycle; not yet confirmed to illuminate MIL. | `47 <Count> <DTC1_High> <DTC1_Low> ...` |
| **08** | Control On-Board Devices | Bi-directional test execution (e.g., EVAP canister leak test). OEM specific implementation. | `48 <Data>` |
| **09** | Vehicle Information | Read Vehicle Identification Number (VIN), Calibration IDs (CALID), CVN, and ECU tracking. | `49 <InfoType> <Data>` |
| **0A** | Permanent DTCs | Faults that cannot be cleared via Mode 04 or battery disconnect; clears only after self-healing drive cycles. | `4A <Count> <DTC1_High> <DTC1_Low> ...` |

---

## 4. Hardware Interface & Connector Pinout (SAE J1962)

### 4.1 Physical Connector Geometry & Keying
The SAE J1962 connector is a 16-pin dual-row receptacle with a trapezoidal shroud:
* **Type A (12V Nominal):** Used in light-duty passenger vehicles (up to 4A continuous on Pin 16). Features an unbroken central horizontal alignment partition.
* **Type B (24V Nominal):** Used in medium- and heavy-duty vehicles (up to 2A continuous on Pin 16). Features a central partition interrupted by a mechanical keyway tab to prevent plugging a 12V tool into a 24V socket.

```text
               VEHICLE MATING CONNECTOR (FEMALE FACE VIEW)
               +-----------------------------------------+
               \   1   2   3   4   5   6   7   8        /
                \                                      /
                 \  9  10  11  12  13  14  15  16     /
                  +----------------------------------+
```

### 4.2 Pinout Reference Matrix

|  Pin   | Electrical Signal Name     | Formal Standard           | Description / Signal Specification                                                     |
| :----: | :------------------------- | :------------------------ | :------------------------------------------------------------------------------------- |
| **1**  | Manufacturer Discretionary | OEM Specific              | OEM proprietary link, SWCAN (GM), or Ethernet TX+ (DoIP ISO 13400).                    |
| **2**  | SAE J1850 Bus (+)          | SAE J1850                 | High line for PWM (differential, 0–5V) or VPW (single-wire, 0–7V, active high).        |
| **3**  | Manufacturer Discretionary | OEM Specific              | OEM proprietary link, or Ethernet TX- (DoIP ISO 13400).                                |
| **4**  | Chassis Ground             | SAE J1962                 | Vehicle chassis ground reference (low resistance to vehicle metal structure).          |
| **5**  | Signal Ground              | SAE J1962                 | Clean analog/logic signal ground return for communication circuitry.                   |
| **6**  | CAN High (CAN-H)           | ISO 15765-4 / ISO 11898-2 | High-speed CAN bus differential high signal (Recessive: 2.5V, Dominant: 3.5V).         |
| **7**  | K-Line                     | ISO 9141-2 / ISO 14230-4  | Bidirectional single-wire ISO asynchronous communication (pull-up to battery voltage). |
| **8**  | Manufacturer Discretionary | OEM Specific              | OEM ignition sense, secondary bus, or DoIP activation line (ISO 13400).                |
| **9**  | Manufacturer Discretionary | OEM Specific              | OEM proprietary (e.g., tachometer/speed pulse, GM 8192-baud ALDL).                     |
| **10** | SAE J1850 Bus (-)          | SAE J1850                 | Low line for differential PWM (0–5V, complementary to Pin 2). Unused in VPW.           |
| **11** | Manufacturer Discretionary | OEM Specific              | OEM proprietary link, or Ethernet RX+ (DoIP ISO 13400).                                |
| **12** | Manufacturer Discretionary | OEM Specific              | OEM proprietary link, or Ethernet RX- (DoIP ISO 13400).                                |
| **13** | Manufacturer Discretionary | OEM Specific              | OEM programming voltage (FEPS) or chassis diagnostics.                                 |
| **14** | CAN Low (CAN-L)            | ISO 15765-4 / ISO 11898-2 | High-speed CAN bus differential low signal (Recessive: 2.5V, Dominant: 1.5V).          |
| **15** | L-Line                     | ISO 9141-2 / ISO 14230-4  | Optional unidirectional initialization line for early ISO 9141 implementations.        |
| **16** | Battery Power (VBAT)       | SAE J1962                 | Unswitched permanent battery positive (+12V nominal on Type A; +24V on Type B).        |

---

## 5. ELM327 Wi-Fi Adapter Connection Standard & Network Profile

### 5.1 Architecture Overview
An ELM327 Wi-Fi adapter is an embedded peripheral integrating:
1. **Diagnostic Line Transceivers:** CAN transceiver (e.g., MCP2551 / TJA1040 / TJA1050), K-Line transceiver (e.g., MC33290 / SI9243), and J1850 comparator circuits.
2. **OBD Interpreter Microcontroller:** Original Elm Electronics PIC18F2480 firmware or modern ARM Cortex-M/PIC clone microcontrollers executing the ELM327 command set.
3. **Wi-Fi SoC / Serial Bridge:** ESP8266, ESP8285, HF-LPT100, or Realtek Wi-Fi module running a TCP/UDP-to-UART bridging firmware.

```
+--------------------+        TCP/IP over 802.11       +--------------------------+
|  Client Software   | <=============================> |   Wi-Fi Bridge SoC       |
|  (App / Agent)     |      Socket: 192.168.0.10:35000 |   (ESP8266 / HF-LPT100)  |
+--------------------+                                 +------------+-------------+
                                                                    | UART (38.4k / 115.2k)
                                                                    v
+--------------------+        CAN / K-Line / J1850     +------------+-------------+
|    Vehicle ECUs    | <=============================> |  ELM327 Microcontroller  |
|  (OBD-II Port)     |        SAE J1962 Physical Bus   |  Interpreter & ISO-TP    |
+--------------------+                                 +--------------------------+
```

### 5.2 Network Specification
* **WLAN Standard:** IEEE 802.11 b/g/n (2.4 GHz).
* **Operating Mode:** SoftAP (Software Access Point). Typical broadcast SSIDs: `WiFi_OBDII`, `OBDII`, `V-Link`, `CLKDevices`.
* **Security:** Open (None) or WPA2-PSK (Default PSK typically `12345678`).
* **Addressing Model:**
  * **Adapter Static IP:** `192.168.0.10`
  * **Subnet Mask:** `255.255.255.0` (`/24`)
  * **Adapter Gateway / DNS:** `192.168.0.10`
  * **DHCP Range for Clients:** `192.168.0.11` – `192.168.0.254`
* **Transport Layer:**
  * **Protocol:** **TCP** (Transmission Control Protocol) stream.
  * **Default Port:** `35000` (De-facto industry standard).
  * *Note:* Some firmware builds also listen on UDP port `35000` or TCP port `23` (Telnet), but **TCP port 35000** is the universal standard for client diagnostic applications.

### 5.3 Application Framing & Stream Protocol
* **Encoding:** 7-bit ASCII.
* **Termination:** Commands transmitted to the adapter MUST terminate with a Carriage Return (`\r`, ASCII `0x0D`). Do NOT send Line Feed (`\n`) as part of the command unless configured.
* **Prompt Token:** The ELM327 signals completion of command execution and readiness for the next command by outputting the greater-than character: `>` (ASCII `0x3E`).
* **Line Feeds:** Depending on `ATL1`/`ATL0`, responses include or omit `\n` (`0x0A`).
* **Echo:** By default, the adapter echoes received characters back. Applications MUST issue `ATE0` (Echo Off) during bootstrap to simplify parser state machines.

### 5.4 Standard Initialization Sequence
```text
Client -> Adapter:  "ATZ\r"         (Reset IC; wait ~1 sec for greeting, e.g. "ELM327 v1.5")
Client -> Adapter:  "ATE0\r"        (Echo off -> adapter responds: "OK\r>")
Client -> Adapter:  "ATL0\r"        (Linefeeds off -> adapter responds: "OK\r>")
Client -> Adapter:  "ATS0\r"        (Spaces off -> responses returned as contiguous hex: "OK\r>")
Client -> Adapter:  "ATH0\r"        (Headers off -> only payload data returned: "OK\r>")
Client -> Adapter:  "ATSP0\r"       (Set protocol to Automatic: "OK\r>")
Client -> Adapter:  "0100\r"        (Query Mode 01 Supported PIDs 01-20; initiates bus search)
Adapter -> Client:  "SEARCHING...\r4100BE3EB811\r>"
```

---

## 6. CAN Bus Compatibility Analysis (ELM327 vs CANBUS)

### 6.1 Does ELM327 Support CANBUS?
**YES.** Controller Area Network (CAN) support is a foundational capability of the ELM327 IC and is fully supported by all compliant devices.

### 6.2 ELM327 Protocol Map (`AT SP` / `AT TP`)

| Code | Protocol Identifier | Baud Rate | ID Format | ISO / SAE Standard |
|:---:|:---|:---:|:---:|:---|
| **0** | Automatic Protocol Detection | Dynamic | Dynamic | Tries all protocols sequentially |
| **1** | SAE J1850 PWM | 41.6 kbps | Variable | Ford legacy |
| **2** | SAE J1850 VPW | 10.4 kbps | Variable | GM legacy |
| **3** | ISO 9141-2 | 10.4 kbps | 11-bit | Asian / European legacy |
| **4** | ISO 14230-4 KWP (5 baud init) | 10.4 kbps | 11-bit | Asian / European legacy |
| **5** | ISO 14230-4 KWP (Fast init) | 10.4 kbps | 11-bit | Asian / European legacy |
| **6** | **ISO 15765-4 CAN** | **500 kbps** | **11-bit** | **Standard US MY2008+ (Default)** |
| **7** | **ISO 15765-4 CAN** | **500 kbps** | **29-bit** | **Extended CAN 500k** |
| **8** | **ISO 15765-4 CAN** | **250 kbps** | **11-bit** | **Standard Low-Speed Diagnostic CAN** |
| **9** | **ISO 15765-4 CAN** | **250 kbps** | **29-bit** | **Extended CAN 250k** |
| **A** | **SAE J1939 CAN** | **250 kbps** | **29-bit** | **Heavy Duty Commercial Vehicles** |
| **B** | **User 1 CAN** | Configurable | 11/29-bit | Custom timing registers (`AT PB`) |
| **C** | **User 2 CAN** | Configurable | 11/29-bit | Custom timing registers (`AT PB`) |

### 6.3 Dedicated ELM327 CAN Control Commands
* **`AT CAF1` / `AT CAF0`:** CAN Automatic Formatting On / Off.
  * *`CAF1` (Default):* Microcontroller automatically formats ISO 15765-2 multi-frame (ISO-TP) packets, strips PCI bytes, and manages frame lengths.
  * *`CAF0`:* Raw CAN frame mode. Applications must inspect PCI bytes, DLC, and frame headers manually.
* **`AT CFC1` / `AT CFC0`:** CAN Flow Control On / Off.
  * *`CFC1` (Default):* The ELM327 hardware automatically sends ISO 15765-2 Flow Control (FC) frames when receiving multi-frame ECU replies.
* **`AT CRA <ID>`:** Set CAN Receive Address. Quickly filters the bus to accept only the designated 11-bit (`CRA 7E8`) or 29-bit ID, ignoring irrelevant bus traffic.
* **`AT CF <Filter>` & `AT CM <Mask>`:** Hardware bitmask filters for acceptance filtering across message groups.
* **`AT CSM1` / `AT CSM0`:** CAN Silent Monitoring Mode (Listen-only mode; disables ACKs on the physical bus to avoid disrupting vehicle modules).
* **`AT MA` / `AT MR` / `AT MT`:** Monitor All / Monitor Receiver / Monitor Transmitter (sniffs live CAN frames continuously).

### 6.4 Critical Engineering Limitations of ELM327 on CAN Networks

| Limitation Factor | Physical Cause | Real-World Impact |
|:---|:---|:---|
| **UART / Wi-Fi Bottleneck** | Internal microcontroller communicates with Wi-Fi bridge over 38,400 or 115,200 baud UART. | 500 kbps CAN bus running at 40% bus load produces ~200 kbps raw data. The UART link saturates immediately during unfiltered promiscuous monitoring (`AT MA`). |
| **Buffer Overflow** | Original ELM327 has a ~512-byte FIFO buffer. Cheap clones have <128 bytes. | Emits `BUFFER FULL` error during heavy bus traffic unless aggressive filtering (`AT CRA`) is applied. |
| **CAN-FD Incompatibility** | ELM327 transceiver and controller lack Bosch ISO 11898-1:2015 CAN-FD hardware support. | **Cannot read CAN-FD** (Flexible Data-rate, up to 5–8 Mbps, 64-byte payload) found in 2020+ GM (Global B), Ford, BMW, and VAG platforms. |
| **Clone Firmware Deficiencies** | >95% of cheap adapters use cloned chips (marked "v1.5" or "v2.1" — versions never released by Elm Electronics). | Many clones fail ISO-TP multi-frame reassembly, lack non-volatile EEPROM, or freeze when receiving out-of-order CAN frames. |

### 6.5 Alternative Solutions for High-Throughput / CAN-FD Ingestion
When the application requires non-emissions high-throughput reverse engineering, raw bus sniffing, or modern CAN-FD compatibility:
1. **STN1110 / STN2120 / OBDLink Family:**
   * Fully backwards compatible with ELM327 AT commands, but includes the extended ST commands.
   * Large RX/TX RAM buffers (tens of kilobytes), native UART rates up to 10 Mbps.
2. **Native Linux SocketCAN Hardware:**
   * USB-to-CAN converters (e.g., Candlelight / CANable, InnoMaker USB-CAN, PEAK PCAN-USB FD).
   * Appears in Linux as native network interfaces (`can0`, `vcan0`).
   * Managed via standard `iproute2` and parsed using C/C++, Python (`python-can`), or Rust (`socketcan`).
3. **Automotive Engineering Interfaces:**
   * Vector VN1600 series, Intrepid Control Systems neoVI Fire 3, Kvaser Leaf Pro FD.
   * Required for high-precision timestamping, dual-wire/single-wire CAN, and CAN-FD/LIN/Ethernet logging.

---

## 7. Software Architecture & Ingestion Specification

For an autonomous implementation agent, the OBD-II Reader engine should be structured into four decoupled layers:

```
+-------------------------------------------------------------------------------+
|                       Presentation / UI / Diagnostic CLI                      |
|            PID Dashboards, DTC Read/Clear Views, Raw Bus Sniffer              |
+-------------------------------------------------------------------------------+
|                    OBD-II Diagnostic Engine (Domain Layer)                    |
|  * Mode 01 PID Decoder (Formulas, scaling, metric/imperial conversions)       |
|  * Mode 03 / 07 / 0A DTC Decoder (Fault categorization, SAE J2012 dictionary) |
|  * Mode 09 VIN Decoder (ISO 3779 checksum, manufacturer decoding)             |
+-------------------------------------------------------------------------------+
|                 ELM327 Protocol Interpreter (Session Layer)                   |
|  * State Machine: DISCONNECTED -> CONNECTING -> INITIALIZING -> READY         |
|  * Prompt Parser: Reads until '>' token, cleans whitespace, strips echo       |
|  * Error Handler: Detects "NO DATA", "UNABLE TO CONNECT", "BUS BUSY", "ERR"   |
|  * PID Query Scheduler: Prioritized round-robin PID polling                   |
+-------------------------------------------------------------------------------+
|                     Network Transport Layer (I/O Layer)                       |
|  * Async TCP Socket Client: Connects to 192.168.0.10:35000                    |
|  * Reconnect backoff engine with keep-alive heartbeat (`AT\r`)                |
|  * Raw telemetry logger / packet recorder                                     |
+-------------------------------------------------------------------------------+
```

### 7.1 Essential PID Decoding Reference (Mode 01)
* **PID `0x0C` (Engine RPM):**
  * Bytes returned: `A, B` (2 bytes)
  * Formula: $\text{RPM} = \frac{(256 \cdot A) + B}{4}$
* **PID `0x0D` (Vehicle Speed):**
  * Bytes returned: `A` (1 byte)
  * Formula: $\text{Speed (km/h)} = A$ | $\text{Speed (mph)} = A \times 0.621371$
* **PID `0x05` (Engine Coolant Temperature):**
  * Bytes returned: `A` (1 byte)
  * Formula: $\text{Temp}(^\circ\text{C}) = A - 40$
* **PID `0x04` (Calculated Engine Load):**
  * Bytes returned: `A` (1 byte)
  * Formula: $\text{Load}(\%) = \frac{A \cdot 100}{255}$
* **PID `0x10` (Mass Air Flow - MAF):**
  * Bytes returned: `A, B` (2 bytes)
  * Formula: $\text{MAF}(\text{g/s}) = \frac{(256 \cdot A) + B}{100}$

---

## 8. Verification & References Index

1. **EPA OBD Regulations:**
   * 40 CFR § 86.1806-05: *On-board diagnostics for 2005 and later model year vehicles.*
   * URL: https://www.ecfr.gov/current/title-40/part-86/section-86.1806-05
2. **SAE Technical Standards:**
   * SAE J1962: *Diagnostic Connector Equivalent to ISO/DIS 15031-3*
   * SAE J1978: *OBD-II Scan Tool*
   * SAE J1979: *E/E Diagnostic Test Modes*
   * SAE J1979-2: *E/E Diagnostic Test Modes: OBDonUDS*
   * SAE J2012: *Diagnostic Trouble Code Definitions*
   * SAE J1850: *Class B Data Communication Network Interface*
   * URL: https://www.sae.org/standards/content/j1979_201702/
3. **ISO Standards Catalog:**
   * ISO 15031 Series: *Road vehicles — Communication between vehicle and external equipment for emissions-related diagnostics*
   * ISO 15765-4: *Diagnostic communication over Controller Area Network (DoCAN)*
   * ISO 11898-1/2: *Road vehicles — Controller Area Network (CAN)*
   * ISO 14229-1: *Road vehicles — Unified diagnostic services (UDS)*
   * URL: https://www.iso.org/standard/66380.html
4. **ELM Electronics Technical Documentation:**
   * *ELM327 OBD to RS232 Interpreter Datasheet*, Elm Electronics.
   * Commands, CAN filter configurations, timing parameters, and AT instruction reference.
5. **STN Protocol Reference:**
   * *STN11xx / STN21xx Family Reference Manual*, Scantool.net LLC.
