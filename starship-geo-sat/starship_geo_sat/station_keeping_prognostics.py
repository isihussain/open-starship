"""
Geostationary satellite station-keeping budget and fuel lifetime prognosticator.

Implements long-term orbital maintenance and End-of-Life (EOL) disposal physics:
  - North-South station-keeping (NSSK) lunisolar 3rd-body inclination drift
  - East-West station-keeping (EWSK) Earth triaxiality geopotential J22 longitude drift
  - Tank Pressure-Volume-Temperature (PVT) helium ullage propellant gauging
  - IADC super-GEO graveyard orbit disposal delta-v and reserve mass enforcement
  - Predictive operational life calculation for chemical and electric propulsion buses
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import math


@dataclass
class StationKeepingConfig:
    """Satellite propulsion and orbital parameters."""
    slot_longitude_deg: float                # Nominal geostationary longitude (e.g. 13.0, 42.0, 46.0)
    dry_mass_kg: float                       # Satellite dry mass at EOL (kg)
    current_propellant_kg: float             # Total propellant mass remaining in tanks (kg)
    thruster_isp_s: float = 310.0            # Specific impulse (310s bipropellant, 1800s Hall-effect)
    solar_array_area_m2: float = 40.0        # Cross-sectional area exposed to solar radiation
    radiation_pressure_cr: float = 1.30      # Surface reflectivity coefficient (1.0 = absorption, 2.0 = specular)
    is_electric_propulsion: bool = False     # False for chemical, True for all-electric (Eurostar Neo)


@dataclass
class TankPVTReading:
    """Pressure-Volume-Temperature telemetry from propulsion tanks."""
    tank_pressure_bar: float                 # Current regulated/blowdown tank pressure (bar)
    propellant_temp_k: float                 # Temperature (K)
    tank_volume_m3: float = 0.85             # Total physical interior tank volume
    helium_mass_kg: float = 1.25             # Fixed mass of gaseous helium pressurant
    propellant_density_kg_m3: float = 1180.0 # Density of liquid propellant (e.g. MMH / Hydrazine)


@dataclass
class StationKeepingBudget:
    """Annual delta-v and propellant consumption requirements."""
    annual_nssk_dv_ms: float
    annual_ewsk_dv_ms: float
    annual_eccentricity_dv_ms: float
    annual_total_dv_ms: float
    annual_propellant_consumption_kg: float


@dataclass
class LifetimePrognosisReport:
    """Prognostic forecast of remaining operational mission lifetime."""
    slot_longitude_deg: float
    current_propellant_kg: float
    graveyard_reserve_kg: float
    graveyard_delta_v_ms: float
    graveyard_altitude_increment_km: float
    usable_propellant_kg: float
    remaining_lifetime_years: float
    remaining_lifetime_days: float
    annual_burn_budget_ms: float
    eol_status: str                          # "HEALTHY_EXPEDITION", "EOL_WARNING_UNDER_2_YEARS", "IMMEDIATE_GRAVEYARD_DISPOSAL_REQUIRED"


class StationKeepingPrognosticator:
    """
    Predictive fuel consumption and orbital station-keeping evaluator for GEO satellites.

    Physics formulations:
      Lunisolar inclination secular drift:
        di/dt ~ 0.86 to 0.95 deg/year
        Delta_V_NSSK = 2 * v_geo * sin(Delta_i / 2) ~ 46 - 51 m/s/yr

      Triaxial geopotential J22 longitudinal drift:
        lambda_ddot = -3 * J22 * n^2 * (R_E / r_geo)^2 * sin(2 * (lambda - lambda_22))
        Stable nodes: 75.1°E, 105.3°W. Unstable nodes: 165.1°E, 14.9°W.
        Delta_V_EWSK ~ 1.5 to 4.5 m/s/yr depending on |lambda - lambda_stable|

      IADC Super-GEO Graveyard disposal:
        Delta_r_grave = 235 km + 1000 * C_R * (A / m_dry)
        Delta_V_grave = 0.25 * v_geo * (Delta_r_grave / r_geo) ~ 10.5 to 12.0 m/s

      Rocket equation:
        m_prop = m_dry * (exp(Delta_V / (I_sp * g_0)) - 1)
    """

    GEO_RADIUS_M = 42164140.0                # Geostationary orbital radius (m)
    GEO_VELOCITY_MS = 3074.66                # Circular geostationary velocity (m/s)
    STANDARD_GRAVITY = 9.80665               # m/s^2
    EARTH_RADIUS_M = 6371000.0
    J22_COEFF = -1.815e-6                    # Earth triaxiality harmonic
    STABLE_NODE_DEG = 75.1                   # Indian Ocean stable node (deg East)
    GAS_CONSTANT_HELIUM = 2077.1             # J / (kg * K) for Helium gas

    def __init__(self, config: Optional[StationKeepingConfig] = None):
        self.config = config or StationKeepingConfig(
            slot_longitude_deg=42.0,
            dry_mass_kg=2200.0,
            current_propellant_kg=280.0,
            thruster_isp_s=310.0,
        )

    def calculate_triaxial_ewsk_requirement(self, longitude_deg: float) -> float:
        """
        Calculates annual East-West station-keeping delta-v from J22 gravity harmonics [m/s/year].
        """
        # Angular offset from nearest stable/unstable equilibrium meridian
        delta_lambda_rad = math.radians(2.0 * (longitude_deg - self.STABLE_NODE_DEG))
        # Longitudinal acceleration magnitude
        geom_ratio = (self.EARTH_RADIUS_M / self.GEO_RADIUS_M) ** 2
        accel_geo = 3.0 * abs(self.J22_COEFF) * geom_ratio * abs(math.sin(delta_lambda_rad))

        # Integrate annual correction requirement with margin
        dv_annual = accel_geo * self.GEO_VELOCITY_MS * (365.25 * 86400.0) * 0.08 + 1.2
        return round(min(6.0, max(1.5, dv_annual)), 2)

    def compute_annual_budget(self) -> StationKeepingBudget:
        """
        Calculates total annual delta-v and propellant mass required for full station-keeping.
        """
        # North-South inclination correction (47.5 m/s average annual secular drift)
        annual_nssk = 48.2

        # East-West longitude correction
        annual_ewsk = self.calculate_triaxial_ewsk_requirement(self.config.slot_longitude_deg)

        # Solar radiation pressure eccentricity control
        annual_ecc = 1.4

        total_annual_dv = annual_nssk + annual_ewsk + annual_ecc

        # Rocket equation propellant consumption per year
        effective_mass = self.config.dry_mass_kg + self.config.current_propellant_kg
        exhaust_velocity = self.config.thruster_isp_s * self.STANDARD_GRAVITY
        mass_ratio = math.exp(total_annual_dv / exhaust_velocity)
        annual_fuel_kg = effective_mass * (1.0 - (1.0 / mass_ratio))

        return StationKeepingBudget(
            annual_nssk_dv_ms=round(annual_nssk, 2),
            annual_ewsk_dv_ms=round(annual_ewsk, 2),
            annual_eccentricity_dv_ms=round(annual_ecc, 2),
            annual_total_dv_ms=round(total_annual_dv, 2),
            annual_propellant_consumption_kg=round(annual_fuel_kg, 2),
        )

    def gauge_propellant_pvt(self, telemetry: TankPVTReading) -> float:
        """
        Estimates remaining liquid propellant mass via helium pressurant gas law [kg].
        """
        pressure_pa = telemetry.tank_pressure_bar * 1e5
        if pressure_pa <= 0.0 or telemetry.propellant_temp_k <= 0.0:
            return 0.0

        # Helium volume: V_He = (m_He * R_He * T) / P
        v_helium_m3 = (
            telemetry.helium_mass_kg
            * self.GAS_CONSTANT_HELIUM
            * telemetry.propellant_temp_k
        ) / pressure_pa

        # Remaining liquid propellant volume
        v_liquid_m3 = max(0.0, telemetry.tank_volume_m3 - v_helium_m3)
        propellant_mass_kg = v_liquid_m3 * telemetry.propellant_density_kg_m3
        return round(propellant_mass_kg, 2)

    def evaluate_graveyard_disposal_requirements(self) -> Tuple[float, float, float]:
        """
        Calculates IADC compliant graveyard orbit altitude increment and fuel reserve.
        Returns (delta_r_grave_km, delta_v_grave_ms, required_reserve_propellant_kg).
        """
        # IADC formula: Delta_r = 235 km + 1000 * C_R * (A / m)
        area_to_mass = self.config.solar_array_area_m2 / self.config.dry_mass_kg
        delta_r_km = 235.0 + 1000.0 * self.config.radiation_pressure_cr * area_to_mass

        # Two-burn Hohmann transfer delta-v to circularize at graveyard altitude:
        # dv_total = dv_perigee + dv_apogee ~ 0.5 * v_geo * (Delta_r / r_geo)
        r_geo_km = self.GEO_RADIUS_M * 1e-3
        delta_v_ms = 0.50 * self.GEO_VELOCITY_MS * (delta_r_km / r_geo_km)

        # Propellant mass required for graveyard boost
        exhaust_velocity = self.config.thruster_isp_s * self.STANDARD_GRAVITY
        reserve_fuel_kg = self.config.dry_mass_kg * (math.exp(delta_v_ms / exhaust_velocity) - 1.0)

        # Include 15% safety margin on graveyard disposal fuel
        reserve_fuel_kg *= 1.15

        return round(delta_r_km, 2), round(delta_v_ms, 2), round(reserve_fuel_kg, 2)

    def forecast_mission_lifetime(self) -> LifetimePrognosisReport:
        """
        Forecasts remaining years and days of station-keeping before graveyard reserve is breached.
        """
        budget = self.compute_annual_budget()
        delta_r_km, delta_v_grave, reserve_kg = self.evaluate_graveyard_disposal_requirements()

        usable_propellant_kg = self.config.current_propellant_kg - reserve_kg

        if usable_propellant_kg <= 0.0:
            remaining_years = 0.0
            remaining_days = 0.0
            status = "IMMEDIATE_GRAVEYARD_DISPOSAL_REQUIRED"
        else:
            remaining_years = usable_propellant_kg / budget.annual_propellant_consumption_kg
            remaining_days = remaining_years * 365.25
            if remaining_years < 2.0:
                status = "EOL_WARNING_UNDER_2_YEARS"
            else:
                status = "HEALTHY_EXPEDITION"

        return LifetimePrognosisReport(
            slot_longitude_deg=self.config.slot_longitude_deg,
            current_propellant_kg=round(self.config.current_propellant_kg, 2),
            graveyard_reserve_kg=round(reserve_kg, 2),
            graveyard_delta_v_ms=round(delta_v_grave, 2),
            graveyard_altitude_increment_km=round(delta_r_km, 2),
            usable_propellant_kg=round(max(0.0, usable_propellant_kg), 2),
            remaining_lifetime_years=round(remaining_years, 2),
            remaining_lifetime_days=round(remaining_days, 1),
            annual_burn_budget_ms=budget.annual_total_dv_ms,
            eol_status=status,
        )
