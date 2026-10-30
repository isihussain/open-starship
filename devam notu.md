# Handover & Architecture Notes (Open-Starship Suite)

This document provides developer guidelines, architectural decisions, and operational instructions for contributors and future maintainers.

---

## 1. Project Purpose & Scope
The suite models the primary physical and operational bottlenecks of the SpaceX Starship architecture:
1. **starship-flip-gnc:** 3-DoF trajectory optimization, thrust-vector control (TVC), and Mechazilla chopstick tower catch kinematics.
2. **starship-cryo-slosh:** Fluid free-surface sloshing, suction inlet gas ingestion in cryogenic header tanks, and orbital ship-to-ship propellant transfers.
3. **starship-tps-vision:** Optical defect detection and aerothermal load prioritization for 18,000+ hexagonal ceramic heat shield tiles.
4. **visualizer:** Interactive 3D WebGL flight replay and real-time slosh cutaway app.

---

## 2. Cross-Module Data Exchange Contract
```
[ starship-flip-gnc ] ──► [ Mechazilla Tower Catch Solver ]
       │                   (Chopstick pin alignment tolerances & impact load)
       │
       │ (JSON/CSV Telemetry: time, x, z, vx, vz, pitch, pitch_rate, a_lat, a_ax, q_dyn, heat_flux)
       ├─────────────────────────────────────────┐
       ▼                                         ▼
[ starship-cryo-slosh ]               [ starship-tps-vision ]
  - Mechanical pendulum slosh           - Hull aerothermal risk mapping
  - Suction line submergence            - Defect classification
  - Turbopump gas ingestion             - Ranked repair schedule (Markdown/JSON)
  - Orbital propellant transfer
```

---

## 3. Test & Verification Commands
```bash
cd /Users/johndoe/.gemini/antigravity/scratch/open-starship

# Run all 29 unit tests across the 3 packages:
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-flip-gnc/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-cryo-slosh/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-tps-vision/tests

# Run the 5-phase end-to-end pipeline:
python3 run_pipeline.py pipeline_artifacts

# Open the 3D browser visualizer:
open visualizer/index.html
```

---

## 4. Systems Compiler & Avionics Integration (Oxide)
- The numerical equations in `starship-flip-gnc` and `starship-cryo-slosh` are designed to compile directly into freestanding C99 using **[Oxide](https://github.com/isihussain/oxide-compiler)**.
- Oxide's `StageMass` verification invariant enforces that total vehicle mass never breaches physical dry mass ($m_{\text{total}} \ge m_{\text{dry}}$), eliminating negative mass singularities during flight burns.
- `native_bridge.py` dynamically compiles `starship_core.c` via standard `cc -O3 -shared -fPIC` and executes RK4 steps at native C execution speed via `ctypes`.

---

## 5. Future Development Roadmap
- **starship-flip-gnc:** Extend 3-DoF equations into a full 6-DoF rigid-body dynamic model with flap aero-moment tables.
- **starship-cryo-slosh:** Couple with 3D Smoothed Particle Hydrodynamics (SPH) solver for chaotic violent slosh regimes.
- **starship-tps-vision:** Connect PyTorch YOLOv8 / Segment Anything (SAM) weights trained on drone inspection footage from the Starbase launch tower.
