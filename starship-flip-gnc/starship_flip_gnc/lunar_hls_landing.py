"""
Lunar Starship (HLS) terminal descent and plume-surface interaction (PSI) simulator.

Models Apollo and Artemis lunar soil mechanics under supersonic methalox plume exhaust:
  - Roberts viscous shear stress regolith erosion and cratering excavation
  - High-velocity hypervelocity ejecta particle impingement risks on landing legs
  - Vacuum ballistic dust cloud dispersal and optical/LiDAR attenuation
  - Terrain Relative Navigation (TRN) feature tracking vs. IMU dead-reckoning handover
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import math


@dataclass
class LunarLandingState:
    """State vector during lunar powered descent touchdown."""
    time_s: float
    altitude_m: float
    vertical_velocity_ms: float   # negative downwards
    horizontal_velocity_ms: float
    thrust_n: float
    vehicle_mass_kg: float
    surface_shear_pa: float = 0.0
    crater_depth_m: float = 0.0
    trn_optical_transmission: float = 1.0


@dataclass
class PlumeErosionReport:
    """Quantitative evaluation of regolith erosion and cratering."""
    erosion_active: bool
    peak_shear_stress_pa: float
    critical_shear_threshold_pa: float
    total_eroded_mass_kg: float
    final_crater_depth_m: float
    excavation_radius_m: float


@dataclass
class EjectaRiskAssessment:
    """Risk to landing gear, engine skirts, and navigation sensors from blast ejecta."""
    peak_particle_velocity_ms: float
    peak_kinetic_energy_j: float
    landing_gear_abrasion_risk: str  # "LOW", "MODERATE", "CRITICAL"
    sensor_window_damage: bool
    final_trn_mode: str              # "NOMINAL_OPTICAL_TRN", "DEGRADED_IMU_DEAD_RECKONING"
    touchdown_velocity_ms: float
    touchdown_stable: bool


class LunarHLSPlumeSolver:
    """
    Simulates the terminal 100 meters of Starship Human Landing System (HLS) touchdown.

    Physics formulations:
      Plume centerline stagnation and dynamic pressure (Roberts model):
        q_plume(h) = (gamma_gas * P_chamber) / (1 + (h / R_exit)^2)
        tau_shear = 0.5 * C_f * rho_exhaust * v_exhaust^2 * (R_exit / h)^2

      Regolith erosion rate (Apollo soil mechanics):
        m_dot_erosion = alpha_erosion * (max(0, tau_shear - tau_crit))^1.5 [kg/(m^2 * s)]
        h_crater = integral(m_dot_erosion / rho_bulk) dt

      Dust cloud optical depth (Beer-Lambert law):
        tau_optical = kappa_dust * sigma_dust
        T_opt = exp(-tau_optical)
        When T_opt < 0.20, TRN optical correlation fails.
    """

    LUNAR_GRAVITY_MS2 = 1.622        # m/s^2 (Apollo 11/17 measured mean)
    BULK_REGOLITH_DENSITY = 1520.0   # kg/m^3 (Apollo lunar soil bulk density)
    CRITICAL_SHEAR_PA = 0.08         # Pa (mobilization threshold for 70 micron grains)
    EROSION_ALPHA = 0.038            # Empirical erosion coefficient for lunar vacuum
    EXHAUST_VELOCITY_MS = 3300.0     # Methalox vacuum exhaust velocity (Isp ~ 336s)
    DUST_MASS_EXTINCTION = 0.12      # m^2 / kg (optical extinction cross-section)
    SKIN_FRICTION_COEFF = 0.0035

    def __init__(
        self,
        landing_mass_kg: float = 95000.0,
        nozzle_exit_radius_m: float = 1.15,
        number_of_active_thrusters: int = 4,
        max_total_thrust_n: float = 800000.0,
        landing_gear_clearance_m: float = 4.2,
    ):
        self.landing_mass_kg = landing_mass_kg
        self.nozzle_radius_m = nozzle_exit_radius_m
        self.num_thrusters = number_of_active_thrusters
        self.max_thrust_n = max_total_thrust_n
        self.gear_clearance_m = landing_gear_clearance_m

    def compute_surface_shear_stress(self, altitude_m: float, thrust_n: float) -> float:
        """
        Calculates peak surface aerodynamic shear stress exerted by thruster plume [Pa].
        """
        effective_alt = max(0.5, altitude_m)
        effective_exit_radius = self.nozzle_radius_m * math.sqrt(self.num_thrusters)

        # Dynamic expansion pressure ratio
        geom_factor = (effective_exit_radius / (effective_alt + effective_exit_radius)) ** 2
        # Dynamic pressure at ground interface
        gas_mass_flow = thrust_n / self.EXHAUST_VELOCITY_MS
        exhaust_area = math.pi * (effective_exit_radius ** 2)
        rho_exhaust = gas_mass_flow / (exhaust_area * self.EXHAUST_VELOCITY_MS)

        tau = 0.5 * self.SKIN_FRICTION_COEFF * rho_exhaust * (self.EXHAUST_VELOCITY_MS ** 2) * geom_factor
        return tau

    def evaluate_dust_optical_transmission(self, erosion_rate_kg_m2_s: float, altitude_m: float) -> float:
        """
        Calculates optical transmission (0.0 to 1.0) through the kicked-up dust cloud.
        """
        if erosion_rate_kg_m2_s <= 0.0:
            return 1.0

        # Column mass of suspended dust along line-of-sight in vacuum
        column_density = erosion_rate_kg_m2_s * (max(1.0, altitude_m) / 10.0) * 0.4
        tau_optical = self.DUST_MASS_EXTINCTION * column_density
        transmission = math.exp(-tau_optical)
        return max(0.01, min(1.0, transmission))

    def run_terminal_landing(
        self,
        initial_altitude_m: float = 80.0,
        initial_vertical_velocity_ms: float = -12.0,
        initial_horizontal_velocity_ms: float = 3.0,
        target_touchdown_vz_ms: float = -1.2,
        dt: float = 0.05,
        max_time_s: float = 40.0,
    ) -> Tuple[List[LunarLandingState], PlumeErosionReport, EjectaRiskAssessment]:
        """
        Simulates terminal closed-loop descent with throttle throttling and plume erosion.
        """
        alt = initial_altitude_m
        vz = initial_vertical_velocity_ms
        vx = initial_horizontal_velocity_ms
        mass = self.landing_mass_kg
        t = 0.0

        states: List[LunarLandingState] = []
        crater_depth = 0.0
        total_eroded_mass = 0.0
        peak_shear = 0.0
        peak_ejecta_v = 0.0
        peak_ejecta_ke = 0.0
        min_transmission = 1.0
        typical_grain_mass_kg = 5.0e-7  # ~150 micron basaltic particle

        while t < max_time_s and alt > 0.0:
            # Proportional vertical velocity guidance
            err_vz = target_touchdown_vz_ms - vz
            desired_accel_z = self.LUNAR_GRAVITY_MS2 + 0.8 * err_vz
            required_thrust = mass * desired_accel_z
            thrust = max(0.2 * self.max_thrust_n, min(self.max_thrust_n, required_thrust))

            # Plume impingement on surface
            shear = self.compute_surface_shear_stress(alt, thrust)
            if shear > peak_shear:
                peak_shear = shear

            # Erosion calculation
            excess_shear = max(0.0, shear - self.CRITICAL_SHEAR_PA)
            erosion_rate = self.EROSION_ALPHA * (excess_shear ** 1.5)  # kg/(m^2 * s)

            excavation_radius = 2.5 * self.nozzle_radius_m + 0.2 * alt
            excavation_area = math.pi * (excavation_radius ** 2)
            d_mass = erosion_rate * excavation_area * dt
            total_eroded_mass += d_mass
            crater_depth += (erosion_rate / self.BULK_REGOLITH_DENSITY) * dt

            # Particle ejection velocity and kinetic energy
            if excess_shear > 0.0:
                ejecta_v = 0.35 * self.EXHAUST_VELOCITY_MS * (excess_shear / (excess_shear + 1.0))
                if ejecta_v > peak_ejecta_v:
                    peak_ejecta_v = ejecta_v
                ke = 0.5 * typical_grain_mass_kg * (ejecta_v ** 2)
                if ke > peak_ejecta_ke:
                    peak_ejecta_ke = ke

            # Optical dust attenuation
            transmission = self.evaluate_dust_optical_transmission(erosion_rate, alt)
            if transmission < min_transmission:
                min_transmission = transmission

            states.append(
                LunarLandingState(
                    time_s=round(t, 2),
                    altitude_m=round(alt, 3),
                    vertical_velocity_ms=round(vz, 3),
                    horizontal_velocity_ms=round(vx, 3),
                    thrust_n=round(thrust, 1),
                    vehicle_mass_kg=round(mass, 1),
                    surface_shear_pa=round(shear, 4),
                    crater_depth_m=round(crater_depth, 5),
                    trn_optical_transmission=round(transmission, 4),
                )
            )

            # Equations of motion in lunar vacuum
            az = (thrust / mass) - self.LUNAR_GRAVITY_MS2
            # Horizontal velocity damping via RCS
            ax = -0.4 * vx

            vz += az * dt
            vx += ax * dt
            alt += vz * dt

            # Fuel depletion
            mass_flow = thrust / self.EXHAUST_VELOCITY_MS
            mass -= mass_flow * dt
            t += dt

        # Touchdown outcome assessment
        touchdown_stable = (abs(vz) <= 2.5) and (abs(vx) <= 1.0) and (crater_depth < 0.35)

        if peak_ejecta_v > 800.0:
            abrasion_risk = "CRITICAL"
        elif peak_ejecta_v > 300.0:
            abrasion_risk = "MODERATE"
        else:
            abrasion_risk = "LOW"

        sensor_damage = peak_ejecta_ke > 0.15  # Joules per particle
        trn_mode = "NOMINAL_OPTICAL_TRN" if min_transmission >= 0.20 else "DEGRADED_IMU_DEAD_RECKONING"

        erosion_report = PlumeErosionReport(
            erosion_active=total_eroded_mass > 0.1,
            peak_shear_stress_pa=round(peak_shear, 4),
            critical_shear_threshold_pa=self.CRITICAL_SHEAR_PA,
            total_eroded_mass_kg=round(total_eroded_mass, 2),
            final_crater_depth_m=round(crater_depth, 4),
            excavation_radius_m=round(2.5 * self.nozzle_radius_m, 2),
        )

        risk_report = EjectaRiskAssessment(
            peak_particle_velocity_ms=round(peak_ejecta_v, 1),
            peak_kinetic_energy_j=round(peak_ejecta_ke, 5),
            landing_gear_abrasion_risk=abrasion_risk,
            sensor_window_damage=sensor_damage,
            final_trn_mode=trn_mode,
            touchdown_velocity_ms=round(vz, 2),
            touchdown_stable=touchdown_stable,
        )

        return states, erosion_report, risk_report
