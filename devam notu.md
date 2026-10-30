# Handover & Architecture Notes (Open-Starship Suite)

This document provides developer guidelines, architectural decisions, and operational instructions for contributors and future maintainers.

---

## 1. Project Purpose & Scope
The suite models the three primary physical and operational bottlenecks of the SpaceX Starship architecture:
1. **starship-flip-gnc:** 3-DoF trajectory optimization and thrust-vector control (TVC) for the horizontal belly-flop to vertical landing maneuver.
2. **starship-cryo-slosh:** Fluid free-surface sloshing, center-of-mass excursions, and suction inlet gas ingestion in cryogenic header tanks during high-g reorientation.
3. **starship-tps-vision:** Optical defect detection and aerothermal load prioritization for 18,000+ hexagonal ceramic heat shield tiles.

---

## 2. Cross-Module Data Exchange Contract
```
[ starship-flip-gnc ]
       │
       │ (JSON/CSV Telemetry: time, x, z, vx, vz, pitch, pitch_rate, a_lat, a_ax, q_dyn, heat_flux)
       ├─────────────────────────────────────────┐
       ▼                                         ▼
[ starship-cryo-slosh ]               [ starship-tps-vision ]
  - Mechanical pendulum slosh           - Hull aerothermal risk mapping
  - Suction line submergence            - Defect classification
  - Disturbance torque output           - Ranked repair schedule (Markdown/JSON)
```

---

## 3. Test & Verification Commands
```bash
cd /Users/johndoe/.gemini/antigravity/scratch/open-starship

# Run all unit tests across the 3 packages:
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-flip-gnc/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-cryo-slosh/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-tps-vision/tests

# Run the end-to-end pipeline:
python3 run_pipeline.py pipeline_artifacts
```

---

## 4. Systems Compiler & Avionics Integration (Oxide)
- The numerical equations in `starship-flip-gnc` and `starship-cryo-slosh` are designed to compile directly into freestanding C99 using **[Oxide](https://github.com/isihussain/oxide-compiler)**.
- Oxide's `StageMass` verification invariant enforces that total vehicle mass never breaches physical dry mass ($m_{\text{total}} \ge m_{\text{dry}}$), eliminating negative mass singularities during flight burns.
- Emitted C99 files can be compiled into `.so`/`.dylib` shared libraries and called from Python via `ctypes`.

---

## 5. Future Development Roadmap
- **starship-flip-gnc:** Extend 3-DoF equations into a full 6-DoF rigid-body dynamic model with flap aero-moment tables.
- **starship-cryo-slosh:** Implement a multi-mode pendulum model or a low-resolution Smoothed Particle Hydrodynamics (SPH) solver.
- **starship-tps-vision:** Connect PyTorch YOLOv8 / Segment Anything (SAM) weights trained on drone inspection footage from the Starbase launch tower.
