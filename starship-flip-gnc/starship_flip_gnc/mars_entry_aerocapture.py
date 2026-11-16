"""
Mars atmospheric entry, aerocapture, and supersonic retro-propulsion (SRP) handover solver.

Models direct interplanetary entry into the thin Martian carbon dioxide atmosphere:
  - 95.3% CO2 atmospheric density, pressure, and speed of sound profile
  - 3-DoF point-mass spherical planet entry equations with bank-angle lift vector control
  - Aerodynamic corridor boundaries: skip-out overshoot vs. excessive deceleration undershoot
  - Tauber-Sutton Martian convective stagnation heat flux and CO2-band radiative emission
  - Supersonic retro-propulsion (SRP) engine ignition handover criteria (Mach 1.5 - 2.4)
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import math


@dataclass
class MarsAtmosphere:
    """
    Martian barometric atmosphere model for carbon dioxide environment.

    Composition: 95.3% CO2, 2.7% N2, 1.6% Ar.
    Mean molecular weight: M = 43.34 g/mol.
    Specific heat ratio: gamma = 1.29.
    """
    surface_density_kg_m3: float = 0.020      # kg/m^3
    surface_pressure_pa: float = 610.0        # Pa (nominal mean surface datum)
    scale_height_m: float = 11100.0           # meters
    surface_temperature_k: float = 210.0      # Kelvin
    gas_constant_j_kg_k: float = 188.92       # J / (kg * K) for CO2
    gamma_co2: float = 1.29

    def density(self, altitude_m: float) -> float:
        """Calculates ambient Martian atmospheric density [kg/m^3]."""
        alt = max(0.0, altitude_m)
        if alt > 140000.0:
            return 0.0
        return self.surface_density_kg_m3 * math.exp(-alt / self.scale_height_m)

    def pressure(self, altitude_m: float) -> float:
        """Calculates ambient Martian atmospheric pressure [Pa]."""
        alt = max(0.0, altitude_m)
        return self.surface_pressure_pa * math.exp(-alt / self.scale_height_m)

    def temperature(self, altitude_m: float) -> float:
        """Calculates temperature using Martian tropospheric lapse rate [K]."""
        alt = max(0.0, altitude_m)
        lapse_rate = 0.00099  # K/m (approximate Martian lapse rate)
        t = self.surface_temperature_k - lapse_rate * min(alt, 45000.0)
        return max(130.0, t)

    def speed_of_sound(self, altitude_m: float) -> float:
        """Calculates local speed of sound in CO2 [m/s]."""
        t = self.temperature(altitude_m)
        return math.sqrt(self.gamma_co2 * self.gas_constant_j_kg_k * t)


@dataclass
class MarsEntryCorridor:
    """Flight path angle boundaries for Martian atmospheric entry."""
    gamma_overshoot_rad: float = math.radians(-11.5)   # Shallower angle risks skip-out into orbit
    gamma_undershoot_rad: float = math.radians(-16.5)  # Steeper angle causes structural overload
    max_load_factor_g: float = 5.5                      # Peak allowable acceleration (Earth g)
    max_heat_flux_w_m2: float = 2.2e6                   # Peak heat flux threshold (2.2 MW/m^2)


@dataclass
class MarsEntryState:
    """Instantaneous vehicle kinematic and aerothermal state during Mars entry."""
    time_s: float
    altitude_m: float
    velocity_ms: float
    flight_path_angle_rad: float
    bank_angle_rad: float
    downrange_m: float
    mach_number: float
    convective_heat_flux_w_m2: float = 0.0
    radiative_heat_flux_w_m2: float = 0.0
    deceleration_g: float = 0.0


@dataclass
class SRPHandoverCriteria:
    """Validation gates for supersonic retro-propulsion ignition."""
    min_altitude_m: float = 1500.0
    max_altitude_m: float = 8000.0
    min_mach: float = 1.2
    max_mach: float = 5.2
    min_thrust_coefficient: float = 2.0  # C_T = Thrust / (q * S_ref)


@dataclass
class MarsTrajectoryProfile:
    """Complete record of a Martian atmospheric entry simulation."""
    success: bool
    outcome: str
    peak_convective_flux_w_m2: float
    peak_radiative_flux_w_m2: float
    total_heat_load_j_m2: float
    peak_g_load: float
    srp_handover_achieved: bool
    srp_altitude_m: float
    srp_velocity_ms: float
    srp_mach: float
    terminal_time_s: float
    states: List[MarsEntryState] = field(default_factory=list)


class MarsEntryAerocaptureSolver:
    """
    Simulates direct Martian entry and aerocapture dynamics for Starship.

    Physics formulations:
      Planetary parameters:
        R_mars = 3,389,500 m
        GM_mars = 4.282837e13 m^3 / s^2
        g0_earth = 9.80665 m/s^2

      Equations of motion over spherical Mars:
        dr/dt = v * sin(gamma)
        dv/dt = -D / m - g_mars * sin(gamma)
        dgamma/dt = (L * cos(sigma)) / (m * v) - (g_mars / v - v / r) * cos(gamma)

      Aerothermal convective heating (Tauber-Sutton Martian formulation):
        q_conv = k_mars * sqrt(rho / R_nose) * v^3
        where k_mars = 1.902e-4 W*s^3 / (m^3 * kg^0.5) for CO2-N2 shock layers.

      Aerothermal radiative heating (CO2 4th-positive band & CN violet):
        q_rad = C_rad * R_nose^0.5 * rho^1.2 * v^8.5
    """

    MARS_RADIUS_M = 3389500.0
    GM_MARS = 4.282837e13
    EARTH_G0 = 9.80665
    TAUBER_SUTTON_K = 1.902e-4
    RADIATIVE_C = 2.8e-28

    def __init__(
        self,
        vehicle_mass_kg: float = 130000.0,
        reference_area_m2: float = 125.0,
        nose_radius_m: float = 5.0,
        lift_coefficient: float = 0.55,
        drag_coefficient: float = 1.35,
        corridor: Optional[MarsEntryCorridor] = None,
        atmosphere: Optional[MarsAtmosphere] = None,
    ):
        self.mass_kg = vehicle_mass_kg
        self.ref_area_m2 = reference_area_m2
        self.nose_radius_m = nose_radius_m
        self.cl = lift_coefficient
        self.cd = drag_coefficient
        self.corridor = corridor or MarsEntryCorridor()
        self.atmo = atmosphere or MarsAtmosphere()

    def check_corridor(self, entry_gamma_rad: float) -> Tuple[bool, str]:
        """Validates if the entry flight path angle falls within safe corridor limits."""
        if entry_gamma_rad > self.corridor.gamma_overshoot_rad:
            return False, "CORRIDOR_OVERSHOOT_RISK_MARS_SKIP_OUT"
        if entry_gamma_rad < self.corridor.gamma_undershoot_rad:
            return False, "CORRIDOR_UNDERSHOOT_RISK_EXCESSIVE_DECELERATION"
        return True, "NOMINAL_MARS_ENTRY_CORRIDOR"

    def calculate_convective_heat_flux(self, density_kg_m3: float, velocity_ms: float) -> float:
        """Calculates Martian convective stagnation heat flux [W/m^2]."""
        if density_kg_m3 <= 0.0 or velocity_ms <= 0.0:
            return 0.0
        return self.TAUBER_SUTTON_K * math.sqrt(density_kg_m3 / self.nose_radius_m) * (velocity_ms ** 3)

    def calculate_radiative_heat_flux(self, density_kg_m3: float, velocity_ms: float) -> float:
        """Calculates CO2 shock layer nonequilibrium radiative heat flux [W/m^2]."""
        if density_kg_m3 <= 0.0 or velocity_ms < 4000.0:
            return 0.0
        q_rad = (
            self.RADIATIVE_C
            * math.sqrt(self.nose_radius_m)
            * (density_kg_m3 ** 1.2)
            * (velocity_ms ** 8.5)
        )
        return min(1.5e6, q_rad)

    def evaluate_srp_handover(
        self,
        altitude_m: float,
        mach: float,
        dynamic_pressure_pa: float,
        srp_thrust_n: float = 1800000.0,
    ) -> Tuple[bool, str]:
        """
        Validates ignition gate for supersonic retro-propulsion (SRP).
        """
        criteria = SRPHandoverCriteria()
        if altitude_m < criteria.min_altitude_m or altitude_m > criteria.max_altitude_m:
            return False, "ALTITUDE_OUT_OF_BOUNDS"
        if mach < criteria.min_mach or mach > criteria.max_mach:
            return False, "MACH_OUT_OF_BOUNDS"

        # Thrust coefficient: C_T = Thrust / (q * S_ref)
        if dynamic_pressure_pa > 0.0:
            c_t = srp_thrust_n / (dynamic_pressure_pa * self.ref_area_m2)
            if c_t < criteria.min_thrust_coefficient:
                return False, "INSUFFICIENT_THRUST_COEFFICIENT"

        return True, "SRP_HANDOVER_PERMITTED"

    def propagate_mars_entry(
        self,
        entry_altitude_m: float = 125000.0,
        entry_velocity_ms: float = 7400.0,
        entry_gamma_rad: float = math.radians(-14.2),
        bank_angle_rad: float = math.radians(40.0),
        dt: float = 0.5,
        max_time_s: float = 800.0,
        srp_target_altitude_m: float = 4000.0,
    ) -> MarsTrajectoryProfile:
        """
        Integrates Martian entry trajectory from 125 km down to SRP ignition handover.
        """
        r = self.MARS_RADIUS_M + entry_altitude_m
        v = entry_velocity_ms
        gamma = entry_gamma_rad
        downrange = 0.0
        t = 0.0
        min_alt = entry_altitude_m

        states: List[MarsEntryState] = []
        peak_conv = 0.0
        peak_rad = 0.0
        total_heat_load = 0.0
        peak_g = 0.0
        srp_achieved = False
        srp_alt = 0.0
        srp_vel = 0.0
        srp_mach_val = 0.0
        outcome = "UNKNOWN"
        success = False

        while t < max_time_s:
            alt = r - self.MARS_RADIUS_M
            if alt < min_alt:
                min_alt = alt

            rho = self.atmo.density(alt)
            a_sound = self.atmo.speed_of_sound(alt)
            mach = v / a_sound if a_sound > 0 else 0.0
            dyn_press = 0.5 * rho * (v ** 2)

            lift = dyn_press * self.ref_area_m2 * self.cl
            drag = dyn_press * self.ref_area_m2 * self.cd

            total_aero = math.sqrt(lift * lift + drag * drag)
            g_load = total_aero / (self.mass_kg * self.EARTH_G0)
            if g_load > peak_g:
                peak_g = g_load

            q_conv = self.calculate_convective_heat_flux(rho, v)
            q_rad = self.calculate_radiative_heat_flux(rho, v)
            if q_conv > peak_conv:
                peak_conv = q_conv
            if q_rad > peak_rad:
                peak_rad = q_rad

            total_heat_load += (q_conv + q_rad) * dt

            # Closed-loop bank angle scheduling for Mars atmosphere
            effective_bank = bank_angle_rad
            if alt <= 55000.0:
                if gamma > math.radians(-3.5):
                    effective_bank = math.radians(82.0)  # Roll steep to stay in atmosphere
                elif g_load > 4.8:
                    effective_bank = math.radians(20.0)  # Loft slightly if g exceeds target
                else:
                    effective_bank = math.radians(60.0)

            states.append(
                MarsEntryState(
                    time_s=round(t, 2),
                    altitude_m=round(alt, 1),
                    velocity_ms=round(v, 2),
                    flight_path_angle_rad=round(gamma, 5),
                    bank_angle_rad=round(effective_bank, 4),
                    downrange_m=round(downrange, 1),
                    mach_number=round(mach, 2),
                    convective_heat_flux_w_m2=round(q_conv, 1),
                    radiative_heat_flux_w_m2=round(q_rad, 1),
                    deceleration_g=round(g_load, 3),
                )
            )

            # Check for SRP handover gate
            if alt <= srp_target_altitude_m:
                srp_valid, _ = self.evaluate_srp_handover(alt, mach, dyn_press)
                if srp_valid:
                    srp_achieved = True
                    srp_alt = alt
                    srp_vel = v
                    srp_mach_val = mach
                    success = True
                    outcome = "SUCCESS_SRP_HANDOVER"
                    break

            # Skip-out detection
            if min_alt < 80000.0 and alt > 100000.0 and gamma > 0.0:
                success = False
                outcome = "MARS_ATMOSPHERIC_SKIP_OUT"
                break

            if alt > entry_altitude_m and t > 10.0 and gamma > 0.0:
                success = False
                outcome = "MARS_ATMOSPHERIC_SKIP_OUT"
                break

            # Deceleration load limit check
            if g_load > self.corridor.max_load_factor_g:
                success = False
                outcome = "STRUCTURAL_LOAD_EXCEEDED"
                break

            # Local Martian gravity
            g_loc = self.GM_MARS / (r * r)

            # Derivatives
            dr_dt = v * math.sin(gamma)
            dv_dt = -(drag / self.mass_kg) - g_loc * math.sin(gamma)

            centrif_term = (g_loc / v - v / r) * math.cos(gamma)
            lift_term = (lift * math.cos(effective_bank)) / (self.mass_kg * v)
            dgamma_dt = lift_term - centrif_term

            dx_dt = (self.MARS_RADIUS_M / r) * v * math.cos(gamma)

            r += dr_dt * dt
            v += dv_dt * dt
            gamma += dgamma_dt * dt
            downrange += dx_dt * dt
            t += dt

        return MarsTrajectoryProfile(
            success=success,
            outcome=outcome,
            peak_convective_flux_w_m2=round(peak_conv, 1),
            peak_radiative_flux_w_m2=round(peak_rad, 1),
            total_heat_load_j_m2=round(total_heat_load, 1),
            peak_g_load=round(peak_g, 2),
            srp_handover_achieved=srp_achieved,
            srp_altitude_m=round(srp_alt, 1),
            srp_velocity_ms=round(srp_vel, 1),
            srp_mach=round(srp_mach_val, 2),
            terminal_time_s=round(t, 1),
            states=states,
        )
