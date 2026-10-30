# Open-Starship

[![CI](https://github.com/isihussain/open-starship/actions/workflows/ci.yml/badge.svg)](https://github.com/isihussain/open-starship/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-29%20passed-22c55e.svg)](https://github.com/isihussain/open-starship)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-38bdf8.svg)](https://www.python.org)
[![Compiler](https://img.shields.io/badge/verified%20by-Oxide%20C%2B%2B20-orange.svg)](https://github.com/isihussain/oxide-compiler)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An open-source engineering suite that models and solves fundamental physical and operational challenges across next-generation reusable spacecraft:

1. **`starship-flip-gnc`**: 3-DoF trajectory optimization, thrust-vector control (TVC), and Mechazilla chopstick tower catch kinematics.
2. **`starship-cryo-slosh`**: Reduced-order mechanical pendulum simulator for cryogenic propellant sloshing, ullage gas ingestion, and orbital ship-to-ship propellant transfers.
3. **`starship-tps-vision`**: Inspection pipeline fusing flight aerothermal load maps with optical sensor data to identify and prioritize damaged Thermal Protection System (TPS) hexagonal tiles.
4. **`visualizer/`**: Interactive 3D WebGL flight and slosh visualizer running directly in any modern browser without installation.

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
       └────────────────────┬────────────────────┘
                            ▼
              [ 3D WebGL Flight Visualizer ]
               (visualizer/index.html)
```

---

## Repository Structure

```
open-starship/
├── .github/workflows/ci.yml # Multi-platform CI (Ubuntu, macOS, Python 3.9-3.12)
├── starship-flip-gnc/     # Flight dynamics, 3-DoF optimizer, Mechazilla catch, C99 kernel
│   ├── starship_flip_gnc/ # GNC models, aerodynamics, trajectory, catch dynamics, FFI
│   ├── native/            # Freestanding C99 core (starship_core.c)
│   └── tests/             # Unit test suite (11 tests)
├── starship-cryo-slosh/   # Cryogenic propellant slosh & orbital transfer simulator
│   ├── starship_cryo_slosh/ # Tank geometry, pendulum model, simulator, orbital transfer
│   └── tests/             # Unit test suite (11 tests)
├── starship-tps-vision/   # TPS heat shield tile defect detection & work order pipeline
│   ├── starship_tps_vision/ # Risk map, synthetic generator, detector, reporter
│   └── tests/             # Unit test suite (7 tests)
├── visualizer/            # Standalone 3D Three.js flight & slosh browser visualizer
│   └── index.html         # Interactive real-time 3D telemetry and tank cutaway app
├── run_pipeline.py        # 5-phase end-to-end orchestration runner
├── yapacagin isler.md     # Milestone tracking specification
├── yaptigin isler.md      # Completed technical report & verification logs
├── devam notu.md          # Architectural handover notes for developers
└── README.md              # Root project documentation
```

---

## Quickstart

Requires Python 3.9+. Runs with zero required external dependencies.

### 1. Run 5-Phase End-to-End Pipeline

```bash
python3 run_pipeline.py pipeline_artifacts
```

This single command executes:
1. **Landing Flip Simulation**: Solves 3-engine flip and 1-engine touchdown to `pipeline_artifacts/flight_telemetry.json`.
2. **Cryogenic Slosh Dynamics**: Evaluates header tank free-surface displacement and turbopump gas ingestion risks to `pipeline_artifacts/slosh_dynamics.json`.
3. **TPS Damage Work Order**: Evaluates 600 hexagonal tiles against flight peak heat flux to `pipeline_artifacts/tps_maintenance_work_order.md`.
4. **Mechazilla Chopstick Catch**: Evaluates pin capture tolerances ($\pm 0.5\text{ m}$ lateral, $< 0.4\text{ m/s}$ descent) and structural contact loads.
5. **In-Space Propellant Transfer**: Simulates microgravity RCS ullage settling (Bond number $Bo > 50$) and pressure-driven cryogenic mass transfer from Tanker to Depot.

### 2. Launch 3D Flight & Slosh Visualizer

Open `visualizer/index.html` directly in any web browser:

```bash
open visualizer/index.html
```

* **Interactive 3D Starship Model**: Real-time rendering of pitch reorientation, engine gimbal deflection, and dynamic plume throttle.
* **Launch Tower & Chopsticks**: Animated landing capture targeting the Mechazilla tower arms.
* **Live Header Tank Cutaway**: Real-time liquid free-surface slosh angle and suction inlet submergence monitoring.
* **Custom Telemetry Ingestion**: Load any generated `flight_telemetry.json` via the file picker.

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

---

## Avionics & Systems Compiler Integration (Oxide)

The flight dynamic kernels and mass-depletion laws in this project are designed to integrate with **[Oxide (oxide-compiler)](https://github.com/isihussain/oxide-compiler)**, our independent C++20 Rust compiler:

* **Zero-Dependency Freestanding C99 (`starship_core.c`):** The numerical guidance and slosh models compile via Oxide's `StageMass` verification invariants ($m_{\text{total}} \ge m_{\text{dry}}$), targeting bare-metal flight computers and radiation-hardened microcontrollers (ARM Cortex-R, RISC-V, LEON) without `rustc` or LLVM overhead.
* **Native C-ABI Speedup:** Includes `native_bridge.py`, an FFI bridge compiling and dispatching 4th-order Runge-Kutta steps at native C execution speeds.

---

## Contributing & Support

Contributions are welcome under the MIT License. Engineers are invited to fork any module, plug in vehicle parameters, or extend the inspection algorithms.

* **GitHub Sponsors:** [github.com/sponsors/isihussain](https://github.com/sponsors/isihussain)

> **Developer Note:** I have developed this project over the past 3 years in my local Git environment. My decision to publish it as open source is driven by my commitment to supporting the establishment of permanent human colonies and settlements on other worlds.
