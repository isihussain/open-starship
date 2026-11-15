"""
Aerodynamic force and aerothermal heating models for Starship landing regimes.

Includes cross-sectional drag variation across angle-of-attack, stagnation heat flux,
and atmospheric boundary layer wind shear and discrete gust dynamics.
"""

from dataclasses import dataclass
from typing import Tuple
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


@dataclass
class WindModel:
    """
    Atmospheric boundary layer wind shear and discrete gust model.

    Power-law boundary layer shear:
      v_mean(z) = v_ref * (z / z_ref) ^ alpha_shear

    Discrete '1 - cosine' gust profile (FAA/MIL-F-8785C compliant):
      v_gust(t) = (A_gust / 2) * (1 - cos(2*pi * (t - t_start) / T_gust))
    """
    ref_wind_speed: float = 0.0      # m/s at reference altitude
    ref_altitude: float = 10.0       # Reference altitude (standard 10m meteorological height)
    shear_exponent: float = 0.14     # Terrain roughness exponent (0.14 for coastal Starbase terrain)
    gust_amplitude: float = 0.0      # Gust peak velocity [m/s]
    gust_start_time: float = 0.0     # Time when gust initiates [s]
    gust_duration: float = 5.0       # Total duration of discrete gust [s]
    gust_direction_deg: float = 0.0  # Angle in horizontal plane (0 deg = pure +X crosswind)

    def compute_wind(self, altitude_m: float, time_s: float = 0.0) -> tuple[float, float]:
        """
        Calculates horizontal (vx) and vertical (vz) wind velocity components at (altitude, time).

        Returns:
            tuple[float, float]: (wind_vx, wind_vz) in inertial frame [m/s].
        """
        alt = max(0.1, altitude_m)
        mean_speed = self.ref_wind_speed * ((alt / self.ref_altitude) ** self.shear_exponent)

        # Evaluate discrete gust:
        gust_speed = 0.0
        if self.gust_amplitude > 0.0 and self.gust_duration > 0.0:
            if self.gust_start_time <= time_s <= (self.gust_start_time + self.gust_duration):
                phase = 2.0 * math.pi * (time_s - self.gust_start_time) / self.gust_duration
                gust_speed = (self.gust_amplitude / 2.0) * (1.0 - math.cos(phase))

        total_horizontal_speed = mean_speed + gust_speed
        rad = math.radians(self.gust_direction_deg)
        wind_vx = total_horizontal_speed * math.cos(rad)
        wind_vz = 0.0  # In boundary layer, vertical wind is typically zero or negligible

        return (wind_vx, wind_vz)


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
        atmosphere: Atmosphere,
        wind_vx: float = 0.0,
        wind_vz: float = 0.0
    ) -> dict:
        """
        Calculates drag, lift, dynamic pressure, and aerothermal heat flux.

        Args:
            vx: Horizontal inertial velocity [m/s].
            vz: Vertical inertial velocity [m/s].
            theta: Pitch angle [rad] (0 = vertical nose-up, pi/2 = horizontal).
            altitude: Current altitude above surface [m].
            atmosphere: Atmospheric density provider.
            wind_vx: Ambient horizontal wind velocity [m/s] (positive = in +X direction).
            wind_vz: Ambient vertical wind velocity [m/s].

        Returns:
            Dictionary containing fx_aero, fz_aero, dynamic_pressure, heat_flux_w_m2.
        """
        # Relative airspeed vector:
        u_rel_x = vx - wind_vx
        u_rel_z = vz - wind_vz
        speed = math.hypot(u_rel_x, u_rel_z)

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

        # Body orientation vector pointing from tail to nose:
        body_x = math.sin(theta)
        body_z = math.cos(theta)

        # Relative velocity unit vector:
        uv_x = u_rel_x / speed
        uv_z = u_rel_z / speed

        # Cosine of angle between body axis and relative velocity vector:
        cos_beta = max(-1.0, min(1.0, body_x * uv_x + body_z * uv_z))
        beta = math.acos(cos_beta)

        # Angle of attack alpha: deviation from axial flow (0 to pi/2)
        alpha = beta if beta <= (math.pi / 2.0) else (math.pi - beta)

        # Effective projected area and drag coefficient interpolation:
        sin_a = math.sin(alpha)
        cos_a = math.cos(alpha)

        cd = self.cd_axial * (cos_a ** 2) + self.cd_broadside * (sin_a ** 2)
        ref_area = self.area_axial * (cos_a ** 2) + self.area_broadside * (sin_a ** 2)

        # Total drag opposes the relative velocity vector:
        drag_force = q_dyn * cd * ref_area

        # Flap-modulated lift acts perpendicular to relative velocity:
        cl = self.cl_max * math.sin(2.0 * alpha)
        lift_force = q_dyn * cl * ref_area

        # Drag components (strictly opposing relative velocity):
        f_drag_x = -drag_force * uv_x
        f_drag_z = -drag_force * uv_z

        # Lift direction: perpendicular to relative velocity, oriented towards suction side.
        # 2D cross product of relative airspeed and body vector determines signed lateral pitch:
        cross_rel_body = uv_x * body_z - uv_z * body_x
        side = 1.0 if cross_rel_body >= 0.0 else -1.0

        f_lift_x = side * (-lift_force * uv_z)
        f_lift_z = side * (lift_force * uv_x)

        # Stagnation point aerothermal heat flux (Sutton-Graves relation):
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


@dataclass
class AtmosphericState:
    """
    Thermodynamic state vector for atmospheric point.
    """
    altitude_m: float
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    speed_of_sound_mps: float


class StandardAtmosphere1976:
    """
    US Standard Atmosphere 1976 (USSA76) multi-layer barometric model.
    Piecewise linear temperature gradient up to 51,000 meters altitude.
    """

    R_AIR = 287.05287            # Specific gas constant for air [J / (kg * K)]
    GAMMA = 1.40                 # Adiabatic index for air
    G0 = 9.80665                 # Gravitational acceleration [m/s^2]

    # Layer base boundaries: (z_base_m, T_base_K, lapse_rate_K_per_m, P_base_Pa)
    LAYERS = [
        (0.0, 288.15, -0.0065, 101325.0),        # Troposphere
        (11000.0, 216.65, 0.0, 22632.1),         # Tropopause (isothermal)
        (20000.0, 216.65, 0.0010, 5474.89),      # Stratosphere 1
        (32000.0, 228.65, 0.0028, 868.019),      # Stratosphere 2
        (47000.0, 270.65, 0.0, 110.906),         # Stratopause
    ]

    def evaluate(self, altitude_m: float) -> AtmosphericState:
        """
        Calculates temperature, pressure, density, and sound velocity at geometric altitude.
        """
        z = max(0.0, min(51000.0, altitude_m))

        # Identify layer:
        z_base, t_base, lapse, p_base = self.LAYERS[0]
        for layer in self.LAYERS:
            if z >= layer[0]:
                z_base, t_base, lapse, p_base = layer
            else:
                break

        dz = z - z_base
        if abs(lapse) < 1e-9:
            # Isothermal layer:
            temp = t_base
            pressure = p_base * math.exp(-self.G0 * dz / (self.R_AIR * t_base))
        else:
            # Constant lapse rate layer:
            temp = t_base + lapse * dz
            exponent = -self.G0 / (lapse * self.R_AIR)
            pressure = p_base * ((temp / t_base) ** exponent)

        density = pressure / (self.R_AIR * temp)
        sound_speed = math.sqrt(self.GAMMA * self.R_AIR * temp)

        return AtmosphericState(
            altitude_m=round(z, 2),
            temperature_k=round(temp, 2),
            pressure_pa=round(pressure, 2),
            density_kg_m3=round(density, 5),
            speed_of_sound_mps=round(sound_speed, 2),
        )

    def density(self, altitude_m: float) -> float:
        """
        Convenience density lookup compatible with standard Atmosphere interface.
        """
        return self.evaluate(altitude_m).density_kg_m3


class RadiativeEquilibriumThermalModel:
    """
    Computes steady-state surface radiation equilibrium temperature for TPS tiles.
    Stefan-Boltzmann radiation cooling balance: q_conv = epsilon * sigma * T_wall^4.
    """

    STEFAN_BOLTZMANN = 5.670374e-8  # W / (m^2 * K^4)

    def __init__(self, surface_emissivity: float = 0.88):
        self.emissivity = surface_emissivity

    def compute_surface_temperature_k(self, convective_heat_flux_w_m2: float) -> float:
        """
        Solves for radiative equilibrium wall temperature in Kelvin.
        """
        q = max(0.0, convective_heat_flux_w_m2)
        if q <= 0.0:
            return 288.15  # Ambient baseline
        t_wall = (q / (self.emissivity * self.STEFAN_BOLTZMANN)) ** 0.25
        return round(t_wall, 2)


@dataclass
class DrydenTurbulenceModel:
    """
    Low-altitude continuous atmospheric turbulence generator based on Dryden spectra (MIL-HDBK-1797).
    """
    severity_intensity: str = "MODERATE"   # "LIGHT", "MODERATE", "SEVERE"
    wind_speed_at_20ft_mps: float = 12.0

    def compute_turbulence_intensity(self, altitude_m: float) -> Tuple[float, float, float]:
        """
        Computes Dryden scale lengths (Lu, Lw) and vertical/horizontal RMS intensities (sigma_u, sigma_w).
        """
        z = max(3.0, min(600.0, altitude_m))
        # Low altitude MIL-F-8785C relations:
        l_w = z
        l_u = z / ((0.177 + 0.000823 * z) ** 1.2)

        # Scale intensity with reference wind:
        sigma_w = 0.1 * self.wind_speed_at_20ft_mps
        if self.severity_intensity == "SEVERE":
            sigma_w *= 2.0
        elif self.severity_intensity == "LIGHT":
            sigma_w *= 0.5

        sigma_u = sigma_w / ((0.177 + 0.000823 * z) ** 0.4)
        return l_u, l_w, round(sigma_u, 3)
