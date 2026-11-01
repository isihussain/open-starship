"""
Inclined orbit drift simulation and ground tracking pointing compensator.

Mitigates station-keeping propellant depletion anomalies (e.g., Türksat 1B in 2005, Türksat 1C in 2008),
where chemical propellant exhaustion forced operators to abandon North-South station-keeping,
causing lunisolar gravitational perturbations to induce a natural ~0.86 deg/year inclination drift
and daily figure-eight ground track oscillations.

Calculates orbital element drift, ground station Azimuth/Elevation pointing schedules,
antenna gain loss without tracking, and delta-v budgets for super-GEO graveyard disposal.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict
import math


@dataclass
class OrbitalElements:
    """
    Classical orbital elements for geostationary spacecraft.
    """
    semi_major_axis_km: float = 42_164.14     # GEO nominal orbital radius
    eccentricity: float = 0.0002
    inclination_deg: float = 0.05
    raan_deg: float = 75.0                    # Right Ascension of Ascending Node
    argument_of_perigee_deg: float = 0.0
    mean_anomaly_deg: float = 0.0
    nominal_longitude_deg: float = 42.0       # Türksat primary slot (42°E)


@dataclass
class GroundStation:
    """
    Uplink/Downlink ground station coordinates and antenna specifications.
    """
    name: str = "Ankara_Golbasi_Gateway"
    latitude_deg: float = 39.789
    longitude_deg: float = 32.812
    altitude_m: float = 950.0
    dish_diameter_m: float = 9.0
    frequency_ghz: float = 14.25              # Ku-band uplink
    beamwidth_3db_deg: float = 0.17           # ~70 * (lambda / D)


@dataclass
class InclinedOrbitReport:
    """
    Ground track displacement, pointing schedule, link degradation, and disposal margin.
    """
    elapsed_years: float
    current_inclination_deg: float
    daily_latitude_excursion_deg: float       # Peak +/- North-South excursion
    daily_longitude_drift_deg: float          # Peak East-West figure-8 oscillation
    antenna_azimuth_deg: float
    antenna_elevation_deg: float
    pointing_error_deg: float
    fixed_antenna_gain_loss_db: float
    tracking_required: bool
    graveyard_delta_v_mps: float
    graveyard_fuel_required_kg: float
    disposal_safe: bool
    status_message: str


class InclinedOrbitDynamics:
    """
    Simulates secular lunisolar inclination drift and calculates tracking antenna bias.
    """

    EARTH_RADIUS_KM = 6378.137
    GEO_RADIUS_KM = 42_164.14
    SPEED_OF_LIGHT = 299_792_458.0
    STANDARD_GRAVITY = 9.80665

    # Secular inclination drift rate driven by Moon and Sun gravitational third-body torque
    ANNUAL_INCLINATION_DRIFT_DEG = 0.865

    def __init__(
        self,
        spacecraft_dry_mass_kg: float = 1200.0,
        specific_impulse_s: float = 310.0,    # Apogee chemical bipropellant thruster Isp
        area_to_mass_ratio_m2_kg: float = 0.03, # Solar array cross-section to mass ratio
        reflectivity_coeff: float = 1.3,
    ):
        self.dry_mass = spacecraft_dry_mass_kg
        self.isp = specific_impulse_s
        self.amr = area_to_mass_ratio_m2_kg
        self.cr = reflectivity_coeff

    def propagate_drift(
        self,
        initial: OrbitalElements,
        elapsed_years: float,
        station: GroundStation,
        current_time_hours: float = 6.0,
        remaining_fuel_kg: float = 18.0,
    ) -> InclinedOrbitReport:
        """
        Calculates inclination drift over years, instantaneous 24-hr pointing angles, and link loss.
        """
        inc = initial.inclination_deg + (self.ANNUAL_INCLINATION_DRIFT_DEG * elapsed_years)

        # Diurnal ground track motion:
        # Latitude: phi(t) = inc * sin(omega * t)
        # Longitude: delta_lambda(t) = - (inc^2 / 8) * sin(2 * omega * t)
        omega_orbit = 2.0 * math.pi / 24.0   # rad/hour
        t_phase = omega_orbit * current_time_hours

        inc_rad = math.radians(inc)
        sub_sat_lat = inc * math.sin(t_phase)
        sub_sat_lon = initial.nominal_longitude_deg - math.degrees((inc_rad**2 / 8.0) * math.sin(2.0 * t_phase))

        # Ground station look angles (Azimuth and Elevation)
        az_deg, el_deg = self._calculate_look_angles(station.latitude_deg, station.longitude_deg, sub_sat_lat, sub_sat_lon)
        nominal_az, nominal_el = self._calculate_look_angles(station.latitude_deg, station.longitude_deg, 0.0, initial.nominal_longitude_deg)

        pointing_err = math.hypot(az_deg - nominal_az, el_deg - nominal_el)

        # Off-axis antenna gain loss model: L = 12 * (theta / theta_3dB)^2
        bw = station.beamwidth_3db_deg
        gain_loss_db = 12.0 * ((pointing_err / max(0.01, bw)) ** 2)

        tracking_needed = pointing_err > (0.25 * bw)

        # IADC Graveyard disposal delta-V requirement:
        # delta_h = 235 km + (1000 * Cr * A / m) km
        delta_h_km = 235.0 + (1000.0 * self.cr * self.amr)
        # Hohmann transfer from GEO to GEO + delta_h:
        # dv ~ 0.5 * v_geo * (delta_h / r_geo)
        v_geo = 3074.6  # m/s
        dv_graveyard = (0.5 * v_geo * (delta_h_km / self.GEO_RADIUS_KM))

        # Tsiolkovsky propellant requirement: delta_m = m_dry * (exp(dv / (Isp * g0)) - 1)
        ve = self.isp * self.STANDARD_GRAVITY
        fuel_needed = self.dry_mass * (math.exp(dv_graveyard / ve) - 1.0)

        disposal_ok = remaining_fuel_kg >= fuel_needed

        msg = (
            f"INCLINED ORBIT ACTIVE: Year {elapsed_years:.1f}, Inclination={inc:.2f}°. "
            f"Diurnal pointing offset={pointing_err:.2f}° (Gain loss={gain_loss_db:.1f} dB without tracking). "
            f"Graveyard delta-v={dv_graveyard:.1f} m/s (Requires {fuel_needed:.1f} kg fuel, remaining={remaining_fuel_kg:.1f} kg)."
        )

        return InclinedOrbitReport(
            elapsed_years=round(elapsed_years, 2),
            current_inclination_deg=round(inc, 3),
            daily_latitude_excursion_deg=round(inc, 3),
            daily_longitude_drift_deg=round(math.degrees(inc_rad**2 / 8.0), 4),
            antenna_azimuth_deg=round(az_deg, 2),
            antenna_elevation_deg=round(el_deg, 2),
            pointing_error_deg=round(pointing_err, 3),
            fixed_antenna_gain_loss_db=round(gain_loss_db, 2),
            tracking_required=tracking_needed,
            graveyard_delta_v_mps=round(dv_graveyard, 2),
            graveyard_fuel_required_kg=round(fuel_needed, 2),
            disposal_safe=disposal_ok,
            status_message=msg,
        )

    def _calculate_look_angles(
        self,
        gs_lat: float,
        gs_lon: float,
        sat_lat: float,
        sat_lon: float,
    ) -> Tuple[float, float]:
        """
        Calculates Azimuth and Elevation look angles from ground station to satellite.
        """
        lat_r = math.radians(gs_lat)
        d_lon_r = math.radians(sat_lon - gs_lon)
        sat_lat_r = math.radians(sat_lat)

        # Geocentric range vector:
        r_ratio = self.EARTH_RADIUS_KM / self.GEO_RADIUS_KM

        # Elevation angle calculation
        cos_beta = math.cos(lat_r) * math.cos(sat_lat_r) * math.cos(d_lon_r) + math.sin(lat_r) * math.sin(sat_lat_r)
        sin_beta = math.sqrt(max(0.0, 1.0 - cos_beta**2))

        el_rad = math.atan2(cos_beta - r_ratio, sin_beta)

        # Azimuth angle calculation
        az_rad = math.atan2(
            math.sin(d_lon_r) * math.cos(sat_lat_r),
            math.sin(sat_lat_r) * math.cos(lat_r) - math.cos(sat_lat_r) * math.sin(lat_r) * math.cos(d_lon_r),
        )

        az_deg = (math.degrees(az_rad) + 360.0) % 360.0
        el_deg = max(0.0, math.degrees(el_rad))

        return az_deg, el_deg
