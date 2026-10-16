# Powersports, Motorcycle & Marine OBD Standards Specification
**Document ID:** SPEC-OBD2-EXT-002  
**Version:** 1.0.0  
**Target Domains:** Motorcycles, ATVs/UTVs, Watercraft (Pleasure Boats & PWCs), Snowmobiles  
**Purpose:** Technical reference cataloging regulatory mandates, diagnostic protocols, physical connector geometries, and architectural deviations from passenger car OBD-II standards.

---

## 1. Executive Summary & Core Deviation Philosophy

In United States passenger cars (MY1996+), On-Board Diagnostics is federally uniform: every vehicle features an unsealed 16-pin **SAE J1962** connector in the passenger footwell, responds to **SAE J1979** Mode `01`–`0A` services, encodes faults in **SAE J2012** 5-character format, and (since MY2008) runs **ISO 15765-4 CAN** at 500 kbps.

**In Powersports and Marine, this uniformity does NOT exist natively.**
Instead, the ecosystem is governed by distinct regulatory regimes (EPA 40 CFR Part 1051, Part 1045; EU Regulation 168/2013), rugged environmental constraints (demanding IP67/IP68 waterproof connectors), industrial bus protocols (**SAE J1939** and **NMEA 2000**), and proprietary manufacturer silos (BRP BUDS, Polaris Digital Wrench, Mercury SmartCraft, Yamaha YDS).

```
+-----------------------------------------------------------------------------------------------------+
| PASSENGER CAR BASELINE:  Cabin-mounted, unsealed 16-pin SAE J1962 | SAE J1979 (Modes 01-0A) | CAN 500k |
+-----------------------------------------------------------------------------------------------------+
         |
         +---> MOTORCYCLES:      Euro 5 Standard: Sealed 6-pin ISO 19689 | ISO 15765-4 / UDS | CAN 500k
         |                       Pre-Euro 5: Highly fragmented OEM plugs (Honda 4p, Yamaha 3/4p, BMW 10p)
         |
         +---> ATVs / UTVs:      NO US OBD-II mandate (EPA Part 1051) | Proprietary CAN / J1939
         |                       Polaris 8-pin Delphi / Can-Am 6-pin Deutsch DTM | OEM software silos
         |
         +---> MARINE CRAFT:     EPA Part 1045 mandate: Inboard/Sterndrive requires SAE J1939-05 (NOT J1979!)
         |                       NMEA 2000 (M12 Micro-C 5-pin) | Mercury SmartCraft | BRP Sea-Doo BUDS
         |
         +---> SNOWMOBILES:      Shared parent powersports architecture (BRP Rotax / Polaris / Arctic Cat)
```

---

## 2. Motorcycles (On-Road Two-Wheelers)

### 2.1 Regulatory Framework
* **European Union (The Global Benchmark):**
  * **EU Regulation No 168/2013 (Annex XII):**
    * **Euro 4 (2016/2017):** Introduced **OBD Stage I** (circuit continuity, electrical short/open detection, and basic sensor plausibility).
    * **Euro 5 (2020/2021) & Euro 5+ (2024):** Introduced **OBD Stage II** (full catalytic converter efficiency monitoring, engine misfire detection, lambda/O2 sensor degradation, and standardized communication).
* **United States:**
  * **EPA (40 CFR Part 86, Subpart E):** Sets exhaust and evaporative emissions limits for highway motorcycles ($\ge 50\text{cc}$), but historically did *not* mandate an automotive-style 16-pin OBD port.
  * **CARB (Title 13 CCR § 1958):** California Air Resources Board has harmonized diagnostic requirements with Euro 5/5+ benchmarks.
  * **UNECE Global Technical Regulation (GTR No. 18):** Global technical regulation for on-board diagnostic systems for two-wheeled vehicles.

### 2.2 Physical Connector Standard: ISO 19689
Under Euro 5, the motorcycle industry resolved decades of plug fragmentation by adopting **ISO 19689:2016** (*Motorcycles and mopeds — Communication between vehicle and external equipment for diagnostics — Diagnostic connector and related electrical circuits*).

* **Connector Form Factor:** Compact, red or black, waterproof, latching **6-pin connector** (frequently JST / Sumitomo style) rated to **IP67**.
* **Mounting Location:** Under the passenger seat, behind a side battery cowl, or near the steering head.

```text
               ISO 19689 6-PIN CONNECTOR (FRONT MATING FACE)
                           +---------------+
                           |  [1]  [2]  [3]|
                           |  [4]  [5]  [6]|
                           +---------------+
```

#### ISO 19689 Pin Assignment & Conversion to SAE J1962 (Passenger Car OBD-II)

| ISO 19689 Pin | Signal Function | Protocol / Electrical Spec | Mates to SAE J1962 (OBD2) Pin |
|:---:|:---|:---|:---:|
| **1** | K-Line (Secondary) / Vendor | Optional K-Line or OEM Kline 2 | Pin 15 (L-Line) or OEM Discretionary |
| **2** | **CAN High (CAN-H)** | ISO 15765-4 (High-Speed CAN 500 kbps) | **Pin 6** |
| **3** | **Chassis / Signal Ground** | 0V Ground Reference | **Pin 4 & Pin 5** |
| **4** | **Battery Power (+12V)** | Unswitched Battery Positive (VBAT) | **Pin 16** |
| **5** | **CAN Low (CAN-L)** | ISO 15765-4 (High-Speed CAN 500 kbps) | **Pin 14** |
| **6** | **K-Line (Primary)** | ISO 14230-4 / ISO 9141-2 K-Line | **Pin 7** |

### 2.3 Pre-Euro 5 Legacy Fragmentation (Adapter Reference)
Before ISO 19689, every manufacturer used proprietary connectors:
* **Honda:** 4-pin red Sumitomo connector (K-Line + CAN on newer models).
* **Yamaha:** 3-pin white triangular connector (K-Line) $\rightarrow$ 4-pin square connector (CAN).
* **Kawasaki:** 4-pin or 6-pin semi-sealed connector.
* **KTM / Husqvarna:** 6-pin white/black Sumitomo connector.
* **Ducati:** 4-pin DDA (Ducati Data Analyzer) connector under seat.
* **BMW Motorrad:** Round 10-pin ICOM-D connector (pre-2017) $\rightarrow$ 16-pin OBD2 (Euro 4) $\rightarrow$ ISO 19689 (Euro 5).
* **Harley-Davidson:** 4-pin Deutsch DT (pre-2011, J1850 VPW) $\rightarrow$ 6-pin Deutsch DT (2011+, CAN-based HDLAN).

### 2.4 ELM327 Wi-Fi Compatibility on Motorcycles
* **Verdict:** **HIGHLY COMPATIBLE (with passive adapter cable).**
* Modern Euro 4/5 motorcycles run standard **ISO 15765-4 CAN** (11-bit, 500 kbps) over the bus. An ELM327 Wi-Fi adapter plugged into a **6-pin ISO 19689 to 16-pin SAE J1962 adapter cable** can immediately execute `ATZ`, `ATSP6`, query Mode `01` PIDs (RPM, Speed, Throttle, Temps), and read/clear Mode `03` DTCs.

---

## 3. ATVs & UTVs (Side-by-Sides / Off-Highway Vehicles)

### 3.1 Regulatory Framework
* **EPA Jurisdiction:** **40 CFR Part 1051** (*Control of Emissions From Recreational Engines and Vehicles*).
* **CARB Jurisdiction:** **Title 13 CCR § 2410–2415** (Off-Highway Recreational Vehicles - OHRV).
* **The Regulatory Void:** **There is NO federal or state mandate requiring ATVs or UTVs to implement standard OBD-II (SAE J1962 ports or SAE J1979 diagnostic modes).** Emissions compliance is verified via engine dynamometer / chassis dyno certification cycles rather than in-use standardized OBD-II interrogation.

### 3.2 Manufacturer Diagnostic Connectors & Protocols

| Manufacturer | Vehicle Examples | Diagnostic Port Hardware | Protocol & Signaling | Factory Dealer System |
|:---|:---|:---|:---|:---|
| **Polaris** | RZR XP, Ranger, General, Sportsman | **8-pin sealed Delphi/Aptiv** or **6-pin Deutsch** (under dash or front hood) | Proprietary CAN (250k or 500k) + SAE J1939 elements | **Polaris Digital Wrench** |
| **Can-Am (BRP)** | Maverick X3, Defender, Commander, Outlander | **6-pin sealed Deutsch DTM** (under seat or dash) | Proprietary BRP CAN (250 kbps, Rotax ECM) | **BRP BUDS / BUDS2 / MPI-3** |
| **Yamaha Powersports** | YXZ1000R, Wolverine, Grizzly | **4-pin Sumitomo waterproof** coupler | Yamaha proprietary K-Line / CAN | **Yamaha YDS** |
| **Honda Powersports** | Talon 1000, Pioneer 1000/700 | **4-pin red Sumitomo** coupler | Honda HDS proprietary serial/CAN | **Honda Diagnostic System (HDS)** |
| **Kawasaki** | Teryx KRX 1000, Mule | **6-pin sealed coupler** | Kawasaki KDS serial/CAN | **Kawasaki KDS** |

### 3.3 Diagnostic Protocol Realities
* **No Generic OBD Broadcast:** If an ELM327 adapter is wired to a Polaris or Can-Am CAN bus using an adapter cable and issues `0100\r` (Mode 01 supported PIDs), the vehicle ECU will typically return **`NO DATA`**.
* **Why?** The ECUs do not listen on the standard emissions broadcast ID (`0x7DF`) and do not implement SAE J1979 service IDs. Instead, they require:
  1. Diagnostic session requests under **ISO 14229 (UDS)** or **KWP2000**.
  2. Manufacturer-specific CAN identifiers (e.g., Bosch/Delphi target IDs on Polaris; Rotax IDs on Can-Am).
* **Aftermarket Solutions:** Tuners like **Dynojet Power Vision**, **HP Tuners MPVI3**, and **EZ LYNK** build custom adapter harnesses and speak the manufacturer's proprietary seed-key security protocols over raw CAN.

---

## 4. Watercraft: Pleasure Boats & Personal Watercraft (PWCs)

### 4.1 Regulatory Framework
* **Federal Mandate:** **40 CFR Part 1045** (*Control of Emissions From Spark-Ignition Propulsion Marine Engines and Vessels*).
* **The Marine OBD Mandate (40 CFR § 1045.110):**
  * *"How must my engines diagnose malfunctions?"*
  * Requires manufacturers of marine spark-ignition engines equipped with **three-way catalytic converters and closed-loop air-fuel control** (standard on modern inboard and sterndrive pleasure boats) to equip engines with on-board diagnostics!
* **The Governing Standard:** Instead of passenger-car SAE J1979, the EPA explicitly incorporated by reference:
  * **SAE J1939-05:** *Marine Stern Drive and Inboard Spark-Ignition Engine On-Board Diagnostics Implementation Guide*.

### 4.2 Marine Telemetry & Network Standards: NMEA 2000
While cars use OBD-II, boats network their navigation, gauges, depth sounders, and engines over **NMEA 2000** (standardized internationally as **IEC 61162-3**).
* **Physical Layer:** 5-pin **DeviceNet Micro-C M12 circular waterproof connectors** (rated **IP67/IP68**).
* **Signaling:** High-Speed CAN (**ISO 11898-2**) at **250 kbps** with **29-bit extended identifiers**.
* **Architecture:** Backbone trunk with drop cables and $120\,\Omega$ terminating resistors at each end.
* **Telemetry Data Format (Parameter Group Numbers - PGNs):**
  * **PGN 127488:** *Engine Parameters, Rapid Update* (Engine Speed/RPM, Boost Pressure, Tilt/Trim).
  * **PGN 127489:** *Engine Parameters, Dynamic* (Oil Pressure, Oil Temp, Coolant Temp, Alternator Volts, Fuel Rate, Engine Hours, Coolant Pressure).

```text
               NMEA 2000 MICRO-C M12 5-PIN MALE CONNECTOR
                                 [1] Drain (Shield)
                             [2] NET-S (V+ 12V)
                             [3] NET-C (V- Ground)
                             [4] NET-H (CAN High)
                             [5] NET-L (CAN Low)
```

### 4.3 Inboard, Outboard & PWC Diagnostic Architecture

| Marine Category | Manufacturer / System | Connector Hardware | Diagnostic Protocol |
|:---|:---|:---|:---|
| **Inboard / Sterndrive** | Indmar, PCM, Crusader, Ilmor (Catalyzed GM/Ford V8s) | **Deutsch 6-pin (DT06-6S)** or **Deutsch 9-pin (HD10-9-1939)** | **SAE J1939** (250 kbps, 29-bit CAN). Faults reported via `DM1` (Active DTCs) and `DM2` (Historic DTCs). |
| **Legacy Inboards** | GM Marine MEFI 1, 2, 3, 4 (1990s–2000s) | **10-pin or 12-pin Packard / Delphi Weather Pack** | Asynchronous serial (8192-baud ALDL or 9600-baud). Requires MEFI-Scan tool. |
| **Outboard / Sterndrive** | Mercury Marine (Verado, Pro XS, MerCruiser) | **Proprietary 4-pin or 10-pin circular Amphenol / SmartCraft** | **Mercury SmartCraft** (Proprietary CAN 250 kbps). Requires Mercury Computer Diagnostic System (CDS). |
| **Outboard / PWC** | Yamaha Marine (Outboards & WaveRunners) | **3-pin or 4-pin waterproof Sumitomo** | **Yamaha Diagnostic System (YDS / YDS-2)**. Proprietary serial/CAN. |
| **PWC / Jet Ski** | BRP Sea-Doo (RXP, RXT, GTI, Spark) | **6-pin Deutsch DTM connector** (under seat / front hood) | **BRP BUDS / BUDS2** (Rotax ECM proprietary CAN). |
| **PWC / Jet Ski** | Kawasaki Jet Ski (Ultra 310, STX) | **4-pin / 6-pin waterproof coupler** | **Kawasaki Diagnostic System (KDS)**. |

### 4.4 Marine Diagnostic Trouble Codes: SPN/FMI vs. SAE J2012
On J1939-compliant marine engines (Indmar, PCM, Volvo Penta), fault codes do **not** use the 5-character `P0xxx` format. Instead, they use the modular **SPN / FMI** format:
* **SPN (Suspect Parameter Number):** Identifies the subsystem or component (e.g., `SPN 110` = Engine Coolant Temperature; `SPN 100` = Engine Oil Pressure).
* **FMI (Failure Mode Identifier):** Identifies the specific failure state (e.g., `FMI 3` = Voltage Above Normal / Shorted High; `FMI 4` = Voltage Below Normal / Shorted Low).
* *Example:* An open coolant sensor circuit is reported as `SPN 110 / FMI 3` rather than `P0118`.

---

## 5. Powersports: Snowmobiles

Snowmobiles inherit the powertrain and electrical architecture of their parent powersports manufacturers:
* **Ski-Doo / Lynx (BRP):** Rotax E-TEC 2-stroke and 4-TEC 4-stroke engines utilize the standard **BRP 6-pin Deutsch DTM** diagnostic port and communicate via **BRP BUDS2**.
* **Polaris Snow (Indy, RMK, Switchback):** Patriot and Cleanfire engines use the **Polaris 8-pin Delphi** diagnostic port (Polaris Digital Wrench).
* **Arctic Cat / Textron (C-TEC2, ZR):** Yamaha/Suzuki-based or proprietary engines using 4-pin or 6-pin sealed connectors.
* **Environmental Demands:** All snowmobile diagnostic harnesses operate under severe temperature extremes (down to $-40^\circ\text{C}$), requiring silicone seals, gold-plated terminals, and heavy vibration isolation.

---

## 6. Comprehensive Deviations Matrix: Passenger Cars vs. Non-Automotive Vehicles

| Feature / Axis | Passenger Cars & Light Trucks | Motorcycles (Euro 5) | ATVs / UTVs (Side-by-Sides) | Marine Inboard & Sterndrive | Marine PWCs & Outboards |
|:---|:---|:---|:---|:---|:---|
| **Governing Regulation** | EPA 40 CFR Part 86 / CARB Title 13 § 1968.2 | EU Reg 168/2013 / CARB Title 13 § 1958 | EPA 40 CFR Part 1051 / CARB § 2410 | EPA 40 CFR § 1045.110 (Catalyzed engines) | EPA 40 CFR Part 1045 (Emissions only; no OBD mandate) |
| **Mandatory Diagnostic Standard** | **SAE J1979 / SAE J1978** | **ISO 19689 / ISO 15765-4** | **None** (Proprietary OEM) | **SAE J1939-05** | **None** (Proprietary OEM) |
| **Physical Connector** | **SAE J1962 (16-Pin)** | **ISO 19689 (6-Pin)** | **Polaris 8-pin / BRP 6-pin** | **Deutsch 6-pin / 9-pin or M12** | **Sumitomo 3/4p / Deutsch 6p** |
| **Waterproofing / Ingress Rating** | **Unsealed (IP20)** — Dry cabin only | **IP67 Sealed** (Weatherproof) | **IP67 / IP68 Sealed** (Mud/Water submerged) | **IP67 / IP68 Sealed** (Salt spray / Bilge) | **IP68 Sealed** (Water tight) |
| **Primary Physical Bus** | High-Speed CAN (500 kbps) | High-Speed CAN (500 kbps) | CAN (250k or 500k) | **CAN (250 kbps)** | Proprietary CAN or K-Line |
| **CAN Identifier Format** | 11-bit Standard (or 29-bit) | 11-bit Standard | OEM specific (11/29-bit) | **29-bit Extended (J1939)** | OEM specific |
| **Diagnostic Service Protocol** | Modes `01`–`0A` (PIDs) | Modes `01`–`0A` & UDS (ISO 14229) | UDS or Proprietary Seed-Key | **J1939 PGNs (`DM1`, `DM2`)** | Proprietary Factory Protocols |
| **Fault Code Nomenclature** | **SAE J2012** (`P0xxx` 5-char) | **SAE J2012** (`P0xxx` 5-char) | OEM Hex or J1939 | **J1939 SPN / FMI** | OEM Hex Fault Codes |
| **Telemetry Format** | OBD-II PIDs (`0x0C` RPM, etc.) | OBD-II PIDs & UDS DIDs | Raw CAN frames / DIDs | **NMEA 2000 PGNs / J1939 SPNs** | Proprietary stream |
| **ELM327 Wi-Fi Compatibility** | **100% Native Plug-and-Play** | **High** (requires 6-pin adapter) | **Low** (requires custom harness + UDS) | **Moderate** (supports `ATSPA`, requires cable) | **Low/None** (requires OEM hardware) |

---

## 7. Strategic Architectural Guidance for Implementation Agents

For software agents extending our OBD-II reader to support powersports and marine craft:

1. **Physical Adaptation Layer:**
   * Never attempt to connect directly with an SAE J1962 plug. The agent or documentation must specify the appropriate adapter cable (e.g., *ISO 19689 6-pin to OBD2 16-pin* for motorcycles; *Deutsch DT06-6S to OBD2* for marine).
2. **Protocol Engine Bifurcation:**
   * **Mode A: Automotive & Motorcycle Mode (ISO 15765-4 / SAE J1979):**
     * Use standard `ATSP6` (CAN 11-bit 500k) or `ATSP3` (ISO 9141-2).
     * Issue standard PIDs (`010C` RPM, `010D` Speed, `03` DTCs).
   * **Mode B: Marine J1939 Mode (SAE J1939 / NMEA 2000):**
     * Configure ELM327 for Protocol A: `AT SP A` (SAE J1939 CAN 29-bit, 250 kbps).
     * Query PGNs using J1939 transport: `AT MP` (Monitor PGN) or construct raw J1939 request frames for `DM1` (Active Diagnostic Trouble Codes, PGN `65226` / `0xFECA`).
     * Replace SAE J2012 P-code decoding with an **SPN/FMI decoder table**.
3. **Electrical Protection Notice:**
   * Stator-based charging systems on motorcycles, ATVs, and watercraft experience voltage spikes up to $16.5\text{V}$–$18.0\text{V}$ and high AC ripple. Ensure any physical ELM327 hardware deployed in powersports incorporates input TVS surge suppression diodes to protect the logic circuits.
