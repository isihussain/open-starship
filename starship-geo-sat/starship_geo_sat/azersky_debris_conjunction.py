"""
AzerSky Sun-Synchronous Orbit Debris Impact & Anomaly Diagnostics Module.

Models operational dynamics, hypervelocity orbital debris impact physics, and telemetry loss
diagnostics for the AzerSky Earth observation satellite:
  - Orbit: Sun-synchronous orbit (SSO), altitude 694.9 km, inclination 98.2°
  - Platform: Astrosat-500 (Airbus SPOT 7 heritage, 712 kg, 1.5 m panchromatic resolution)
  - Historical Incident: March 17, 2023, 19:34-20:48 UTC sudden telemetry cessation
  - Diagnostic: US Space Surveillance Network confirmed the satellite remained intact in orbit,
    pointing to a micro-debris or micrometeoroid collision (10-15 km/s) that severed electrical
    power bus harnesses without catastrophic structural fragmentation.
"""

from dataclasses import dataclass
import math
from typing import Dict, Optional


@dataclass
class AzerSkyOrbitSpec:
    """AzerSky Earth observation satellite specifications."""
    name: str = "AzerSky (SPOT 7)"
    altitude_km: float = 694.9
    inclination_deg: float = 98.2
    dry_mass_kg: float = 712.0
    cross_section_m2: float = 4.2
    bus_skin_thickness_mm: float = 1.6
    bus_nominal_voltage_volts: float = 28.0
    moment_of_inertia_kg_m2: float = 480.0


@dataclass
class DebrisImpactTelemetry:
    """Telemetry frame at time of orbital communication loss."""
    event_timestamp_utc: str
    estimated_particle_diameter_mm: float
    relative_velocity_km_s: float
    debris_density_g_cm3: float = 2.8  # Typical aluminum space debris density
    measured_bus_voltage_volts: float = 0.0
    ssn_tracked_object_count: int = 1   # US SSN tracked bodies (1 = intact hull)
    rf_signal_strength_dbm: float = -140.0  # Loss of carrier (< -130 dBm)


@dataclass
class DebrisAnomalyReport:
    """Comprehensive anomaly diagnostic report for AzerSky mission review."""
    particle_mass_grams: float
    kinetic_energy_joules: float
    equivalent_tnt_grams: float
    hypervelocity_penetration_mm: float
    bus_skin_breached: bool
    power_harness_severed: bool
    spacecraft_tumble_rate_deg_s: float
    anomaly_classification: str
    service_continuity_plan: str
    status_message: str


class AzerSkyDebrisAnalyzer:
    """
    Analyzes hypervelocity orbital collisions, penetration depth into spacecraft bus shielding,
    and post-impact tumbling dynamics in Low Earth Orbit (LEO).
    """

    EARTH_MU = 3.986004418e14  # m^3/s^2
    EARTH_RADIUS_M = 6378137.0  # m
    ALUMINUM_SPEED_OF_SOUND_KM_S = 5.1  # km/s
    TARGET_ALUMINUM_DENSITY_G_CM3 = 2.70

    def __init__(self, spec: Optional[AzerSkyOrbitSpec] = None):
        self.spec = spec or AzerSkyOrbitSpec()

    def compute_orbital_velocity(self) -> float:
        """
        Calculates circular orbital speed at AzerSky's altitude (694.9 km) in m/s:
        v = sqrt(mu / (R_earth + h))
        """
        r_orbit = self.EARTH_RADIUS_M + (self.spec.altitude_km * 1000.0)
        return math.sqrt(self.EARTH_MU / r_orbit)

    def compute_orbital_period_minutes(self) -> float:
        """Calculates orbital period in minutes."""
        r_orbit = self.EARTH_RADIUS_M + (self.spec.altitude_km * 1000.0)
        t_seconds = 2.0 * math.pi * math.sqrt((r_orbit ** 3) / self.EARTH_MU)
        return t_seconds / 60.0

    def compute_particle_mass_grams(self, diameter_mm: float, density_g_cm3: float = 2.8) -> float:
        """Calculates spherical particle mass in grams from diameter (mm)."""
        radius_cm = (diameter_mm / 10.0) / 2.0
        volume_cm3 = (4.0 / 3.0) * math.pi * (radius_cm ** 3)
        return volume_cm3 * density_g_cm3

    def compute_kinetic_energy(self, mass_grams: float, velocity_km_s: float) -> float:
        """
        Calculates impact kinetic energy in Joules:
        E_k = 0.5 * m * v^2
        """
        mass_kg = mass_grams / 1000.0
        velocity_m_s = velocity_km_s * 1000.0
        return 0.5 * mass_kg * (velocity_m_s ** 2)

    def compute_cour_palais_penetration(
        self,
        diameter_mm: float,
        velocity_km_s: float,
        particle_density_g_cm3: float = 2.8,
    ) -> float:
        """
        Calculates hypervelocity penetration depth (mm) in aluminum using the Cour-Palais formulation:
        P = 0.53 * d_p^1.06 * (rho_p / rho_t)^0.5 * (v_rel / c_sound)^(2/3)
        """
        d_p_cm = diameter_mm / 10.0
        density_ratio = particle_density_g_cm3 / self.TARGET_ALUMINUM_DENSITY_G_CM3
        velocity_ratio = velocity_km_s / self.ALUMINUM_SPEED_OF_SOUND_KM_S

        p_depth_cm = (
            0.53
            * (d_p_cm ** 1.06)
            * (density_ratio ** 0.5)
            * (max(0.1, velocity_ratio) ** (2.0 / 3.0))
        )
        return p_depth_cm * 10.0  # Return in mm

    def estimate_tumble_rate(
        self,
        particle_mass_grams: float,
        velocity_km_s: float,
        impact_lever_arm_m: float = 1.1,
    ) -> float:
        """
        Estimates angular disturbance rate (deg/s) induced by the inelastic collision impulse:
        delta_H = m * v * r_lever
        omega = delta_H / I_yy
        """
        mass_kg = particle_mass_grams / 1000.0
        velocity_m_s = velocity_km_s * 1000.0
        angular_momentum_impulse = mass_kg * velocity_m_s * impact_lever_arm_m
        omega_rad_s = angular_momentum_impulse / self.spec.moment_of_inertia_kg_m2
        return math.degrees(omega_rad_s)

    def diagnose_anomaly(self, telemetry: DebrisImpactTelemetry) -> DebrisAnomalyReport:
        """
        Evaluates flight telemetry and orbital surveillance data to diagnose root cause
        of sudden contact loss on March 17, 2023.
        """
        p_mass_g = self.compute_particle_mass_grams(
            telemetry.estimated_particle_diameter_mm,
            telemetry.debris_density_g_cm3,
        )
        e_k = self.compute_kinetic_energy(p_mass_g, telemetry.relative_velocity_km_s)
        tnt_equiv_g = e_k / 4184.0  # 1 g TNT = 4184 J

        penetration_mm = self.compute_cour_palais_penetration(
            telemetry.estimated_particle_diameter_mm,
            telemetry.relative_velocity_km_s,
            telemetry.debris_density_g_cm3,
        )

        skin_breached = penetration_mm >= self.spec.bus_skin_thickness_mm
        harness_severed = skin_breached and (telemetry.measured_bus_voltage_volts < 2.0)
        tumble_rate = self.estimate_tumble_rate(p_mass_g, telemetry.relative_velocity_km_s)

        # Automated classification
        if telemetry.ssn_tracked_object_count > 10:
            classification = "CATASTROPHIC_EXPLOSIVE_FRAGMENTATION"
            continuity_plan = "IMMEDIATE_DEBRIS_TRACKING_AND_CONSTELLATION_ALERT"
        elif harness_severed and telemetry.ssn_tracked_object_count == 1:
            classification = "HYPERVELOCITY_MICRODEBRIS_COLLISION"
            continuity_plan = "SPOT-6_TWIN_HANDOFF_AND_AZERSKY-2_DISPATCH"
        elif telemetry.measured_bus_voltage_volts < 2.0:
            classification = "INTERNAL_ELECTRICAL_POWER_BUS_FAILURE"
            continuity_plan = "BATTERY_RECONDITIONING_COMMAND_UPLINK"
        else:
            classification = "COMMUNICATION_LINK_OCCULTATION"
            continuity_plan = "NEXT_ORBITAL_PASS_TT_AND_C_ACQUISITION"

        status_msg = (
            f"Anomaly: {classification} | Impact Energy: {e_k:.0f} J ({tnt_equiv_g:.2f}g TNT) | "
            f"Penetration: {penetration_mm:.2f} mm (Skin: {self.spec.bus_skin_thickness_mm} mm) | "
            f"Tumble Rate: {tumble_rate:.2f}°/s | Fallback: {continuity_plan}"
        )

        return DebrisAnomalyReport(
            particle_mass_grams=p_mass_g,
            kinetic_energy_joules=e_k,
            equivalent_tnt_grams=tnt_equiv_g,
            hypervelocity_penetration_mm=penetration_mm,
            bus_skin_breached=skin_breached,
            power_harness_severed=harness_severed,
            spacecraft_tumble_rate_deg_s=tumble_rate,
            anomaly_classification=classification,
            service_continuity_plan=continuity_plan,
            status_message=status_msg,
        )
