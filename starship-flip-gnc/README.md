# starship-flip-gnc

A 3-DoF trajectory optimization and thrust-vector control (TVC) library that models the SpaceX Starship landing flip maneuver from broadside belly-flop to vertical touchdown.

The numerical solver models three active flight regimes under physical actuator and throttle constraints: 3-engine flip rotation, 2-engine high-g deceleration, and single-engine terminal touchdown.

---

## Flight Dynamic Equations

### 1. Translational Dynamics
The engine thrust vector direction is governed by vehicle pitch angle $\theta$ and engine nozzle gimbal deflection $\delta$:

$$F_{T,x} = F_T \sin(\theta - \delta)$$

$$F_{T,z} = F_T \cos(\theta - \delta)$$

Net accelerations incorporate gravity ($g = 9.80665 \text{ m/s}^2$) and aerodynamic drag/lift forces:

$$a_x = \frac{F_{T,x} + F_{aero,x}}{m(t)}, \quad a_z = \frac{F_{T,z} + F_{aero,z} - m(t)g}{m(t)}$$

### 2. Rotational Dynamics
The engine gimbal pivot is located $19.0\text{ m}$ aft of the vehicle center of mass. The resulting pitching torque is:

$$M_{net} = -F_T \sin(\delta) \cdot r_{gimbal} - c_{rot} q_{dyn} A_{broad} L \omega$$

Angular acceleration $\alpha_{ang} = M_{net} / I_{yy}$ is integrated using a 4th-order Runge-Kutta (RK4) numerical scheme.

---

## Installation

Zero external C-compiler dependencies. Requires standard Python 3.9+:

```bash
cd starship-flip-gnc
pip install -e .
```

---

## Quickstart

### CLI Simulation

```bash
python3 -m starship_flip_gnc.cli --altitude 500.0 --vz -70.0 --export-json telemetry.json --export-csv telemetry.csv
```

### Python API

```python
from starship_flip_gnc.models import StarshipVehicle, FlightState
from starship_flip_gnc.trajectory import TrajectoryOptimizer
from starship_flip_gnc.telemetry import TelemetryLogger

vehicle = StarshipVehicle(dry_mass=100000.0, landing_propellant_mass=25000.0)
optimizer = TrajectoryOptimizer(vehicle=vehicle)
logger = TelemetryLogger()

initial_state = FlightState(z=500.0, vz=-70.0)
result = optimizer.simulate(initial_state=initial_state, dt=0.02, logger=logger)

print(f"Outcome: {'SUCCESS' if result.success else 'FAILED'}")
print(f"Touchdown Time: {result.touchdown_time_s} s | Remaining Fuel: {result.propellant_remaining_kg} kg")

# Export flight telemetry for downstream slosh and TPS analysis
logger.export_json("flight_telemetry.json")
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
