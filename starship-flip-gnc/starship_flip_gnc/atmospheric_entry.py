"""
Atmospheric entry trajectory solver and aerothermal corridor evaluator for Starship.

Propagates 3-DoF point-mass spherical planet entry dynamics from orbital interface
(120 km) through peak aerothermal heating, plasma sheath communications blackout,
and bank-angle lift vector modulation to supersonic/transonic handover (10 km).
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import math


@dataclass
class EntryState:
    """Instantaneous state vector during atmospheric entry."""
    time_s: float
    altitude_m: float
    velocity_ms: float
    flight_path_angle_rad: float  # gamma (negative for descent)
    bank_angle_rad: float         # sigma (roll around velocity vector)
    downrange_m: float
    crossrange_m: float
    heat_flux_w_m2: float = 0.0
    deceleration_g: float = 0.0
    plasma_freq_hz: float = 0.0


@dataclass
class EntryCorridorLimits:
    """Aerodynamic and thermal boundaries for safe atmospheric entry."""
    gamma_undershoot_rad: float = math.radians(-1.75)  # Steep boundary (structural load limit)
    gamma_overshoot_rad: float = math.radians(-1.15)   # Shallow boundary (skip-out limit)
    max_load_factor_g: float = 5.0                      # Peak allowable acceleration (g)
    max_heat_flux_w_m2: float = 1.5e6                   # Peak heat flux before tile damage (1.5 MW/m^2)


@dataclass
class EntryTrajectoryProfile:
    """Summary and trajectory records of an atmospheric entry simulation."""
    success: bool
    outcome: str
    peak_heat_flux_w_m2: float
    peak_g_load: float
    total_heat_load_j_m2: float
    blackout_duration_s: float
    terminal_altitude_m: float
    terminal_velocity_ms: float
    terminal_time_s: float
    states: List[EntryState] = field(default_factory=list)


class AtmosphericEntrySolver:
    """
    3-DoF atmospheric entry equations of motion with bank-angle guidance.

    Equations of motion over spherical Earth:
      dr/dt = v * sin(gamma)
      dv/dt = -D / m - g * sin(gamma)
      dgamma/dt = (L * cos(sigma)) / (m * v) - (g / v - v / r) * cos(gamma)
      dx/dt = (R_earth / r) * v * cos(gamma)  (downrange progress)

    Aerothermal convective stagnation heat flux (Sutton-Graves formulation):
      q_dot = k_sg * sqrt(rho / R_nose) * v^3
      where k_sg = 1.7415e-4 W*s^3 / (m^3 * kg^0.5) for Earth air.

    Plasma cutoff frequency (telemetry blackout):
      n_e = C_plasma * sqrt(rho) * v^2
      f_p = (1 / (2*pi)) * sqrt(n_e * e^2 / (m_e * eps_0))
    """

    EARTH_RADIUS_M = 6371000.0
    STANDARD_GRAVITY = 9.80665
    GM_EARTH = 3.986004418e14  # m^3 / s^2
    SUTTON_GRAVES_K = 1.7415e-4
    ELECTRON_CHARGE = 1.602176634e-19
    ELECTRON_MASS = 9.1093837e-31
    VACUUM_PERMITTIVITY = 8.8541878128e-12
    PLASMA_ION_COEFF = 8.5e11  # Calibrated for hypersonic shock ionization

    def __init__(
        self,
        vehicle_mass_kg: float = 120000.0,
        reference_area_m2: float = 125.0,
        nose_radius_m: float = 5.0,
        lift_coefficient: float = 0.60,
        drag_coefficient: float = 1.20,
        corridor_limits: Optional[EntryCorridorLimits] = None,
    ):
        self.mass_kg = vehicle_mass_kg
        self.ref_area_m2 = reference_area_m2
        self.nose_radius_m = nose_radius_m
        self.cl = lift_coefficient
        self.cd = drag_coefficient
        self.corridor = corridor_limits or EntryCorridorLimits()

    def get_atmospheric_density(self, altitude_m: float) -> float:
        """Calculates exponential atmospheric density with scale height segments."""
        if altitude_m <= 0.0:
            return 1.225
        if altitude_m > 130000.0:
            return 0.0

        if altitude_m < 25000.0:
            rho_0 = 1.225
            h_scale = 7200.0
            return rho_0 * math.exp(-altitude_m / h_scale)
        elif altitude_m < 50000.0:
            rho_0 = 0.040
            h_scale = 7800.0
            return rho_0 * math.exp(-(altitude_m - 25000.0) / h_scale)
        elif altitude_m < 85000.0:
            rho_0 = 1.0e-3
            h_scale = 6500.0
            return rho_0 * math.exp(-(altitude_m - 50000.0) / h_scale)
        else:
            rho_0 = 8.2e-6
            h_scale = 8200.0
            return rho_0 * math.exp(-(altitude_m - 85000.0) / h_scale)

    def calculate_stagnation_heat_flux(self, altitude_m: float, velocity_ms: float) -> float:
        """
        Calculates convective stagnation heat flux via Sutton-Graves relation [W/m^2].
        """
        rho = self.get_atmospheric_density(altitude_m)
        if rho <= 0.0 or velocity_ms <= 0.0:
            return 0.0
        return self.SUTTON_GRAVES_K * math.sqrt(rho / self.nose_radius_m) * (velocity_ms ** 3)

    def calculate_plasma_cutoff_frequency(self, altitude_m: float, velocity_ms: float) -> Tuple[float, bool]:
        """
        Calculates plasma electron density and cutoff frequency [Hz].
        Returns (f_plasma_hz, is_blackout_at_s_band).
        S-band baseline frequency: 2.2 GHz.
        """
        rho = self.get_atmospheric_density(altitude_m)
        if rho <= 0.0 or velocity_ms < 1500.0:
            return 0.0, False

        # Shock layer electron density [electrons / m^3]
        n_e = self.PLASMA_ION_COEFF * math.sqrt(rho) * (velocity_ms ** 2)
        n_e = max(0.0, n_e)

        radicand = (n_e * (self.ELECTRON_CHARGE ** 2)) / (self.ELECTRON_MASS * self.VACUUM_PERMITTIVITY)
        f_p = (1.0 / (2.0 * math.pi)) * math.sqrt(radicand)
        is_s_band_blackout = f_p >= 2.2e9
        return f_p, is_s_band_blackout

    def check_corridor_entry(self, flight_path_angle_rad: float) -> Tuple[bool, str]:
        """Validates if initial entry angle falls inside the safe entry corridor."""
        if flight_path_angle_rad > self.corridor.gamma_overshoot_rad:
            return False, "CORRIDOR_OVERSHOOT_RISK_ATMOSPHERIC_SKIP"
        if flight_path_angle_rad < self.corridor.gamma_undershoot_rad:
            return False, "CORRIDOR_UNDERSHOOT_RISK_EXCESSIVE_DECELERATION"
        return True, "NOMINAL_ENTRY_CORRIDOR"

    def propagate_entry(
        self,
        entry_altitude_m: float = 120000.0,
        entry_velocity_ms: float = 7600.0,
        entry_gamma_rad: float = math.radians(-1.45),
        bank_angle_schedule_rad: float = math.radians(35.0),
        dt: float = 0.5,
        max_time_s: float = 1800.0,
        target_handover_altitude_m: float = 10000.0,
        enable_bank_modulation: bool = True,
    ) -> EntryTrajectoryProfile:
        """
        Integrates atmospheric entry equations from entry interface down to terminal altitude.
        """
        r = self.EARTH_RADIUS_M + entry_altitude_m
        v = entry_velocity_ms
        gamma = entry_gamma_rad
        downrange = 0.0
        crossrange = 0.0
        time = 0.0
        min_alt_reached = entry_altitude_m

        states: List[EntryState] = []
        peak_heat_flux = 0.0
        peak_g = 0.0
        total_heat_load = 0.0
        blackout_time_s = 0.0
        success = False
        outcome = "UNKNOWN"

        while time < max_time_s:
            alt = r - self.EARTH_RADIUS_M
            if alt < min_alt_reached:
                min_alt_reached = alt

            if alt <= target_handover_altitude_m:
                success = True
                outcome = "SUCCESS_SUBSONIC_HANDOVER"
                break

            # Skip-out detection: vehicle climbed back up into upper atmosphere/space with positive gamma
            if min_alt_reached < 80000.0 and alt > 95000.0 and gamma > 0.0:
                success = False
                outcome = "ATMOSPHERIC_SKIP_OUT"
                break

            if alt > entry_altitude_m and time > 10.0 and gamma > 0.0:
                success = False
                outcome = "ATMOSPHERIC_SKIP_OUT"
                break

            rho = self.get_atmospheric_density(alt)
            dyn_press = 0.5 * rho * (v ** 2)

            lift = dyn_press * self.ref_area_m2 * self.cl
            drag = dyn_press * self.ref_area_m2 * self.cd

            total_aero_force = math.sqrt(lift * lift + drag * drag)
            g_load = total_aero_force / (self.mass_kg * self.STANDARD_GRAVITY)
            if g_load > peak_g:
                peak_g = g_load

            q_dot = self.calculate_stagnation_heat_flux(alt, v)
            if q_dot > peak_heat_flux:
                peak_heat_flux = q_dot

            total_heat_load += q_dot * dt

            f_p, is_blackout = self.calculate_plasma_cutoff_frequency(alt, v)
            if is_blackout:
                blackout_time_s += dt

            # Closed-loop bank modulation to limit peak g-loads below structural limits
            effective_bank = bank_angle_schedule_rad
            if enable_bank_modulation:
                if g_load > 2.8:
                    effective_bank = math.radians(12.0)  # Roll towards wings-level to increase lift and loft
                elif g_load < 1.0 and alt < 65000.0:
                    effective_bank = math.radians(50.0)  # Roll steeper to descend faster

            # Record state
            states.append(
                EntryState(
                    time_s=round(time, 2),
                    altitude_m=round(alt, 1),
                    velocity_ms=round(v, 2),
                    flight_path_angle_rad=round(gamma, 5),
                    bank_angle_rad=round(effective_bank, 4),
                    downrange_m=round(downrange, 1),
                    crossrange_m=round(crossrange, 1),
                    heat_flux_w_m2=round(q_dot, 1),
                    deceleration_g=round(g_load, 3),
                    plasma_freq_hz=round(f_p, 1),
                )
            )

            # Check hard limits
            if g_load > self.corridor.max_load_factor_g:
                success = False
                outcome = "STRUCTURAL_LOAD_EXCEEDED"
                break

            # Local gravitational acceleration
            g_local = self.GM_EARTH / (r * r)

            # Derivatives
            dr_dt = v * math.sin(gamma)
            dv_dt = -(drag / self.mass_kg) - g_local * math.sin(gamma)

            centrif_term = (g_local / v - v / r) * math.cos(gamma)
            lift_term = (lift * math.cos(effective_bank)) / (self.mass_kg * v)
            dgamma_dt = lift_term - centrif_term

            dx_dt = (self.EARTH_RADIUS_M / r) * v * math.cos(gamma)
            dy_dt = (self.EARTH_RADIUS_M / r) * v * math.cos(gamma) * math.sin(effective_bank) * 0.1

            r += dr_dt * dt
            v += dv_dt * dt
            gamma += dgamma_dt * dt
            downrange += dx_dt * dt
            crossrange += dy_dt * dt
            time += dt

        final_alt = r - self.EARTH_RADIUS_M
        return EntryTrajectoryProfile(
            success=success,
            outcome=outcome,
            peak_heat_flux_w_m2=round(peak_heat_flux, 1),
            peak_g_load=round(peak_g, 2),
            total_heat_load_j_m2=round(total_heat_load, 1),
            blackout_duration_s=round(blackout_time_s, 1),
            terminal_altitude_m=round(final_alt, 1),
            terminal_velocity_ms=round(v, 2),
            terminal_time_s=round(time, 1),
            states=states,
        )
