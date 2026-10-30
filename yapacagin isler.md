# Planned Work Items (Open-Starship Suite)

This document tracks planned development phases and architecture milestones for the Open-Starship suite.

---

## Phase 1: starship-flip-gnc (Flight Dynamics & Landing Flip Trajectory Optimizer)
- [x] 1.1 Model vehicle mass distribution (dry mass, landing propellant, pitch inertia, Raptor 3 cluster thrust and gimbal limits).
- [x] 1.2 Implement aerodynamic force polars (cross-sectional drag variation across angle-of-attack, barometric atmosphere).
- [x] 1.3 Implement 3-DoF landing flip trajectory solver (horizontal belly-flop to vertical touchdown, Runge-Kutta 4 integration).
- [x] 1.4 Implement flight telemetry exporter (time-series acceleration, angular rate, dynamic pressure, heat flux in JSON/CSV).
- [x] 1.5 Write and verify unit test suite (`test_models.py`, `test_aerodynamics.py`, `test_trajectory.py`, `test_telemetry.py`).
- [x] 1.6 Author `starship-flip-gnc/README.md`.

---

## Phase 2: starship-cryo-slosh (Cryogenic Propellant Slosh & Ullage Ingestion Simulator)
- [x] 2.1 Model nose LOX and inter-tank CH4 header tank geometries and cryogenic fluid properties.
- [x] 2.2 Formulate equivalent mechanical pendulum slosh equations (natural frequency, damping ratio, free-surface motion).
- [x] 2.3 Couple flight telemetry from `starship-flip-gnc` into RK4 fluid state integrator.
- [x] 2.4 Implement suction inlet submergence monitoring and turbopump gas ingestion threshold detection.
- [x] 2.5 Write and verify unit test suite (`test_tank.py`, `test_slosh.py`, `test_telemetry_coupling.py`).
- [x] 2.6 Author `starship-cryo-slosh/README.md`.

---

## Phase 3: starship-tps-vision (Heat Shield Tile Inspection & Prioritization Pipeline)
- [x] 3.1 Derive vehicle hull aerothermal risk mapping from flight peak heat flux and dynamic pressure.
- [x] 3.2 Implement synthetic hexagonal tile sector generator with injected defect modes (missing, cracked, chipped, gap expansion).
- [x] 3.3 Implement defect detection and risk-weighted priority scoring engine.
- [x] 3.4 Build structured JSON work order exporter and Markdown maintenance report generator.
- [x] 3.5 Write and verify unit test suite (`test_thermal_map.py`, `test_synthetic.py`, `test_detector.py`, `test_reporter.py`).
- [x] 3.6 Author `starship-tps-vision/README.md`.

---

## Phase 4: Extended Aerospace Capabilities & Ecosystem Upgrades
- [x] 4.1 Mechazilla chopstick tower catch kinematics and contact impulse solver (`catch_dynamics.py`).
- [x] 4.2 In-space cryogenic propellant transfer & microgravity RCS settling simulator (`orbital_transfer.py`).
- [x] 4.3 Freestanding C99 flight dynamics kernel (`starship_core.c`) and Python FFI bridge (`native_bridge.py`).
- [x] 4.4 Standalone interactive 3D WebGL flight & slosh browser visualizer (`visualizer/index.html`).
- [x] 4.5 Multi-platform GitHub Actions CI/CD matrix across Python 3.9-3.12 (`.github/workflows/ci.yml`).
- [x] 4.6 MIT License file and root README documentation with badges and Oxide ecosystem links.
