"""
Upper-stage cryogenic propulsion health monitor and suborbital abort detector.

Mitigates launch-vehicle third-stage propulsion failures (e.g., Türksat 1A on Ariane 44LP V63,
January 1994), where cryogenic turbopump oxygen valve failure caused stage underperformance,
failing to achieve Geostationary Transfer Orbit (GTO) and resulting in ocean impact.

Monitors chamber pressure decay, turbopump speed, and inertial velocity shortfall,
calculating ballistic impact coordinates and latching spacecraft contingency safing.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import math


@dataclass
class PropulsionTelemetry:
    """
    Real-time propulsion health indicators from launch vehicle upper stage.
    """
    timestamp_s: float
    chamber_pressure_bar: float
    nominal_chamber_pressure_bar: float = 35.0   # Ariane 4 H10-3 nominal Pc
    turbopump_speed_rpm: float = 60_000.0
    nominal_turbopump_speed_rpm: float = 62_000.0
    lox_valve_position_percent: float = 100.0
    axial_acceleration_mps2: float = 18.5
    altitude_km: float = 180.0
    inertial_velocity_mps: float = 7800.0
    flight_phase: str = "THIRD_STAGE_BURN"


@dataclass
class AbortAssessment:
    """
    Evaluation of upper-stage injection integrity and contingency state.
    """
    nominal_thrust: bool
    abort_triggered: bool
    injection_shortfall_mps: float
    time_to_impact_s: float
    impact_latitude_deg: float
    impact_longitude_deg: float
    spacecraft_safing_commanded: bool
    telemetry_burst_active: bool
    status_message: str


class LaunchAbortDetector:
    """
    Detects upper-stage propulsion collapse and coordinates autonomous spacecraft survival actions.
    """

    EARTH_RADIUS_KM = 6378.137
    STANDARD_GRAVITY = 9.80665

    def __init__(
        self,
        min_pc_ratio: float = 0.80,            # Trip below 80% nominal chamber pressure
        min_turbopump_speed_ratio: float = 0.75, # Trip below 75% nominal turbopump speed
        min_valve_opening_percent: float = 60.0,
        target_gto_velocity_mps: float = 10_200.0,
    ):
        self.min_pc_ratio = min_pc_ratio
        self.min_tp_ratio = min_turbopump_speed_ratio
        self.min_valve_pct = min_valve_opening_percent
        self.target_v_gto = target_gto_velocity_mps
        self.abort_latched = False

    def evaluate(
        self,
        telemetry: PropulsionTelemetry,
        launch_site_lat_deg: float = 5.237,     # CSG Kourou latitude
        launch_site_lon_deg: float = -52.768,   # CSG Kourou longitude
        flight_azimuth_deg: float = 90.0,       # Due-east equatorial launch
    ) -> AbortAssessment:
        """
        Evaluates stage burn health and projects ballistic fallout point upon flameout.
        """
        pc_ratio = telemetry.chamber_pressure_bar / max(1.0, telemetry.nominal_chamber_pressure_bar)
        tp_ratio = telemetry.turbopump_speed_rpm / max(1.0, telemetry.nominal_turbopump_speed_rpm)
        valve_ok = telemetry.lox_valve_position_percent >= self.min_valve_pct

        is_underperforming = (
            pc_ratio < self.min_pc_ratio
            or tp_ratio < self.min_tp_ratio
            or not valve_ok
        )

        shortfall = max(0.0, self.target_v_gto - telemetry.inertial_velocity_mps)

        if is_underperforming:
            self.abort_latched = True

        if not self.abort_latched:
            return AbortAssessment(
                nominal_thrust=True,
                abort_triggered=False,
                injection_shortfall_mps=round(shortfall, 1),
                time_to_impact_s=0.0,
                impact_latitude_deg=0.0,
                impact_longitude_deg=0.0,
                spacecraft_safing_commanded=False,
                telemetry_burst_active=False,
                status_message="Upper stage cryogenic propulsion operating within nominal envelope.",
            )

        # Stage failed before orbital insertion speed achieved: compute suborbital ballistic arc
        # Altitude and velocity in SI:
        z0 = telemetry.altitude_km * 1000.0
        vz = telemetry.axial_acceleration_mps2 * 0.1  # Vertical component approximation
        vx = telemetry.inertial_velocity_mps

        # Vacuum freefall time from altitude z0:
        # z(t) = z0 + vz*t - 0.5*g*t^2 = 0
        discriminant = vz * vz + 2.0 * self.STANDARD_GRAVITY * z0
        t_impact = (vz + math.sqrt(max(0.0, discriminant))) / self.STANDARD_GRAVITY

        # Downrange ballistic distance traveled during fall
        downrange_km = (vx * t_impact) / 1000.0

        # Spherical geodetic projection along azimuth:
        az_rad = math.radians(flight_azimuth_deg)
        angular_dist_rad = downrange_km / self.EARTH_RADIUS_KM

        lat0_rad = math.radians(launch_site_lat_deg)
        lon0_rad = math.radians(launch_site_lon_deg)

        imp_lat_rad = math.asin(
            math.sin(lat0_rad) * math.cos(angular_dist_rad)
            + math.cos(lat0_rad) * math.sin(angular_dist_rad) * math.cos(az_rad)
        )
        imp_lon_rad = lon0_rad + math.atan2(
            math.sin(az_rad) * math.sin(angular_dist_rad) * math.cos(lat0_rad),
            math.cos(angular_dist_rad) - math.sin(lat0_rad) * math.sin(imp_lat_rad),
        )

        imp_lat = math.degrees(imp_lat_rad)
        imp_lon = math.degrees(imp_lon_rad)

        msg = (
            f"SUBORBITAL ABORT DETECTED: Stage pressure collapsed to {telemetry.chamber_pressure_bar:.1f} bar "
            f"(nominal {telemetry.nominal_chamber_pressure_bar:.1f} bar), valve={telemetry.lox_valve_position_percent:.0f}%. "
            f"Velocity shortfall={shortfall:.0f} m/s. Projected ocean impact at ({imp_lat:.2f}°, {imp_lon:.2f}°) "
            f"in {t_impact:.0f} seconds."
        )

        return AbortAssessment(
            nominal_thrust=False,
            abort_triggered=True,
            injection_shortfall_mps=round(shortfall, 1),
            time_to_impact_s=round(t_impact, 1),
            impact_latitude_deg=round(imp_lat, 3),
            impact_longitude_deg=round(imp_lon, 3),
            spacecraft_safing_commanded=True,
            telemetry_burst_active=True,
            status_message=msg,
        )
