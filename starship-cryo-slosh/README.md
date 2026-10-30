# starship-cryo-slosh

A reduced-order mechanical pendulum simulator for cryogenic propellant sloshing and ullage gas ingestion in Starship nose (LOX) and common-dome (CH4) header tanks during high-g landing flip maneuvers.

Built on the NASA SP-106 hydrodynamic pendulum formulation to evaluate fluid free-surface displacement and turbopump cavitation risks in real-time flight control loops.

---

## Mathematical Formulation

### 1. Equivalent Pendulum Slosh Dynamics (Abramson / Dodge Model)
Free-surface liquid oscillation inside a spherical tank is modeled as a damped mechanical pendulum:

$$\ddot{\phi} + 2 \zeta \omega_n \dot{\phi} + \frac{g_{eff}}{L_p} \sin(\phi - \phi_{eq}) = -\dot{\omega}_{vehicle}$$

Where:
* $g_{eff} = \sqrt{a_{lateral}^2 + a_{axial}^2}$: Net apparent acceleration in vehicle coordinates.
* $\phi_{eq} = \text{atan2}(a_{lateral}, a_{axial})$: Equilibrium free-surface tilt angle.
* $\omega_n = \sqrt{g_{eff} / L_p}$: Slosh natural frequency.
* $\zeta$: Hydrodynamic damping ratio ($0.018$ for clean walls; $0.085$ with annular ring baffles).

### 2. Ullage Gas Ingestion Criterion
The instantaneous liquid submergence depth above the bottom suction inlet is:

$$h_{submergence} = h_{nominal} - (R + z_{inlet}) - R |\sin(\phi)|$$

When $h_{submergence} < h_{threshold}$ ($0.15\text{ m}$), the simulator flags an active turbopump cavitation and flameout risk warning.

---

## Installation

```bash
cd starship-cryo-slosh
pip install -e .
```

---

## Quickstart

### CLI Usage (with starship-flip-gnc Telemetry)

```bash
python3 -m starship_cryo_slosh.cli --telemetry /path/to/telemetry.json --with-baffles --export-json slosh_output.json
```

### Python API

```python
import json
from starship_cryo_slosh.tank import HeaderTankAssembly
from starship_cryo_slosh.simulator import SloshSimulator

# 1. Initialize tank geometry with optional anti-slosh ring baffles
assembly = HeaderTankAssembly.default_starship(with_baffles=True)
sim = SloshSimulator(assembly=assembly, lox_mass_kg=17500.0, ch4_mass_kg=7500.0)

# 2. Ingest flight telemetry from GNC module
with open("flight_telemetry.json", "r") as f:
    telemetry_records = json.load(f)

# 3. Simulate coupled fluid slosh
result, history = sim.simulate_telemetry(telemetry_records)

print(f"Risk Level: {result.risk_level}")
print(f"LOX Gas Ingestion Time: {result.lox_total_gas_exposure_time_s} s")
print(f"Peak Disturbance Torque: {result.max_slosh_torque_nm} N*m")
print(f"Peak Center-of-Mass Shift: {result.max_com_shift_x_mm} mm")
```

---

## Running Tests

```bash
python3 -m unittest discover -s tests
```

---

## Contributing & Support

* **GitHub Sponsors:** [github.com/sponsors/isihussain](https://github.com/sponsors/isihussain)

> **Developer Note:** I have developed this project over the past 3 years in my local Git environment. My decision to publish it as open source is driven by my commitment to supporting the establishment of permanent human colonies and settlements on other worlds.
