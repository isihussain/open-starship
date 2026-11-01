# Open-Starship

[![CI](https://github.com/isihussain/open-starship/actions/workflows/ci.yml/badge.svg)](https://github.com/isihussain/open-starship/actions/workflows/ci.yml)
[![Live 3D Visualizer](https://img.shields.io/badge/Live%20Demo-3D%20Visualizer-38bdf8?style=flat-square&logo=google-chrome&logoColor=white)](https://isihussain.github.io/open-starship/)
[![Tests](https://img.shields.io/badge/tests-69%20passed-22c55e.svg)](https://github.com/isihussain/open-starship)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-38bdf8.svg)](https://www.python.org)
[![Compiler](https://img.shields.io/badge/verified%20by-Oxide%20C%2B%2B20-orange.svg)](https://github.com/isihussain/oxide-compiler)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An open-source engineering suite that models and solves fundamental physical, operational, and safety challenges across next-generation reusable spacecraft, orbital transfer stages, and geostationary satellite platforms:

1. **`starship-flip-gnc`**: 3-DoF trajectory optimization, thrust-vector control (TVC), Mechazilla chopstick tower catch kinematics, and aerospace flight safety interlocks.
2. **`starship-cryo-slosh`**: Reduced-order mechanical pendulum simulator for cryogenic propellant sloshing, ullage gas ingestion, and orbital ship-to-ship propellant transfers.
3. **`starship-tps-vision`**: Inspection pipeline fusing flight aerothermal load maps with optical sensor data to identify and prioritize damaged Thermal Protection System (TPS) hexagonal tiles.
4. **`starship-geo-sat`**: Geostationary satellite operations, electric orbit raising (EOR), zero-magnetic-field reaction wheel desaturation, and transponder payload protection derived from the Türksat satellite program (Türksat 1A through 6A).
5. **`visualizer/`**: Interactive 3D WebGL flight and slosh visualizer running directly in any modern browser without installation.

---

## Architecture & Data Flow

```
[ starship-flip-gnc ] ──► [ Mechazilla Tower Catch Solver ]
       │                   (Chopstick pin alignment tolerances & impact load)
       │
       │ (Flight Telemetry: time, lateral/axial accel, pitch rate, dynamic pressure, heat flux)
       ├─────────────────────────────────────────┐
       ▼                                         ▼
[ starship-cryo-slosh ]               [ starship-tps-vision ]
  - Equivalent pendulum fluid motion    - Hull aerothermal risk mapping
  - Suction inlet submergence tracking  - Defect detection (missing, cracked, chipped, gap)
  - Turbopump gas ingestion warnings    - Prioritized maintenance work orders (Markdown/JSON)
  - In-space propellant transfer        
       │                                         │
       ├─────────────────────────────────────────┘
       ▼
[ Aerospace Incident Safety Interlocks ]
  - Test stand hold-down breakaway abort guard (Space Pioneer Tianlong-3)
  - Multi-sensor consensus & Weight-on-Wheels touchdown gate (Deep Blue Nebula-1)
  - Aerodynamic surface jam detection & torque reallocation (i-Space Hyperbola-1)
  - Engine-out asymmetric thrust compensation & burn reshaping (LandSpace Zhuque-2)
  - Ballistic Instantaneous Impact Point (IIP) & geofence predictor (Long March corridors)
       │
       ▼
[ starship-geo-sat: Geostationary Satellite Operations & Türksat Mitigations ]
  - Upper-stage cryogenic turbopump failure & suborbital abort detector (Türksat 1A)
  - Propellant depletion, lunisolar drift & inclined orbit ground tracking (Türksat 1B/1C)
  - Electric orbit raising (EOR) & Van Allen radiation damage integration (Türksat 5A/5B)
  - Weak-magnetic-field reaction wheel momentum desaturation via thrusters (Türksat 6A)
  - Transponder cross-polarization guard & Ka-band rain fade AUPC (Türksat 3A/4A/4B)
       │
       ▼
 [ 3D WebGL Flight Visualizer ]
  (visualizer/index.html)
```

---

## Aerospace Launch & Flight Safety Interlocks

The launch vehicle safety subsystem incorporates mitigations derived from real-world aerospace launch, static-fire, and landing incidents across CNSA and commercial NewSpace flight data:

| Subsystem Module | Incident Origin | Failure Mode | Algorithmic Mitigation |
| :--- | :--- | :--- | :--- |
| **`test_stand_safety.py`** | **Space Pioneer Tianlong-3** (June 2024) | Static-fire test stand clamps yielded under 800-ton thrust; missing hold-down abort software allowed the booster to launch and crash into hills. | Enforces sub-20ms emergency engine cutoff and tank venting whenever vertical displacement exceeds 30 mm, acceleration $\ddot{z} > 0.05\text{ g}$, or clamp tension drops below 70% of thrust. |
| **`touchdown_gate.py`** | **Deep Blue Aerospace Nebula-1** (September 2024) | Rocket plume dust backscatter corrupted the radar altimeter at 5 m above pad, commanding premature engine cutoff and a free-fall impact. | Multi-channel median consensus (radar, LiDAR, INS) coupled with a dual-condition gate: engine shutdown requires BOTH fused altitude $\le 0.4\text{ m}$ AND physical compressive load $\ge 40\text{ kN}$ on contact switches. |
| **`actuator_fault_allocator.py`** | **i-Space Hyperbola-1 Y5** (August 2021) | Grid-fin hinge jammed from detached thermal insulation; flight software failed to reallocate control moments, resulting in attitude departure and breakup. | Detects actuator motor stall current saturation ($I \ge 40\text{ A}$) with tracking divergence, freezes the failed surface, subtracts its parasitic aerodynamic torque, and solves a pseudo-inverse reallocation across active flaps and RCS. |
| **`engine_out_recovery.py`** | **LandSpace Zhuque-2** / Multi-engine stages | Single engine flameout causes asymmetric pitching/yawing moments and insufficient descent deceleration. | Computes TVC gimbal trim angles to route the net thrust vector through the vehicle center of mass, throttles operational engines up, and reshapes burn duration using the rocket equation. |
| **`debris_hazard_predictor.py`** | **CNSA Long March** inland corridors | Spent first stages and boosters dropping uncontrolled into inhabited inland villages. | Computes real-time vacuum and drag-retarded Instantaneous Impact Points (IIP), evaluates 3-sigma dispersion bounds against population geofences, and calculates corrective divert velocity vectors ($\Delta \mathbf{v}_{\text{divert}}$) or AFTS triggers. |

---

## Geostationary Satellite Operations (Türksat Fleet Mitigations)

The `starship-geo-sat` package solves operational, orbital mechanics, and space environment failure modes documented across Turkey's national satellite telecommunications fleet:

| Subsystem Module | Historical Reference | Operational Bottleneck | Algorithmic Solution |
| :--- | :--- | :--- | :--- |
| **`launch_abort_detector.py`** | **Türksat 1A** (Ariane 44LP V63, 1994) | Cryogenic third-stage LOX turbopump valve failed; stage underperformed and terminated early, dropping the satellite into the Atlantic Ocean. | Monitors chamber pressure gradient ($\frac{dP_c}{dt}$), turbopump RPM, and stage velocity shortfall. Calculates instantaneous ballistic impact point and triggers spacecraft contingency safing. |
| **`inclined_orbit_dynamics.py`** | **Türksat 1B & 1C** (2005, 2008) | Chemical propellant depleted for North-South station-keeping ($~45\text{ m/s per year}$). Lunisolar third-body gravity caused ~0.86°/year natural inclination drift, causing figure-eight ground tracks and link dropouts. | Models orbital element secular drift under lunar and solar gravity. Calculates ground antenna Azimuth/Elevation pointing corrections and verifies propellant reserve for graveyard disposal ($+235\text{ km} + 1000 C_R \frac{A}{m}$). |
| **`electric_orbit_raising.py`** | **Türksat 5A & 5B** (Eurostar E3000EOR, 2021) | Hall-effect electric orbit raising takes 140 to 160 days from GTO to GEO, exposing solar cells to extended proton and electron radiation within the Van Allen belts. | Low-thrust Gauss-variational spiral propagator. Integrates equivalent 1-MeV electron fluence across belt passes and calculates solar array non-ionizing energy loss (NIEL) power degradation. |
| **`reaction_wheel_desat.py`** | **Türksat 6A** (Indigenous Platform, 2024) | Earth's magnetic field at 35,786 km is negligible (~100 nT), rendering magnetic torquers useless. Solar radiation pressure accumulates angular momentum in reaction wheels. | Formulates coupled minimum-propellant pulsed thruster desaturation firing sequences with zero net translational force, preventing station-keeping deadband violations ($\pm 0.05^\circ$). |
| **`rfi_transponder_guard.py`** | **Türksat 3A, 4A, 4B** (2008–Present) | Terrestrial uplink cross-polarization leakage (XPI < 25 dB), TWTA non-linear saturation from rogue carriers, and Ka-band rain fade (up to 20 dB loss at 30 GHz). | Implements Saleh non-linear TWTA gain compression modeling, co-channel cross-polarization violation detection, and automated uplink power control (AUPC) feedback commands. |

---

## Repository Structure

```
open-starship/
├── .github/workflows/ci.yml # Multi-platform CI (Ubuntu, macOS, Python 3.10-3.12)
├── starship-flip-gnc/     # Flight dynamics, 3-DoF optimizer, Mechazilla catch, safety interlocks
│   ├── starship_flip_gnc/ # GNC models, aerodynamics, trajectory, catch, incident interlocks
│   │   ├── models.py                   # Vehicle geometry, Raptor cluster limits, flight state
│   │   ├── aerodynamics.py             # Drag, lift, atmospheric density, aerothermal flux
│   │   ├── trajectory.py               # 3-phase landing flip trajectory solver (RK4)
│   │   ├── catch_dynamics.py           # Mechazilla chopstick tower capture solver
│   │   ├── test_stand_safety.py        # Static fire clamp breakaway interlock (Tianlong-3)
│   │   ├── touchdown_gate.py           # Multi-sensor consensus & touchdown gate (Nebula-1)
│   │   ├── actuator_fault_allocator.py # Aerodynamic surface jam allocator (Hyperbola-1)
│   │   ├── engine_out_recovery.py      # Asymmetric engine-out gimbal & burn reshaper (Zhuque-2)
│   │   ├── debris_hazard_predictor.py  # Instantaneous impact point & geofence monitor
│   │   ├── telemetry.py                # Flight telemetry logger and schema exporter
│   │   └── native_bridge.py            # Python C-ABI FFI wrapper
│   ├── native/            # Freestanding C99 core (starship_core.c)
│   └── tests/             # Unit test suite (37 tests)
├── starship-cryo-slosh/   # Cryogenic propellant slosh & orbital transfer simulator
│   ├── starship_cryo_slosh/ # Tank geometry, pendulum model, simulator, orbital transfer
│   └── tests/             # Unit test suite (11 tests)
├── starship-tps-vision/   # TPS heat shield tile defect detection & work order pipeline
│   ├── starship_tps_vision/ # Risk map, synthetic generator, detector, reporter
│   └── tests/             # Unit test suite (7 tests)
├── starship-geo-sat/      # Geostationary satellite operations & Türksat incident mitigations
│   ├── starship_geo_sat/  # Launch abort, inclined orbit, electric orbit raising, desat, RFI guard
│   │   ├── launch_abort_detector.py    # Cryogenic upper-stage turbopump abort (Türksat 1A)
│   │   ├── inclined_orbit_dynamics.py  # Lunisolar drift & ground antenna tracking (Türksat 1B/1C)
│   │   ├── electric_orbit_raising.py   # Hall-effect spiral & Van Allen radiation (Türksat 5A/5B)
│   │   ├── reaction_wheel_desat.py     # GEO zero-B reaction wheel desaturation (Türksat 6A)
│   │   └── rfi_transponder_guard.py    # Cross-polarization leakage & Ka-band rain fade AUPC
│   └── tests/             # Unit test suite (14 tests)
├── visualizer/            # Standalone 3D Three.js flight & slosh browser visualizer
│   └── index.html         # Interactive real-time 3D telemetry and tank cutaway app
├── run_pipeline.py        # 7-phase end-to-end orchestration runner
├── yapacagin isler.md     # Milestone tracking specification
├── yaptigin isler.md      # Completed technical report & verification logs
├── devam notu.md          # Architectural handover notes for developers
└── README.md              # Root project documentation
```

---

## Quickstart

Requires Python 3.9+. Runs with zero required external dependencies.

### 1. Run 7-Phase End-to-End Pipeline

```bash
python3 run_pipeline.py pipeline_artifacts
```

This single command executes:
1. **Landing Flip Simulation**: Solves 3-engine flip and 1-engine touchdown to `pipeline_artifacts/flight_telemetry.json`.
2. **Cryogenic Slosh Dynamics**: Evaluates header tank free-surface displacement and turbopump gas ingestion risks to `pipeline_artifacts/slosh_dynamics.json`.
3. **TPS Damage Work Order**: Evaluates 600 hexagonal tiles against flight peak heat flux to `pipeline_artifacts/tps_maintenance_work_order.md`.
4. **Mechazilla Chopstick Catch**: Evaluates pin capture tolerances ($\pm 0.5\text{ m}$ lateral, $< 0.4\text{ m/s}$ descent) and structural contact loads.
5. **In-Space Propellant Transfer**: Simulates microgravity RCS ullage settling (Bond number $Bo > 50$) and pressure-driven cryogenic mass transfer from Tanker to Depot.
6. **Incident Safety Interlocks**: Validates hold-down breakaway cutoff, touchdown consensus, actuator jam reallocation, engine-out gimbal trim, and debris footprint geofencing to `pipeline_artifacts/incident_safety_validation.json`.
7. **Geostationary Satellite Operations**: Validates upper-stage abort detection, inclined orbit tracking, electric orbit raising radiation damage, reaction wheel desaturation, and transponder interference protection to `pipeline_artifacts/geo_satellite_validation.json`.

### 2. Launch Mission Control Visualizer

Open `visualizer/index.html` directly in any web browser — no build step, no server required:

```bash
open visualizer/index.html
```

The visualizer has five tabs, each backed by a live JS simulation that mirrors the Python models exactly:

| Tab | What it shows |
|-----|---------------|
| **Flight & GNC** | Three.js 3D scene with TPS tile hull detail, 3 individual Raptor nozzle plumes, Mechazilla chopstick arm with catch pins; live altitude / speed / heat flux HUD; mini charts for altitude and vertical speed |
| **Cryo Slosh** | LOX and CH4 pendulum canvas cutaway; slosh angle chart; gas ingestion threshold indicator |
| **Safety Interlocks** | Live status grid for all 6 interlocks (hold-down clamp, touchdown gate, actuator allocation, engine-out, IIP, AFTS); incident reference library for all 5 CNSA/NewSpace incidents |
| **GEO-SAT** | All 5 Türksat subsystem displays: abort detector state machine, inclined-orbit AZ/EL tracker, EOR spiral day counter, reaction wheel desat momentum bars, transponder XPI/AUPC gauge |
| **TPS Tiles** | 6-zone hull aerothermal risk map (canvas); tile count summary by zone and defect category; live heat flux chart |

**Loading recorded pipeline data:** click "Load JSON" and select `pipeline_artifacts/flight_telemetry.json` produced by `run_pipeline.py`. The visualizer replaces its simulation with the recorded trace.

---

## Standalone Subpackage Usage

Each module can be run and tested independently:

### 1. starship-flip-gnc

```bash
cd starship-flip-gnc
python3 -m unittest discover -s tests
python3 -m starship_flip_gnc.cli --altitude 500.0 --vz -70.0 --export-json telemetry.json
```

### 2. starship-cryo-slosh

```bash
cd starship-cryo-slosh
python3 -m unittest discover -s tests
python3 -m starship_cryo_slosh.cli --telemetry ../starship-flip-gnc/telemetry.json --with-baffles
```

### 3. starship-tps-vision

```bash
cd starship-tps-vision
python3 -m unittest discover -s tests
python3 -m starship_tps_vision.cli --telemetry ../starship-flip-gnc/telemetry.json --export-markdown work_order.md
```

### 4. starship-geo-sat

```bash
cd starship-geo-sat
python3 -m unittest discover -s tests
```

---

## Avionics & Systems Compiler Integration (Oxide)

The flight dynamic kernels, safety interlocks, and mass-depletion laws in this project integrate with **[Oxide (oxide-compiler)](https://github.com/isihussain/oxide-compiler)**, an independent C++20 compiler for aerospace control software:

* **Zero-Dependency Freestanding C99 (`starship_core.c`):** The numerical guidance and slosh models compile via Oxide's `StageMass` verification invariants ($m_{\text{total}} \ge m_{\text{dry}}$), targeting bare-metal flight computers and radiation-hardened microcontrollers (ARM Cortex-R, RISC-V, LEON) without `rustc` or LLVM overhead.
* **Native C-ABI Speedup:** Includes `native_bridge.py`, an FFI bridge compiling and dispatching 4th-order Runge-Kutta steps at native C execution speeds.

---

## Contributing & Support

Contributions are welcome under the MIT License. Engineers are invited to fork any module, plug in vehicle parameters, or extend the inspection algorithms.

* **GitHub Sponsors:** [github.com/sponsors/isihussain](https://github.com/sponsors/isihussain)

> **Developer Note:** I have developed this project over the past 3 years in my local Git environment. My decision to publish it as open source is driven by my commitment to supporting the establishment of permanent human colonies and settlements on other worlds.
