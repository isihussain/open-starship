# Open-Starship

An open-source engineering suite that models and solves three physical and operational bottlenecks in the SpaceX Starship architecture:

1. **`starship-flip-gnc`**: 3-DoF trajectory optimization and thrust-vector control (TVC) solver for the horizontal belly-flop to vertical landing maneuver.
2. **`starship-cryo-slosh`**: Reduced-order mechanical pendulum simulator for cryogenic propellant sloshing and ullage gas ingestion in header tanks during high-g reorientation.
3. **`starship-tps-vision`**: Inspection pipeline that fuses aerothermal flight loads with ground optical sensor data to identify and prioritize damaged Thermal Protection System (TPS) hexagonal tiles.

---

## Architecture & Data Flow

```
[ starship-flip-gnc ]
       │
       │ (Flight Telemetry: time, lateral/axial accel, pitch rate, dynamic pressure, heat flux)
       ├─────────────────────────────────────────┐
       ▼                                         ▼
[ starship-cryo-slosh ]               [ starship-tps-vision ]
  - Equivalent pendulum fluid motion    - Hull aerothermal risk mapping
  - Suction inlet submergence tracking  - Defect detection (missing, cracked, chipped, gap)
  - Turbopump gas ingestion warnings    - Prioritized maintenance work orders (Markdown/JSON)
  - Slosh disturbance torque output
```

---

## Repository Structure

```
open-starship/
├── starship-flip-gnc/     # Flight dynamics & 3-DoF landing flip trajectory optimizer
├── starship-cryo-slosh/   # Cryogenic propellant slosh & ullage gas ingestion analyzer
├── starship-tps-vision/   # TPS heat shield tile defect detection & work order pipeline
├── run_pipeline.py        # End-to-end orchestration runner connecting all three modules
├── yapacagin isler.md     # Planned development milestones
├── yaptigin isler.md      # Completed technical report & verification logs
├── devam notu.md          # Architectural handover notes for developers
└── README.md              # Root project documentation
```

---

## Quickstart

Requires Python 3.9+. Runs with zero external C-compiler dependencies.

### Run End-to-End Pipeline

```bash
python3 run_pipeline.py pipeline_artifacts
```

This single command:
1. Simulates the 3-engine flip and 1-engine terminal touchdown descent, writing time-series flight telemetry to `pipeline_artifacts/flight_telemetry.json`.
2. Passes dynamic acceleration and body rates to the cryogenic header tank simulator, outputting slosh angles, suction submergence, and ingestion warnings to `pipeline_artifacts/slosh_dynamics.json`.
3. Maps peak aerothermal heating and dynamic pressure to hull coordinates, inspects 600 hexagonal tiles, and writes a ranked repair schedule to `pipeline_artifacts/tps_maintenance_work_order.md`.

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

The flight dynamic models and mass-depletion laws in this project are designed to integrate with **[Oxide (oxide-compiler)](https://github.com/isihussain/oxide-compiler)**, our independent C++20 Rust compiler:

* **Zero-Dependency Freestanding C99:** The numerical guidance and slosh models compile via Oxide's `StageMass` verification invariants ($m_{\text{total}} \ge m_{\text{dry}}$), targeting bare-metal flight computers and radiation-hardened microcontrollers (ARM, RISC-V, LEON) without `rustc` or LLVM overhead.
* **Deterministic Execution:** Eliminates garbage collection pauses and nondeterministic heap allocations in the flight-critical guidance loop.

---

## Contributing & Support

Contributions are welcome under the MIT License. Engineers are invited to fork any module, plug in vehicle parameters, or extend the inspection algorithms.

* **GitHub Sponsors:** [github.com/sponsors/isihussain](https://github.com/sponsors/isihussain)

> **Developer Note:** I have developed this project over the past 3 years in my local Git environment. My decision to publish it as open source is driven by my commitment to supporting the establishment of permanent human colonies and settlements on other worlds.
