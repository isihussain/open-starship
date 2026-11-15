# Handover & Architecture Notes (Open-Starship Suite)

This document provides developer guidelines, architectural decisions, and operational instructions for contributors and future maintainers.

---

## 1. Project Purpose & Scope
The suite models the primary physical, operational, and safety bottlenecks across next-generation reusable launch vehicles, orbital transfer stages, and geostationary telecommunications platforms:
1. **starship-flip-gnc:** 3-DoF trajectory optimization, thrust-vector control (TVC), Mechazilla chopstick tower catch kinematics, and aerospace incident safety interlocks.
2. **starship-cryo-slosh:** Fluid free-surface sloshing, suction inlet gas ingestion in cryogenic header tanks, and orbital ship-to-ship propellant transfers.
3. **starship-tps-vision:** Optical defect detection and aerothermal load prioritization for 18,000+ hexagonal ceramic heat shield tiles.
4. **starship-geo-sat:** Geostationary satellite operations, electric orbit raising (EOR), zero-magnetic-field reaction wheel desaturation, and transponder payload protection derived from the Türksat satellite program (Türksat 1A through 6A).
5. **visualizer:** 5-tab mission control dashboard (Three.js 3D scene, live JS physics simulation, slosh pendulum, safety interlocks, GEO-SAT subsystems, TPS thermal map).
   Open with `open visualizer/index.html` — or load `pipeline_artifacts/flight_telemetry.json` directly in the browser.

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

# Run all 99 unit tests across the 4 packages:
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision:starship-geo-sat" python3 -m unittest discover -s starship-flip-gnc/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision:starship-geo-sat" python3 -m unittest discover -s starship-cryo-slosh/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision:starship-geo-sat" python3 -m unittest discover -s starship-tps-vision/tests
PYTHONPATH="starship-flip-gnc:starship-cryo-slosh:starship-tps-vision:starship-geo-sat" python3 -m unittest discover -s starship-geo-sat/tests

# Run the 8-phase end-to-end pipeline with artifact validation:
python3 run_pipeline.py pipeline_artifacts

# Open the 5-tab mission control visualizer:
open visualizer/index.html
# In the browser, use the tab bar to switch between:
#   Flight & GNC | Cryo Slosh | Safety Interlocks | GEO-SAT | TPS Tiles
# To load recorded pipeline data, click "Load JSON" in any tab and select:
#   pipeline_artifacts/flight_telemetry.json
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

6. **`azercosmos_orbital_coordination.py` (Azerspace-1 & Azerspace-2):**
   - *Operational Bottleneck:* 0.9° angular separation between Azerspace-1 (46.0°E) and Azerspace-2 (45.1°E) exceeds the 3 dB beamwidth of standard user earth stations (1.2m to 2.4m dishes), creating Adjacent Satellite Interference (ASI) and self-jamming risk on overlapping Ku-band channels.
   - *Architecture:* Evaluates ITU-R S.580/S.465 off-axis sidelobe discrimination, computes $(C/I)_{\text{ASI}}$, selects DVB-S2X adaptive coding and modulation (ACM: 32APSK, 16APSK, 8PSK, QPSK), and coordinates automated failover between Absheron Main Teleport and Nakhchivan Reserve Teleport.

7. **`azersky_debris_conjunction.py` (AzerSky / SPOT 7):**
   - *Failure Mode:* Sudden communication loss on March 17, 2023 at 19:34–20:48 UTC while the satellite remained on its nominal 694.9 km Sun-Synchronous Orbit (confirmed by US Space Surveillance Network), indicating an untracked hypervelocity micro-debris strike severing the main power harness without catastrophic hull disintegration.
   - *Architecture:* Calculates hypervelocity impact kinetic energy ($E_k = \frac{1}{2} m v^2$) and Cour-Palais penetration depth in aluminum bus skin, estimates post-impact tumbling rate ($\boldsymbol{\omega}_{\text{tumble}}$), and commands Earth observation continuity fallback to twin SPOT-6 imagery and Azersky-2 constellation tasking.

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

---

## 7. Visual Documentation & Asset Maintenance
- Animated SVG hero banners and visualizer preview cards reside under `docs/assets/`.
- `hero_banner.svg` uses standard CSS keyframes for plume flicker, supersonic shock diamonds, and laser guides without JavaScript dependencies.
- `README.md` uses native GitHub Mermaid syntax (`flowchart TD` and `sequenceDiagram`) which automatically render on GitHub web and mobile. All new subsystem workflows should be mirrored in both Mermaid and the 3D visualizer.
