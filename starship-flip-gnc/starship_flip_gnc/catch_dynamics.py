"""
Mechazilla tower chopstick catch dynamics and pin capture envelope.

Models Flight 5/6 precision hover-and-catch guidance targeting the launch tower arms,
evaluating kinematic capture tolerances, pin contact impulse, and engine shutdown sequencing.
"""

from dataclasses import dataclass
import math
from typing import Optional, Tuple


@dataclass
class CatchEnvelope:
    """
    Physical kinematic tolerance window for Mechazilla chopstick capture pins.
    """
    target_x_m: float = 0.0                  # Launch mount target downrange position [m]
    target_z_m: float = 45.0                 # Chopstick arm catch elevation above pad [m]
    max_lateral_offset_m: float = 0.50       # Lateral pin alignment limit [m] (+/- 50 cm)
    max_vertical_offset_m: float = 0.35      # Vertical arm clearance limit [m]
    max_catch_descent_rate_mps: float = 0.40 # Maximum permissible downward velocity at pin contact [m/s]
    max_lateral_velocity_mps: float = 0.20   # Maximum drift rate at pin contact [m/s]
    max_pitch_deg: float = 1.0               # Maximum body tilt angle [degrees]
    pin_shear_load_limit_n: float = 4.5e6    # Maximum allowable dynamic pin impulse [N]


@dataclass
class CatchResult:
    """
    Chopstick arm capture outcome.
    """
    caught: bool
    lateral_error_m: float
    vertical_error_m: float
    impact_velocity_mps: float
    pitch_error_deg: float
    contact_impulse_n: float
    message: str


class MechazillaCatchSolver:
    """
    Evaluates terminal hover kinematics and executes chopstick pin capture logic.
    """

    def __init__(self, envelope: Optional[CatchEnvelope] = None):
        self.envelope = envelope or CatchEnvelope()

    def evaluate_capture(
        self,
        x_m: float,
        z_m: float,
        vx_mps: float,
        vz_mps: float,
        pitch_deg: float,
        vehicle_mass_kg: float,
    ) -> CatchResult:
        """
        Evaluates whether vehicle state falls inside the Mechazilla chopstick capture envelope.
        """
        lat_err = abs(x_m - self.envelope.target_x_m)
        vert_err = abs(z_m - self.envelope.target_z_m)
        vel_mag = math.hypot(vx_mps, vz_mps)
        pitch_err = abs(pitch_deg)

        # Contact impulse approximation (damped pin deceleration over dt ~ 0.15s):
        dt_capture = 0.15
        contact_force = vehicle_mass_kg * (vel_mag / dt_capture)

        # Tolerance checks:
        lat_ok = lat_err <= self.envelope.max_lateral_offset_m
        vert_ok = vert_err <= self.envelope.max_vertical_offset_m
        vz_ok = abs(vz_mps) <= self.envelope.max_catch_descent_rate_mps
        vx_ok = abs(vx_mps) <= self.envelope.max_lateral_velocity_mps
        pitch_ok = pitch_err <= self.envelope.max_pitch_deg
        load_ok = contact_force <= self.envelope.pin_shear_load_limit_n

        success = lat_ok and vert_ok and vz_ok and vx_ok and pitch_ok and load_ok

        if success:
            msg = (
                f"Chopstick pin capture successful: lat_err={lat_err:.2f}m, "
                f"vz={vz_mps:.2f}m/s, contact_load={contact_force / 1e3:.1f}kN."
            )
        else:
            failures = []
            if not lat_ok:
                failures.append(f"lateral offset {lat_err:.2f}m > {self.envelope.max_lateral_offset_m}m")
            if not vert_ok:
                failures.append(f"vertical offset {vert_err:.2f}m > {self.envelope.max_vertical_offset_m}m")
            if not vz_ok:
                failures.append(f"descent rate {abs(vz_mps):.2f}m/s > {self.envelope.max_catch_descent_rate_mps}m/s")
            if not vx_ok:
                failures.append(f"drift rate {abs(vx_mps):.2f}m/s > {self.envelope.max_lateral_velocity_mps}m/s")
            if not pitch_ok:
                failures.append(f"pitch {pitch_err:.1f}deg > {self.envelope.max_pitch_deg}deg")
            if not load_ok:
                failures.append(f"pin overload {contact_force / 1e6:.2f}MN > {self.envelope.pin_shear_load_limit_n / 1e6:.2f}MN")
            msg = "Capture aborted: " + ", ".join(failures)

        return CatchResult(
            caught=success,
            lateral_error_m=round(lat_err, 3),
            vertical_error_m=round(vert_err, 3),
            impact_velocity_mps=round(vel_mag, 3),
            pitch_error_deg=round(pitch_err, 2),
            contact_impulse_n=round(contact_force, 1),
            message=msg,
        )
