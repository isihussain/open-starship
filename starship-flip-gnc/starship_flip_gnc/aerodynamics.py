"""
Aerodynamic force and aerothermal heating models for Starship landing regimes.

Includes cross-sectional drag variation across angle-of-attack and stagnation heat flux.
"""

from dataclasses import dataclass
import math


@dataclass
class Atmosphere:
    """
    Standard barometric exponential atmosphere model for lower altitudes.
    """
    sea_level_density: float = 1.225  # kg/m^3
    scale_height: float = 8500.0      # meters
    gravitational_accel: float = 9.80665  # m/s^2

    def density(self, altitude_m: float) -> float:
        """
        Calculates ambient air density at given altitude [m].
        Clamped to sea-level density for non-positive altitudes.
        """
        alt = max(0.0, altitude_m)
        return self.sea_level_density * math.exp(-alt / self.scale_height)


class AerodynamicModel:
    """
    Computes aerodynamic drag, lift, and stagnation point heat flux.

    Angle of attack alpha is defined relative to the vehicle body axis:
      - alpha = 0: Nose into wind (axial flight).
      - alpha = pi/2 (90 deg): Cross-flow (belly-flop descent).
    """

    def __init__(self, vehicle_length: float = 50.0, vehicle_diameter: float = 9.0):
        self.length = vehicle_length
        self.diameter = vehicle_diameter
        # Cross-sectional areas:
        self.area_axial = math.pi * (vehicle_diameter / 2.0) ** 2  # ~63.6 m^2
        self.area_broadside = vehicle_length * vehicle_diameter     # 450 m^2

        # Aerodynamic coefficients:
        self.cd_axial = 0.30       # Streamlined nose-first descent
        self.cd_broadside = 1.35   # High-drag blunt cylinder cross-flow
        self.cl_max = 0.50         # Flap-controlled lift authority

        # Sutton-Graves stagnation constant for Earth atmosphere [kg^0.5 / m]:
        self.k_sutton_graves = 1.7415e-4

    def compute_forces(
        self,
        vx: float,
        vz: float,
        theta: float,
        altitude: float,
        atmosphere: Atmosphere
    ) -> dict:
        """
        Calculates drag, lift, dynamic pressure, and aerothermal heat flux.

        Args:
            vx: Horizontal velocity [m/s].
            vz: Vertical velocity [m/s].
            theta: Pitch angle [rad] (0 = vertical nose-up, pi/2 = horizontal).
            altitude: Current altitude above surface [m].
            atmosphere: Atmospheric density provider.

        Returns:
            Dictionary containing fx_aero, fz_aero, dynamic_pressure, heat_flux_w_m2.
        """
        speed = math.hypot(vx, vz)
        rho = atmosphere.density(altitude)
        q_dyn = 0.5 * rho * (speed ** 2)

        if speed < 1e-3:
            return {
                "drag": 0.0,
                "lift": 0.0,
                "fx_aero": 0.0,
                "fz_aero": 0.0,
                "dynamic_pressure": 0.0,
                "alpha_deg": 0.0,
                "heat_flux_w_m2": 0.0,
            }

        # Flight path angle (direction of velocity vector):
        gamma = math.atan2(vz, vx)

        # Body orientation vector pointing from tail to nose:
        # theta = 0 points +Z (vertical), theta = pi/2 points +X (horizontal)
        body_x = math.sin(theta)
        body_z = math.cos(theta)

        # Velocity unit vector:
        uv_x = vx / speed
        uv_z = vz / speed

        # Cosine of angle between body axis and velocity vector:
        cos_beta = max(-1.0, min(1.0, body_x * uv_x + body_z * uv_z))
        beta = math.acos(cos_beta)

        # Angle of attack alpha: deviation from axial flow (0 to pi/2)
        alpha = beta if beta <= (math.pi / 2.0) else (math.pi - beta)

        # Effective projected area and drag coefficient interpolation:
        sin_a = math.sin(alpha)
        cos_a = math.cos(alpha)

        cd = self.cd_axial * (cos_a ** 2) + self.cd_broadside * (sin_a ** 2)
        ref_area = self.area_axial * (cos_a ** 2) + self.area_broadside * (sin_a ** 2)

        # Total drag opposes the velocity vector:
        drag_force = q_dyn * cd * ref_area

        # Flap-modulated lift acts perpendicular to velocity:
        cl = self.cl_max * math.sin(2.0 * alpha)
        lift_force = q_dyn * cl * ref_area

        # Drag components (strictly opposing velocity):
        f_drag_x = -drag_force * uv_x
        f_drag_z = -drag_force * uv_z

        # Lift components (perpendicular to velocity, rotated +90 deg in vertical plane):
        # Normal vector to (uv_x, uv_z) is (-uv_z, uv_x)
        f_lift_x = -lift_force * uv_z
        f_lift_z = lift_force * uv_x

        # Stagnation point aerothermal heat flux (Sutton-Graves relation):
        # q_dot = k * sqrt(rho / R_nose) * v^3 [W/m^2]
        r_nose = self.diameter / 2.0
        heat_flux = self.k_sutton_graves * math.sqrt(rho / r_nose) * (speed ** 3)

        return {
            "drag": drag_force,
            "lift": lift_force,
            "fx_aero": f_drag_x + f_lift_x,
            "fz_aero": f_drag_z + f_lift_z,
            "dynamic_pressure": q_dyn,
            "alpha_deg": math.degrees(alpha),
            "heat_flux_w_m2": heat_flux,
        }
