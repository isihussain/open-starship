# Handover & Architecture Notes (Open-Starship Suite)

This document provides developer guidelines, architectural decisions, and operational instructions for contributors and future maintainers.

---

## 1. Project Purpose & Scope
The suite models the primary physical, operational, and safety bottlenecks across next-generation reusable launch vehicles:
1. **starship-flip-gnc:** 3-DoF trajectory optimization, thrust-vector control (TVC), Mechazilla chopstick tower catch kinematics, and aerospace incident safety interlocks.
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
       │                                         │
       ├─────────────────────────────────────────┘
       ▼
[ Aerospace Incident Safety Interlocks ]
  - Test stand breakaway interlock (Tianlong-3)
  - Touchdown multi-sensor gate (Nebula-1)
  - Actuator fault reallocation (Hyperbola-1)
  - Engine-out trim & burn reshaping (Zhuque-2)
  - Instantaneous impact point & geofencing (Long March)
       │
       ▼
 [ 3D WebGL Flight Visualizer ]
```

---

## 3. Test & Verification Commands
```bash
cd /Users/johndoe/.gemini/antigravity/scratch/open-starship

# Run all 55 unit tests across the 3 packages:
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-flip-gnc/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-cryo-slosh/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision" python3 -m unittest discover -s starship-tps-vision/tests

# Run the 6-phase end-to-end pipeline:
python3 run_pipeline.py pipeline_artifacts

# Open the 3D browser visualizer:
open visualizer/index.html
```

---

## 4. Aerospace Incident Safety Architecture

The aerospace safety subsystem (`starship-flip-gnc`) guards against failure modes identified across CNSA and commercial NewSpace incident data:

1. **`test_stand_safety.py` (Space Pioneer Tianlong-3, June 2024):**
   - *Failure Mode:* Static fire hold-down clamps sheared; flight software lacked automated abort triggers for test-stand breakaway, allowing the vehicle to climb to 2 km before impact.
   - *Architecture:* In `STATIC_FIRE` mode, the module trips an irreversible emergency cutoff and tank depressurization if vertical displacement exceeds 30 mm, upward acceleration $\ddot{z} > 0.05\text{ g}$, or umbilical disconnect occurs during firing.

2. **`touchdown_gate.py` (Deep Blue Aerospace Nebula-1, September 2024):**
   - *Failure Mode:* Rocket exhaust plume dust backscatter caused a single radar altimeter to report 0 m at 5 m altitude, causing premature engine shutdown and a hard landing.
   - *Architecture:* Evaluates multi-channel consensus (radar, LiDAR, INS) to reject backscatter outliers. Requires dual confirmation before allowing engine cutoff: fused altitude $\le 0.40\text{ m}$ AND mechanical contact load $\ge 40\text{ kN}$ on physical microswitches. If cutoff is commanded prematurely, it commands a safe hover throttle override.

3. **`actuator_fault_allocator.py` (i-Space Hyperbola-1 Y5, August 2021):**
   - *Failure Mode:* Detached thermal foam jammed a grid fin hinge; lack of adaptive torque reallocation caused uncontrollable roll rates and vehicle destruction.
   - *Architecture:* Detects motor current stall saturation ($I \ge 40\text{ A}$) with tracking divergence over multiple control frames. Isolates the jammed surface, calculates its parasitic aerodynamic torque at dynamic pressure $q$, and solves least-squares reallocation across active surfaces and RCS thrusters.

4. **`engine_out_recovery.py` (LandSpace Zhuque-2 / Multi-engine vehicles):**
   - *Failure Mode:* Sudden flameout of an off-axis engine induces uncompensated pitching/yawing disturbance moments and cuts descent deceleration.
   - *Architecture:* Determines gimbal trim angles directing the net thrust vector through the center of mass. Adjusts operational engine throttles to preserve required thrust-to-weight ratio (TWR), and extends burn duration via numerical integration of the rocket equation.

5. **`debris_hazard_predictor.py` (CNSA Long March inland corridors):**
   - *Failure Mode:* Spent booster stages falling into populated inland villages.
   - *Architecture:* Projects instantaneous ballistic and drag-retarded impact coordinates (IIP), models 3-sigma dispersion ellipses, checks polygon geofences, and calculates divert $\Delta \mathbf{v}$ vectors to steer stages into safe corridors, or flags autonomous flight termination (AFTS).

---

## 5. Systems Compiler & Avionics Integration (Oxide)
- The numerical equations in `starship-flip-gnc` and `starship-cryo-slosh` compile directly into freestanding C99 using **[Oxide](https://github.com/isihussain/oxide-compiler)**.
- Oxide's `StageMass` verification invariant enforces that total vehicle mass never breaches physical dry mass ($m_{\text{total}} \ge m_{\text{dry}}$), eliminating negative mass singularities during flight burns.
- `native_bridge.py` dynamically compiles `starship_core.c` via standard `cc -O3 -shared -fPIC` and executes RK4 steps at native C execution speed via `ctypes`.

---

## 6. Future Development Roadmap
- **starship-flip-gnc:** Extend 3-DoF equations into a full 6-DoF rigid-body dynamic model with flap aero-moment tables.
- **starship-cryo-slosh:** Couple with 3D Smoothed Particle Hydrodynamics (SPH) solver for chaotic violent slosh regimes.
- **starship-tps-vision:** Connect PyTorch YOLOv8 / Segment Anything (SAM) weights trained on drone inspection footage from the Starbase launch tower.
