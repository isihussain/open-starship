# Handover & Architecture Notes (Open-Starship Suite)

This document provides developer guidelines, architectural decisions, and operational instructions for contributors and future maintainers.

---

## 1. Project Purpose & Scope
The suite models the primary physical, operational, and safety bottlenecks across next-generation reusable launch vehicles, orbital transfer stages, and geostationary telecommunications platforms:
1. **starship-flip-gnc:** 3-DoF trajectory optimization, thrust-vector control (TVC), Mechazilla chopstick tower catch kinematics, and aerospace incident safety interlocks.
2. **starship-cryo-slosh:** Fluid free-surface sloshing, suction inlet gas ingestion in cryogenic header tanks, and orbital ship-to-ship propellant transfers.
3. **starship-tps-vision:** Optical defect detection and aerothermal load prioritization for 18,000+ hexagonal ceramic heat shield tiles.
4. **starship-geo-sat:** Geostationary satellite operations, electric orbit raising (EOR), zero-magnetic-field reaction wheel desaturation, and transponder payload protection derived from the Türksat satellite program (Türksat 1A through 6A).
5. **visualizer:** Interactive 3D WebGL flight replay and real-time slosh cutaway app.

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
[ starship-geo-sat: Geostationary Satellite Operations & Türksat Mitigations ]
  - Upper-stage cryogenic abort detector (Türksat 1A)
  - Inclined orbit drift & ground tracking (Türksat 1B/1C)
  - Electric orbit raising & radiation degradation (Türksat 5A/5B)
  - GEO reaction wheel momentum desaturation (Türksat 6A)
  - Transponder interference & rain fade AUPC (Türksat 3A/4A/4B)
       │
       ▼
 [ 3D WebGL Flight Visualizer ]
```

---

## 3. Test & Verification Commands
```bash
cd /Users/johndoe/.gemini/antigravity/scratch/open-starship

# Run all 69 unit tests across the 4 packages:
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision:starship-geo-sat" python3 -m unittest discover -s starship-flip-gnc/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision:starship-geo-sat" python3 -m unittest discover -s starship-cryo-slosh/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision:starship-geo-sat" python3 -m unittest discover -s starship-tps-vision/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision:starship-geo-sat" python3 -m unittest discover -s starship-geo-sat/tests

# Run the 7-phase end-to-end pipeline:
python3 run_pipeline.py pipeline_artifacts

# Open the 3D browser visualizer:
open visualizer/index.html
```

---

## 4. Geostationary Satellite Architecture (`starship-geo-sat`)

1. **`launch_abort_detector.py` (Türksat 1A):**
   - *Failure Mode:* Cryogenic third-stage LOX turbopump valve failed on Ariane 44LP V63, leaving the spacecraft on a suborbital arc terminating in the Atlantic Ocean.
   - *Architecture:* Detects chamber pressure collapse ($P_c < 0.8 P_{c,\text{nominal}}$) and velocity shortfall ($v < 10,200\text{ m/s}$), solves ballistic freefall equations to project ground impact coordinates, and commands spacecraft contingency battery preservation.

2. **`inclined_orbit_dynamics.py` (Türksat 1B & 1C):**
   - *Failure Mode:* Propellant depletion forced suspension of North-South station-keeping burns ($~45\text{ m/s per year}$). Lunisolar third-body perturbations induced natural inclination drift at ~0.86 deg/year, creating daily figure-eight ground track excursions.
   - *Architecture:* Evaluates secular inclination drift, calculates diurnal Azimuth/Elevation pointing corrections for tracking antennas, computes off-axis parabolic dish gain loss, and reserves delta-v fuel for IADC super-GEO graveyard disposal ($+235\text{ km} + 1000 C_R \frac{A}{m}$).

3. **`electric_orbit_raising.py` (Türksat 5A & 5B):**
   - *Failure Mode:* Hall-effect low-thrust spiral transfer took 140 to 160 days from GTO to GEO, trapping the spacecraft in the Van Allen proton and electron radiation belts.
   - *Architecture:* Propagates low-thrust orbital energy addition, integrates 1-MeV equivalent electron fluence, and models solar cell non-ionizing energy loss (NIEL) power degradation.

4. **`reaction_wheel_desat.py` (Türksat 6A):**
   - *Failure Mode:* At 35,786 km, Earth's geomagnetic field is negligible (~100 nT), rendering magnetic torquers inoperable. Solar radiation pressure (SRP) builds up angular momentum in reaction wheels.
   - *Architecture:* Tracks solar radiation pressure torque accumulation on asymmetric arrays, schedules pure-torque thruster couples (zero net translation force), and ensures orbital slot deadbands ($\pm 0.05^\circ$) are never violated.

5. **`rfi_transponder_guard.py` (Türksat 3A, 4A, 4B):**
   - *Failure Mode:* Terrestrial uplink cross-polarization leakage (XPI < 25 dB), TWTA amplifier saturation from rogue high-power carriers, and severe Ka-band attenuation (15 to 20 dB) during heavy rainstorms.
   - *Architecture:* Models Saleh non-linear TWTA gain compression and IMD3 intermodulation distortion, flags cross-polarization violations, and calculates Automated Uplink Power Control (AUPC) feedback boosts.

---

## 5. Systems Compiler & Avionics Integration (Oxide)
- The numerical equations in `starship-flip-gnc`, `starship-cryo-slosh`, and `starship-geo-sat` compile directly into freestanding C99 using **[Oxide](https://github.com/isihussain/oxide-compiler)**.
- Oxide's `StageMass` verification invariant enforces that total vehicle mass never breaches physical dry mass ($m_{\text{total}} \ge m_{\text{dry}}$), eliminating negative mass singularities during flight burns.
- `native_bridge.py` dynamically compiles `starship_core.c` via standard `cc -O3 -shared -fPIC` and executes RK4 steps at native C execution speed via `ctypes`.

---

## 6. Future Development Roadmap
- **starship-flip-gnc:** Extend 3-DoF equations into a full 6-DoF rigid-body dynamic model with flap aero-moment tables.
- **starship-cryo-slosh:** Couple with 3D Smoothed Particle Hydrodynamics (SPH) solver for chaotic violent slosh regimes.
- **starship-tps-vision:** Connect PyTorch YOLOv8 / Segment Anything (SAM) weights trained on drone inspection footage from the Starbase launch tower.
- **starship-geo-sat:** Expand to include high-altitude lunar relay constellation cross-links and laser inter-satellite links (ISL).
