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

---

## Phase 5: Aerospace Incident Safety Interlocks (CNSA & Global Failure Mitigations)
- [x] 5.1 Test stand structural breakaway interlock & premature liftoff abort guard (`test_stand_safety.py` - Space Pioneer Tianlong-3).
- [x] 5.2 Multi-sensor consensus & Weight-on-Wheels touchdown gate (`touchdown_gate.py` - Deep Blue Aerospace Nebula-1).
- [x] 5.3 Aerodynamic control surface jam detection & torque authority reallocation (`actuator_fault_allocator.py` - i-Space Hyperbola-1 Y5).
- [x] 5.4 Engine-out asymmetric thrust compensation & burn duration reshaping (`engine_out_recovery.py` - LandSpace Zhuque-2).
- [x] 5.5 Ballistic Instantaneous Impact Point (IIP) & population corridor geofence predictor (`debris_hazard_predictor.py` - CNSA Long March corridors).
- [x] 5.6 Comprehensive unit test coverage across all safety modules (19 new tests, 37 total in `flip-gnc`, 55 overall).
- [x] 5.7 End-to-end integration into `run_pipeline.py` emitting `pipeline_artifacts/incident_safety_validation.json`.
- [x] 5.8 Open and resolve dedicated GitHub issues (#12, #13, #14, #15, #16).

---

## Phase 6: starship-geo-sat (Geostationary Operations & Türksat Incident Mitigations)
- [x] 6.1 Cryogenic upper-stage turbopump valve failure & suborbital abort detector (`launch_abort_detector.py` - Türksat 1A).
- [x] 6.2 Propellant exhaustion, lunisolar inclination drift & ground tracking compensation (`inclined_orbit_dynamics.py` - Türksat 1B/1C).
- [x] 6.3 Hall-effect electric orbit raising (EOR) & Van Allen radiation damage integration (`electric_orbit_raising.py` - Türksat 5A/5B).
- [x] 6.4 Zero-magnetic-field reaction wheel desaturation via pure-torque thruster couples (`reaction_wheel_desat.py` - Türksat 6A).
- [x] 6.5 Transponder cross-polarization interference (XPI) & Ka-band rain fade AUPC guard (`rfi_transponder_guard.py` - Türksat 3A/4A/4B).
- [x] 6.6 Standalone unit test suite (14 new tests in `starship-geo-sat/tests`, 69 tests passing total).
- [x] 6.7 Pipeline orchestration integration as Step 7 emitting `pipeline_artifacts/geo_satellite_validation.json`.
- [x] 6.8 Open and resolve dedicated GitHub issues (#17, #18, #19, #20, #21).

---

## Phase 7: Mission Control Visualizer (Full Overhaul)
- [x] 7.1 Rebuild `visualizer/index.html` as a 5-tab mission control dashboard (1575 lines, zero external build dependencies).
- [x] 7.2 Implement JS physics simulation mirroring `trajectory.py` exactly: 3-DoF RK4, TVC gimbal PD controller, propellant burn, barometric atmosphere, Sutton-Graves heat flux.
- [x] 7.3 Implement LOX and CH4 slosh pendulum simulation in JS (natural frequency, damping, free-surface displacement, suction inlet submergence, gas ingestion threshold).
- [x] 7.4 Add live mini line charts: altitude, vertical speed, LOX slosh angle, heat flux — rolling 150-sample window, 30 Hz update.
- [x] 7.5 Add Safety Interlocks panel: live status grid (6 interlocks), incident reference library (all 5 CNSA/NewSpace incidents), multi-sensor altitude readouts.
- [x] 7.6 Add GEO-SAT panel: all 5 Türksat subsystems — abort detector, inclined orbit, EOR spiral day counter, reaction wheel desat bars, transponder XPI/AUPC.
- [x] 7.7 Add TPS panel: 6-zone hull thermal risk map (canvas), tile count summary by zone, live heat flux gauge.
- [x] 7.8 Support JSON file loading from `run_pipeline.py` output (`pipeline_artifacts/flight_telemetry.json`) via drag-drop / file input.
- [x] 7.9 Upgrade 3D scene: TPS tile detail on hull, 3 individual Raptor nozzle plumes, Mechazilla chopstick arm with catch pins, orbit camera toggle.
- [x] 7.10 Add topbar status chips: mission clock, phase badge, slosh risk level, CI test count.

---

## Phase 8: Core Engineering Expansion, Bug Remediation & Technical Audit
- [x] 8.1 Identify and patch 5 physical and numerical failure modes across flight and orbital mechanics modules.
  - [x] 8.1.1 Patch signed lateral aerodynamic lift vector direction with body-relative pitch in `aerodynamics.py`.
  - [x] 8.1.2 Include static gravitational weight support in Mechazilla pin contact load solver in `catch_dynamics.py`.
  - [x] 8.1.3 Integrate radiation exposure over full elapsed step time (24h/day) in `electric_orbit_raising.py`.
  - [x] 8.1.4 Include aerodynamic drag damping in instantaneous impact point divert $\Delta \mathbf{v}$ solver in `debris_hazard_predictor.py`.
  - [x] 8.1.5 Evaluate multi-sensor altitude dispersion across all active channels in `touchdown_gate.py`.
- [x] 8.2 Deliver 25 distinct technical contributions and modular enhancements across the suite:
  - [x] 8.2.1 US Standard Atmosphere 1976 (USSA76) piecewise temperature gradient model.
  - [x] 8.2.2 Stefan-Boltzmann radiative equilibrium surface temperature solver.
  - [x] 8.2.3 Dryden continuous atmospheric turbulence spectrum generator.
  - [x] 8.2.4 Center of mass shift and 3D principal moment of inertia tensor tracking.
  - [x] 8.2.5 Quaternion attitude representation and exact Lie algebra logarithm error kinematics (`quaternion_attitude.py`).
  - [x] 8.2.6 Gain-scheduled altitude-dependent bandwidth controller in `trajectory.py`.
  - [x] 8.2.7 Dynamic tip-over stability and tilt angle validator in `touchdown_gate.py`.
  - [x] 8.2.8 3D spherical cone TVC gimbal limiting and vector cosine loss in `engine_out_recovery.py`.
  - [x] 8.2.9 Minimum-norm control allocator via Moore-Penrose right pseudo-inverse ($B B^T$ formulation).
  - [x] 8.2.10 Hydro-pneumatic spring-damper chopstick pin impact dynamics model.
  - [x] 8.2.11 Second-harmonic ($m=2$) slosh pendulum mode with non-linear fundamental mode coupling.
  - [x] 8.2.12 Miles & Abramson annular ring baffle hydrodynamic damping ratio function in `tank.py`.
  - [x] 8.2.13 Unvented cryogenic tank ullage thermodynamic self-pressurization model.
  - [x] 8.2.14 Transfer line pre-cooling chill-down transient and vapor-lock prevention evaluator.
  - [x] 8.2.15 Multi-modal propellant mass gauging sensor fusion (PVT + capacitive level probes).
  - [x] 8.2.16 Hexagonal axial coordinate system $(q, r)$ and BFS spatial defect clustering.
  - [x] 8.2.17 Multi-spectral optical and thermal infrared inspection fusion for subsurface voids.
  - [x] 8.2.18 Inspection metrics engine (Confusion matrix, Precision, Recall, F1 score).
  - [x] 8.2.19 Lunisolar third-body gravitational tidal drift equations in `inclined_orbit_dynamics.py`.
  - [x] 8.2.20 Ground station Doppler frequency shift and antenna tracking slew rate solver.
  - [x] 8.2.21 Equinox eclipse radiative cooldown and battery Depth-of-Discharge simulator (`eclipse_thermal_model.py`).
  - [x] 8.2.22 Hall-effect thruster hollow cathode erosion and mass utilization efficiency model.
  - [x] 8.2.23 Solar Array Drive Mechanism (SADM) stepper disturbance torque model.
  - [x] 8.2.24 Cryptographic HMAC-SHA256 telemetry frame integrity signer and validator.
  - [x] 8.2.25 Automated pipeline artifact integrity verifier and cross-schema gate in `run_pipeline.py`.
- [x] 8.3 Author comprehensive 25-module technical code review document (`docs/CODE_REVIEWS_25.md`).
- [x] 8.4 Author comprehensive unit test suites expanding verification coverage to 99 passing tests.
