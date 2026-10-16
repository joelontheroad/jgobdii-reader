# Vehicle Failure Modes, Diagnostic Code Clusters & Live Telemetry Knowledge Base
**Document ID:** SPEC-OBD2-KB-003  
**Version:** 1.0.0  
**Target Audience:** Automotive Engineers, Autonomous Implementation Agents & Diagnostic Software Architects  
**Purpose:** Authoritative reference for identifying multi-code fault clusters, interpreting real-time sensor telemetry (fuel trims, MAF, O2 waveforms), and cross-referencing diagnostic data with educational media (Wikipedia, YouTube, NHTSA).

---

## 1. Diagnostic Code Clusters & Root-Cause Failure Modes

In real-world automotive diagnostics, fault codes rarely occur in isolation. Multiple Electronic Control Units (ECUs) and sensors register symptoms stemming from a single underlying mechanical or electrical malfunction.

Recognizing **Diagnostic Code Clusters** allows software to avoid "parts-cannon" shotgun repairs and direct technicians to the genuine root cause.

```
+---------------------------------------------------------------------------------------------------+
|                                  THE DIAGNOSTIC CLUSTER TAXONOMY                                   |
+---------------------------------------------------------------------------------------------------+
|  1. Lean & Vacuum Leak Cluster:     [P0171] + [P0174] + [P0300] + [P0507]                         |
|  2. MAF Sensor Degradation Cluster: [P0101] + [P0171] + [P0174]                                   |
|  3. Catalyst Inefficiency Cluster:  [P0420] + [P0430] (often preceded by [P0300] / [P0130])       |
|  4. Coolant Under-Temp Cluster:     [P0128] + [P0125]                                             |
|  5. Timing & VVT Correlation:       [P0016] + [P0017] + [P0011] + [P0300]                         |
|  6. EVAP System Leak Cluster:       [P0440] + [P0442] + [P0455] + [P0446]                         |
|  7. Charging Brownout Cluster:      [P0562] + [U0100] + [P0117] + [P0122] (Phantom sensor codes)  |
+---------------------------------------------------------------------------------------------------+
```

---

### Detailed Breakdown of the Top 7 Diagnostic Clusters

#### Cluster 1: Unmetered Air & Vacuum Leak
* **Co-Occurring Codes:** `P0171` (System Too Lean Bank 1), `P0174` (System Too Lean Bank 2), `P0300` (Random Misfire), `P0507` (Idle RPM Higher Than Expected).
* **Failure Physics:** Extra air enters the intake tract *downstream* of the Mass Air Flow sensor. Because the ECU has not metered this air, it injects fuel based only on the MAF reading, resulting in a lean air-fuel mixture that causes combustion misfires.
* **Live Telemetry Signature:**
  * **Short Term + Long Term Fuel Trim:** Heavily positive (**$+15\%$ to $+35\%$**) at warm idle.
  * **Off-Idle Test (2,500 RPM):** Total Fuel Trim drops back toward normal (**$0\%$ to $+5\%$**). (At higher RPMs, the fixed volume of the vacuum leak becomes a negligible percentage of total inducted air).
* **Common Physical Causes:** Cracked intake accordion duct, hardened intake manifold gaskets, torn PCV hose, leaking brake booster diaphragm.

#### Cluster 2: Contaminated Mass Air Flow (MAF) Sensor
* **Co-Occurring Codes:** `P0101` (MAF Range/Performance), `P0171` (Lean Bank 1), `P0174` (Lean Bank 2).
* **Failure Physics:** Dirt, airborne debris, or excess oil from reusable aftermarket air filters coats the heated platinum wire of the MAF sensor, insulating it from the incoming airstream. The sensor falsely reports lower-than-actual airflow to the ECU.
* **Live Telemetry Signature:**
  * **Idle MAF Flow:** Reads significantly below the engine displacement benchmark (e.g., a 3.0L engine reads only $1.8\text{ g/s}$ instead of $3.0\text{–}3.5\text{ g/s}$).
  * **Fuel Trims:** Remain elevated (**$+15\%$ to $+25\%$**) **both at idle and at 2,500 RPM** (unlike a vacuum leak, which recovers at higher RPM).
* **Common Physical Causes:** Contaminated hot wire; restricted airbox; electrical harness degradation.

#### Cluster 3: Three-Way Catalytic Converter Degradation
* **Co-Occurring Codes:** `P0420` (Catalyst System Efficiency Below Threshold Bank 1), `P0430` (Bank 2), frequently preceded by `P0300` misfires or `P0130`/`P0136` O2 circuit faults.
* **Failure Physics:** The precious metal substrate (platinum, palladium, rhodium) of the catalytic converter loses its chemical capacity to store and release oxygen, or the honeycomb matrix has melted due to unburnt fuel from ignition misfires burning inside the exhaust.
* **Live Telemetry Signature:**
  * **Downstream O2 Sensor (Sensor 2):** Under normal conditions, Sensor 2 reports a steady, dampened voltage ($0.55\text{V} - 0.70\text{V}$). In a failing converter, **Sensor 2 mirrors the rapid $1\text{–}2\text{ Hz}$ switching of the Upstream O2 Sensor ($0.1\text{V} - 0.9\text{V}$)**, indicating that zero oxygen is being stored.
* **Common Physical Causes:** Thermal shock; chronic misfires; oil consumption past piston rings; silicone contamination from improper RTV sealant.

#### Cluster 4: Cooling System Under-Temperature (Thermostat Stuck Open)
* **Co-Occurring Codes:** `P0128` (Coolant Thermostat - Below Regulating Temp), `P0125` (Insufficient Coolant Temp for Closed Loop).
* **Failure Physics:** The mechanical bimetallic thermostat valve sticks in the open position, allowing continuous radiator coolant flow even when the engine is cold.
* **Live Telemetry Signature:**
  * **Engine Coolant Temperature (PID `05`):** Fails to reach normal operating temperature ($85^\circ\text{C} - 95^\circ\text{C}$ / $185^\circ\text{F} - 203^\circ\text{F}$); plateaus at $60^\circ\text{C} - 72^\circ\text{C}$ during highway driving.
  * **Fuel System Status (PID `03`):** Stays in Open Loop enrichment or flips between Open and Closed loop, causing high fuel consumption and spark plug soot fouling.
* **Common Physical Causes:** Broken thermostat return spring; degraded rubber valve seal; faulty ECT sensor.

#### Cluster 5: Variable Valve Timing (VVT) & Timing Chain Elongation
* **Co-Occurring Codes:** `P0016` (Crank-Cam Correlation Bank 1 Sensor A), `P0017` (Bank 1 Sensor B), `P0011` / `P0012` (Cam Timing Over-Advanced / Over-Retarded), `P0300`.
* **Failure Physics:** Modern DOHC engines use hydraulic phasers to advance/retard camshafts relative to the crankshaft. When the timing chain stretches or oil control solenoids clog, the physical relationship between the crankshaft and camshaft position sensors deviates beyond factory limits.
* **Live Telemetry Signature:**
  * **Camshaft Advance Angle PID:** Desired cam advance does not track Actual cam advance; phase error exceeds $\pm 10^\circ$.
* **Common Physical Causes:** Stretched timing chain links; worn hydraulic tensioners; sludged oil passages in VVT oil control valves.

#### Cluster 6: Evaporative Emission (EVAP) System Leak
* **Co-Occurring Codes:** `P0440` (EVAP Malfunction), `P0442` (Small Leak 0.040"), `P0455` (Gross Leak / Missing Cap), `P0446` (Vent Control Circuit).
* **Failure Physics:** Fuel vapors venting from the gasoline tank are captured in an activated charcoal canister and sucked into the engine via a purge valve. If a seal, hose, or valve fails, hydrocarbon vapors escape to the atmosphere.
* **Live Telemetry Signature:**
  * **Fuel Tank Pressure (FTP) Sensor:** Fails to register negative pressure (vacuum) when the ECM commands the purge solenoid open and the vent solenoid closed during self-test.
* **Common Physical Causes:** Loose or perished fuel filler cap O-ring; cracked charcoal canister; sticking purge solenoid; rusted fuel filler neck.

#### Cluster 7: Low System Voltage & Electrical Ground Brownout
* **Co-Occurring Codes:** `P0562` (System Voltage Low), `U0100` (Lost Comm with ECM), `U0101` (Lost Comm with TCM), accompanied by erratic sensor circuit codes (`P0112`, `P0117`, `P0122`).
* **Failure Physics:** When battery or charging voltage drops below $\approx 10.5\text{V}$, ECU microcontrollers and $5\text{V}$ reference regulators experience voltage brownouts. Multiple sensors trigger false circuit low codes simultaneously.
* **Live Telemetry Signature:**
  * **Control Module Voltage (PID `42` / `ATRV`):** Reads below $12.0\text{V}$ while engine is running (normal charging is $13.5\text{V} - 14.5\text{V}$).
* **Common Physical Causes:** Failed alternator diode pack; sulfated lead-acid battery cell; corroded main chassis/engine block ground strap.

---

## 2. Live Telemetry Interpretation & Diagnostic Logic Guide

This section outlines **what the live sensor data is meant to tell us** and the exact mathematical rules of thumb used by master diagnostic technicians.

```
+---------------------------------------------------------------------------------------------------+
|                                 TELEMETRY HEURISTIC DECISION MATRIX                               |
+---------------------------------------------------------------------------------------------------+
| Metric            | Normal Range         | Diagnostic Significance & Rules of Thumb                |
|-------------------+----------------------+---------------------------------------------------------|
| STFT + LTFT       | -5% to +5%           | Total Trim > +10%: Lean condition (adding fuel)         |
|                   |                      | Total Trim < -10%: Rich condition (subtracting fuel)    |
|                   |                      | Lean at idle, normal at 2.5k RPM = VACUUM LEAK          |
|                   |                      | Lean at idle AND lean at 2.5k RPM = FUEL SUPPLY / MAF   |
|-------------------+----------------------+---------------------------------------------------------|
| Mass Air Flow     | 1.0 g/s per Liter    | Idle g/s should roughly equal engine displacement (L)   |
| (Hot Idle)        | (e.g. 3.0 g/s for 3L)| Low reading = Dirty sensor wire / intake leak           |
|-------------------+----------------------+---------------------------------------------------------|
| Upstream O2 (S1)  | 0.1V to 0.9V         | Rapid 1-2 Hz switching between lean (<0.3V) and rich    |
| (Narrowband)      | (Oscillating)        | (>0.7V). Sluggish or flatline = Failed sensor element   |
|-------------------+----------------------+---------------------------------------------------------|
| Downstream O2(S2) | 0.55V to 0.70V       | MUST be a smooth, steady line. If it mirrors Upstream   |
| (Post-Cat)        | (Steady flatline)    | switching, the CATALYTIC CONVERTER IS DEAD (P0420).     |
|-------------------+----------------------+---------------------------------------------------------|
| Coolant Temp (ECT)| 85°C to 95°C         | Below 75°C = Thermostat stuck open (P0128)              |
|                   | (185°F to 203°F)     | Above 105°C = Overheating (fan, water pump, head gasket)|
|-------------------+----------------------+---------------------------------------------------------|
| Calculated Load   | 15% to 25%           | High idle load (>35%) with A/C off indicates mechanical |
| (Hot Idle)        |                      | drag, timing chain issue, or restricted exhaust flow    |
+---------------------------------------------------------------------------------------------------+
```

### 2.1 The Master Breakdown: Short Term vs. Long Term Fuel Trim

* **Short Term Fuel Trim (STFT - PIDs `06` & `08`):**
  * **What it is:** Immediate, millisecond-level closed-loop adjustment to injector pulse width based on current oxygen sensor voltage.
  * **Behavior:** Rapidly oscillates above and below $0\%$ (typically $-3\%$ to $+3\%$) as the ECU continuously cycles between slightly rich and slightly lean to keep the catalytic converter operating at its optimum conversion window.
* **Long Term Fuel Trim (LTFT - PIDs `07` & `09`):**
  * **What it is:** Learned, persistent correction stored in non-volatile memory across an engine RPM/Load matrix (trim cells).
  * **Behavior:** Changes slowly over minutes and driving cycles. When STFT consistently stays positive (e.g., $+8\%$) over time, the ECU transfers that correction into LTFT and resets STFT back toward center ($0\%$).
* **The Total Fuel Correction Formula:**
  $$\text{Total Fuel Trim} = \text{STFT} + \text{LTFT}$$
* **Diagnostic Interpretation Rule:**
  * **Positive Trims ($> +10\%$):** The engine is running lean (too much air or too little fuel). The ECU is intentionally commanding extra fuel injector open time to compensate.
  * **Negative Trims ($< -10\%$):** The engine is running rich (too little air or too much fuel). The ECU is shortening injector pulse width.
  * **The Idle vs. 2,500 RPM Diagnostic Split:**
    $$\begin{aligned}
    \text{Idle: } +22\%, \quad \text{2,500 RPM: } +2\% &\implies \mathbf{Vacuum\ Leak\ (Air\ leak\ downstream\ of\ MAF)} \\
    \text{Idle: } +18\%, \quad \text{2,500 RPM: } +20\% &\implies \mathbf{Fuel\ Starvation\ (Pump/Filter/Injectors)\ or\ Dirty\ MAF} \\
    \text{Idle: } -16\%, \quad \text{2,500 RPM: } -18\% &\implies \mathbf{Excess\ Fuel\ (Leaking\ injector\ or\ high\ pressure)}
    \end{aligned}$$

---

## 3. Explanatory Media & Open Knowledge Graph Architecture

To empower users and diagnostic agents, our software can enrich every detected fault code and live PID with links to authoritative educational content.

```
+------------------+         +-------------------------------+         +----------------------------+
| Detected Entity  | ------> | Diagnostic Knowledge Base     | ------> | Media & Reference Links    |
| (DTC or PID)     |         | - Root Cause Taxonomy         |         | - Canonical Wikipedia URL  |
+------------------+         | - Cluster Association         |         | - Targeted YouTube Query   |
                             | - Telemetry Benchmark Rules   |         | - NHTSA Safety Recalls API |
                             +-------------------------------+         +----------------------------+
```

### 3.1 Canonical Wikipedia Automotive Knowledge Articles
* **On-Board Diagnostics:** [https://en.wikipedia.org/wiki/On-board_diagnostics](https://en.wikipedia.org/wiki/On-board_diagnostics)
* **OBD-II Parameter IDs (PIDs):** [https://en.wikipedia.org/wiki/OBD-II_PIDs](https://en.wikipedia.org/wiki/OBD-II_PIDs)
* **Fuel Trim:** [https://en.wikipedia.org/wiki/Fuel_trim](https://en.wikipedia.org/wiki/Fuel_trim)
* **Catalytic Converter:** [https://en.wikipedia.org/wiki/Catalytic_converter](https://en.wikipedia.org/wiki/Catalytic_converter)
* **Mass Flow Sensor (MAF):** [https://en.wikipedia.org/wiki/Mass_flow_sensor](https://en.wikipedia.org/wiki/Mass_flow_sensor)
* **Oxygen Sensor (Lambda):** [https://en.wikipedia.org/wiki/Oxygen_sensor](https://en.wikipedia.org/wiki/Oxygen_sensor)
* **Diagnostic Trouble Code:** [https://en.wikipedia.org/wiki/Diagnostic_trouble_code](https://en.wikipedia.org/wiki/Diagnostic_trouble_code)
* **Check Engine Light:** [https://en.wikipedia.org/wiki/Check_engine_light](https://en.wikipedia.org/wiki/Check_engine_light)
* **Variable Valve Timing:** [https://en.wikipedia.org/wiki/Variable_valve_timing](https://en.wikipedia.org/wiki/Variable_valve_timing)
* **Evaporative Emissions (EVAP):** [https://en.wikipedia.org/wiki/Evaporative_emissions_control](https://en.wikipedia.org/wiki/Evaporative_emissions_control)

### 3.2 Canonical Automotive Diagnostic YouTube Channels
* **ScannerDanner (Paul Danner):** Professor of automotive technology; master of fuel trim diagnosis, lab scope wave analysis, and scan tool live data.
  * Search pattern: `https://www.youtube.com/results?search_query=scannerdanner+{TOPIC_OR_CODE}`
* **South Main Auto Repair (Eric O.):** Real-world dealership-grade diagnostics, electrical tracing, and multi-code cluster resolution.
  * Search pattern: `https://www.youtube.com/results?search_query=south+main+auto+{TOPIC_OR_CODE}`
* **Pine Hollow Auto Diagnostics (Ivan):** In-depth oscilloscope analysis, CAN bus network failures, and intermittents.
* **Schrodingers Box:** Physics-level explanations of air-fuel ratios, oxygen sensor chemistry, and fuel trims.
* **ChrisFix:** Step-by-step DIY video guides for testing and replacing diagnosed components.

### 3.3 Dynamic Deep-Linking Engine Specification
Rather than maintaining static video links that decay when creators delete or unlist videos, our software implements a **dynamic deterministic search query generator**:
```python
def generate_media_references(dtc: str, description: str, make: str = "Toyota", model: str = "Camry") -> dict:
    encoded_query = f"diagnose+{dtc}+{make}+{model}".replace(" ", "+")
    return {
        "youtube_search_url": f"https://www.youtube.com/results?search_query={encoded_query}",
        "youtube_scannerdanner_url": f"https://www.youtube.com/results?search_query=scannerdanner+{dtc}",
        "nhtsa_recalls_api": f"https://api.nhtsa.gov/recalls/recallsByVin?vin={{VIN}}&issueType=r",
        "wiki_url": get_wikipedia_topic_for_code(dtc)
    }
```

---

## 4. Open-Source Machine Learning Datasets for Vehicle Diagnostics

For autonomous agents training anomaly detection models or classification algorithms:

1. **`EngineFaultDB` (IEEE Access & GitHub):**
   * High-frequency sensor dataset under controlled lab conditions simulating healthy operation versus specific combustion, misfire, and fuel faults (55,000+ labeled rows).
   * Paper: *EngineFaultDB: A Novel Dataset for Automotive Engine Fault Classification and Baseline Results* [IEEE Access].
   * URL: [https://github.com/leoxthomas/EngineFaultDB](https://github.com/leoxthomas/EngineFaultDB)
2. **Kaggle OBD-II Vehicle Telemetry Datasets:**
   * Features real-world drive traces recording `SHORT TERM FUEL TRIM`, `LONG TERM FUEL TRIM`, `ENGINE_RPM`, `SPEED`, and associated `TROUBLE_CODES`.
   * Useful for benchmarking normal distribution baselines against abnormal sensor behavior.
3. **NHTSA Complaints & Safety Campaign Portal:**
   * Public REST API (`api.nhtsa.gov`) providing official government defect investigation records and recalls searchable by Year/Make/Model and VIN.

---

## Appendix: Complete References, Citations & Source URLs

Below is the authoritative index of all standards, regulatory statutes, diagnostic textbooks, OEM portals, peer-reviewed literature, and open repositories cited throughout this document.

### A. Regulatory Statutes & Government Frameworks
1. **US Electronic Code of Federal Regulations — EPA Light-Duty OBD (40 CFR § 86.1806-05):**
   * *Title:* On-board diagnostics for 2005 and later model year vehicles.
   * *URL:* [https://www.ecfr.gov/current/title-40/part-86/section-86.1806-05](https://www.ecfr.gov/current/title-40/part-86/section-86.1806-05)
2. **US Electronic Code of Federal Regulations — Marine Engine Diagnostics (40 CFR § 1045.110):**
   * *Title:* How must my engines diagnose malfunctions? (Catalyzed spark-ignition sterndrive and inboard marine engines).
   * *URL:* [https://www.ecfr.gov/current/title-40/part-1045/section-1045.110](https://www.ecfr.gov/current/title-40/part-1045/section-1045.110)
3. **California Air Resources Board (CARB) OBD-II Regulations (Title 13 CCR § 1968.2):**
   * *Title:* Malfunction and Diagnostic System Requirements for 2004 and Subsequent Model-Year Passenger Cars, Light-Duty Trucks, and Medium-Duty Vehicles.
   * *URL:* [https://ww2.arb.ca.gov/our-work/programs/obd](https://ww2.arb.ca.gov/our-work/programs/obd)
4. **National Highway Traffic Safety Administration (NHTSA) APIs & Datasets Portal:**
   * *Title:* NHTSA Datasets, APIs, and Safety Campaign Web Services.
   * *URL:* [https://www.nhtsa.gov/nhtsa-datasets-and-apis](https://www.nhtsa.gov/nhtsa-datasets-and-apis)
5. **NHTSA Recalls, Complaints & Safety Issues Public Lookup:**
   * *URL:* [https://www.nhtsa.gov/recalls](https://www.nhtsa.gov/recalls)

### B. Automotive Engineering Standards (SAE & ISO)
1. **SAE J1979 / ISO 15031-5 (Diagnostic Test Modes):**
   * *SAE Portal:* [https://www.sae.org/standards/content/j1979_201702/](https://www.sae.org/standards/content/j1979_201702/)
   * *ISO Portal:* [https://www.iso.org/standard/66380.html](https://www.iso.org/standard/66380.html)
2. **SAE J2012 / ISO 15031-6 (Diagnostic Trouble Code Definitions):**
   * *SAE Portal:* [https://www.sae.org/standards/content/j2012_201612/](https://www.sae.org/standards/content/j2012_201612/)
   * *ISO Portal:* [https://www.iso.org/standard/66381.html](https://www.iso.org/standard/66381.html)
3. **SAE J1962 / ISO 15031-3 (Diagnostic Connector):**
   * *SAE Portal:* [https://www.sae.org/standards/content/j1962_201607/](https://www.sae.org/standards/content/j1962_201607/)
4. **ISO 15765-4 (Diagnostics on Controller Area Network - DoCAN):**
   * *ISO Portal:* [https://www.iso.org/standard/74768.html](https://www.iso.org/standard/74768.html)
5. **SAE J1850 (Class B Data Communication Network Interface):**
   * *SAE Portal:* [https://www.sae.org/standards/content/j1850_200606/](https://www.sae.org/standards/content/j1850_200606/)
6. **SAE J1939 (Serial Control and Communications Heavy Duty Vehicle Network):**
   * *SAE Portal:* [https://www.sae.org/standards/content/j1939_201808/](https://www.sae.org/standards/content/j1939_201808/)

### C. Professional Automotive Diagnostic Textbooks & Certification
1. **Paul Danner (ScannerDanner) — *Engine Performance Diagnostics*:**
   * *Textbook:* [https://www.scannerdanner.com/buy-the-book.html](https://www.scannerdanner.com/buy-the-book.html)
   * *YouTube Channel:* [https://www.youtube.com/@ScannerDanner](https://www.youtube.com/@ScannerDanner)
2. **National Institute for Automotive Service Excellence (ASE Certification):**
   * *ASE Test Series Overview:* [https://www.ase.com/test-series/](https://www.ase.com/test-series/)
   * *Automobile Tests A1–A9 (A8 Engine Performance):* [https://www.ase.com/test-series/automobile-tests-a1-a9/](https://www.ase.com/test-series/automobile-tests-a1-a9/)
   * *Advanced Level Specialist Tests (L1 Advanced Engine Performance):* [https://www.ase.com/test-series/advanced-level-specialist-tests-l1-l3/](https://www.ase.com/test-series/advanced-level-specialist-tests-l1-l3/)
3. **Automotive Trade Technical Publications:**
   * *Motor Magazine (Hearst Business Media):* [https://www.motor.com/](https://www.motor.com/)
   * *VehicleServicePros (PTEN & UnderhoodService Diagnostic Archive):* [https://www.vehicleservicepros.com/diagnostics](https://www.vehicleservicepros.com/diagnostics)

### D. OEM Factory Technical Information Systems
1. **Toyota Technical Information System (TIS):**
   * *Official Factory Repair Manuals & Diagnostic Trees:* [https://techinfo.toyota.com/](https://techinfo.toyota.com/)
2. **Denso Auto Parts Technical Support & Training:**
   * *Engine Management, Sensors & Fuel Systems:* [https://www.densoautoparts.com/tech-support/](https://www.densoautoparts.com/tech-support/)

### E. Academic Research & Peer-Reviewed Literature
1. **IEEE Access (2023) — *EngineFaultDB: A Novel Dataset for Automotive Engine Fault Classification and Baseline Results*:**
   * *Authors:* Leo X. Thomas, et al.
   * *IEEE Xplore Document:* [https://ieeexplore.ieee.org/document/10311222](https://ieeexplore.ieee.org/document/10311222)
   * *DOI Link:* [https://doi.org/10.1109/ACCESS.2023.3330689](https://doi.org/10.1109/ACCESS.2023.3330689)
   * *Official GitHub Dataset:* [https://github.com/leoxthomas/EngineFaultDB](https://github.com/leoxthomas/EngineFaultDB)
2. **SAE Mobilus Peer-Reviewed Research Archive:**
   * *Technical Papers on Fault Detection, Isolation & Sensor Degradation:* [https://saemobilus.sae.org/](https://saemobilus.sae.org/)

### F. Open Community Datasets & Reference Libraries
1. **`mytrile/obd-trouble-codes`:**
   * *5,000+ SAE J2012 fault codes in JSON, CSV, SQLite:* [https://github.com/mytrile/obd-trouble-codes](https://github.com/mytrile/obd-trouble-codes)
2. **`todrobbins/dtcdb`:**
   * *Diagnostic Trouble Code Database in CSV:* [https://github.com/todrobbins/dtcdb](https://github.com/todrobbins/dtcdb)
3. **`brendan-w/python-OBD`:**
   * *Python OBD-II interpreter and PID decoding formulas:* [https://github.com/brendan-w/python-OBD](https://github.com/brendan-w/python-OBD)
4. **`Ircama/ELM327-emulator`:**
   * *Async multi-ECU ELM327 emulator supporting TCP/IP:* [https://github.com/Ircama/ELM327-emulator](https://github.com/Ircama/ELM327-emulator)

