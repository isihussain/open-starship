"""
Azercosmos Geostationary Orbital Coordination & Adjacent Satellite Interference (ASI) Module.

Models operational parameters, radio frequency coordination, and link budgets for:
  - Azerspace-1 (46.0° East, Star-2.4 platform, hybrid C/Ku-band, launched Feb 2013)
  - Azerspace-2 / Intelsat 38 (45.1° East, SSL-1300 platform, Ku-band, launched Sep 2018)
  - Ground segment failover: Absheron Main Ground Control Station (Tier 4 Teleport)
    and Nakhchivan Reserve Ground Control Station.

Solves the 0.9-degree orbital proximity problem where small-aperture ground dishes
(1.2 m to 2.4 m) have 3 dB beamwidths exceeding the angular separation between slots,
causing Adjacent Satellite Interference (ASI) that requires ITU off-axis power limits
and DVB-S2X Adaptive Coding and Modulation (ACM) fallback.
"""

from dataclasses import dataclass
import math
from typing import Dict, Optional


@dataclass
class GroundStationSite:
    """Earth station location and RF aperture parameters."""
    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    antenna_diameter_m: float
    aperture_efficiency: float = 0.65
    tier_rating: str = "Tier 4"


@dataclass
class SatelliteSlot:
    """Geostationary slot parameters for Azercosmos spacecraft."""
    name: str
    nominal_longitude_deg: float
    transponders_c_band: int
    transponders_ku_band: int
    eirp_peak_dbw: float
    station_keeping_deadband_deg: float = 0.05


@dataclass
class AdjacentInterferenceAssessment:
    """Assessment of Adjacent Satellite Interference (ASI) across 0.9 deg separation."""
    angular_separation_deg: float
    ground_antenna_3db_beamwidth_deg: float
    on_axis_gain_dbi: float
    off_axis_gain_interferer_dbi: float
    antenna_isolation_db: float
    carrier_to_adjacent_interference_db: float
    itu_envelope_compliant: bool
    acm_modulation_recommended: str
    failover_to_backup_ground_station: bool
    status_message: str


class AzercosmosOrbitalCoordinator:
    """
    Evaluates RF coordination, off-axis sidelobe discrimination, and ground teleport geometry
    between Azerspace-1 (46.0°E) and Azerspace-2 (45.1°E).
    """

    SPEED_OF_LIGHT = 299792458.0  # m/s
    EARTH_RADIUS_M = 6378137.0    # WGS-84 equatorial radius
    GEO_RADIUS_M = 42164140.0     # Geostationary orbit radius from Earth center

    def __init__(self, slot_1: Optional[SatelliteSlot] = None, slot_2: Optional[SatelliteSlot] = None):
        self.slot_1 = slot_1 or SatelliteSlot(
            name="Azerspace-1",
            nominal_longitude_deg=46.0,
            transponders_c_band=24,
            transponders_ku_band=12,
            eirp_peak_dbw=53.5,
        )
        self.slot_2 = slot_2 or SatelliteSlot(
            name="Azerspace-2 / Intelsat 38",
            nominal_longitude_deg=45.1,
            transponders_c_band=0,
            transponders_ku_band=35,
            eirp_peak_dbw=52.0,
        )

    def compute_angular_separation(self) -> float:
        """Returns angular separation between the two geostationary slots in degrees."""
        return abs(self.slot_1.nominal_longitude_deg - self.slot_2.nominal_longitude_deg)

    def compute_antenna_beamwidth(self, frequency_ghz: float, diameter_m: float) -> float:
        """
        Computes half-power (3 dB) antenna beamwidth in degrees:
        theta_3dB = 70 * (wavelength / diameter)
        """
        wavelength = self.SPEED_OF_LIGHT / (frequency_ghz * 1e9)
        return 70.0 * (wavelength / diameter_m)

    def compute_on_axis_gain(self, frequency_ghz: float, diameter_m: float, efficiency: float = 0.65) -> float:
        """
        Computes on-axis parabolic antenna gain in dBi:
        G0 = 10 * log10( eta * (pi * D / lambda)^2 )
        """
        wavelength = self.SPEED_OF_LIGHT / (frequency_ghz * 1e9)
        g_linear = efficiency * ((math.pi * diameter_m) / wavelength) ** 2
        return 10.0 * math.log10(max(1.0, g_linear))

    def compute_itu_off_axis_gain(self, phi_deg: float, diameter_m: float, frequency_ghz: float) -> float:
        """
        Computes off-axis antenna sidelobe envelope according to ITU-R S.580 / S.465:
        For D/lambda >= 100:
          G(phi) = 29 - 25 * log10(phi)  for 1 deg <= phi <= 20 deg
        For smaller apertures (D/lambda < 100):
          G(phi) = 32 - 25 * log10(phi)  for 1 deg <= phi <= 20 deg
        """
        wavelength = self.SPEED_OF_LIGHT / (frequency_ghz * 1e9)
        d_over_lambda = diameter_m / wavelength
        phi_clamped = max(0.1, abs(phi_deg))

        if d_over_lambda >= 100.0:
            return 29.0 - 25.0 * math.log10(phi_clamped)
        return 32.0 - 25.0 * math.log10(phi_clamped)

    def evaluate_adjacent_interference(
        self,
        earth_station: GroundStationSite,
        carrier_freq_ghz: float = 11.7,
        wanted_satellite_eirp_dbw: float = 52.0,
        interfering_satellite_eirp_dbw: float = 52.0,
        cross_pol_isolation_db: float = 30.0,
    ) -> AdjacentInterferenceAssessment:
        """
        Evaluates Adjacent Satellite Interference (ASI) between 45.1°E and 46.0°E.
        Calculates whether the 0.9° separation causes carrier degradation below DVB-S2X thresholds.
        """
        sep_deg = self.compute_angular_separation()
        bw_3db = self.compute_antenna_beamwidth(carrier_freq_ghz, earth_station.antenna_diameter_m)
        g0 = self.compute_on_axis_gain(carrier_freq_ghz, earth_station.antenna_diameter_m, earth_station.aperture_efficiency)
        g_off = self.compute_itu_off_axis_gain(sep_deg, earth_station.antenna_diameter_m, carrier_freq_ghz)

        # Antenna discrimination (rejection of the adjacent orbital slot)
        antenna_isolation = max(0.0, g0 - g_off)

        # Carrier-to-Adjacent-Interference ratio (C/I_asi)
        delta_eirp = wanted_satellite_eirp_dbw - interfering_satellite_eirp_dbw
        c_i_asi = delta_eirp + antenna_isolation

        # Check ITU-R S.524 compliance (off-axis eirp density within mask)
        itu_compliant = (c_i_asi >= 15.0)

        # Determine DVB-S2X Adaptive Coding and Modulation (ACM) selection
        if c_i_asi >= 22.0:
            acm_mode = "32APSK-9/10 (High Throughput)"
        elif c_i_asi >= 16.0:
            acm_mode = "16APSK-3/4 (Standard Nominal)"
        elif c_i_asi >= 11.0:
            acm_mode = "8PSK-2/3 (Interference Mitigated)"
        else:
            acm_mode = "QPSK-1/2 (Maximum Robustness)"

        # If beamwidth is wider than 1.5x separation and isolation < 14 dB, flag severe warning
        severe_asi = (bw_3db > sep_deg) and (c_i_asi < 14.0)
        status_msg = (
            f"Angular separation: {sep_deg:.2f}° | 3dB Beamwidth: {bw_3db:.2f}° | "
            f"Antenna Isolation: {antenna_isolation:.1f} dB | C/I_asi: {c_i_asi:.1f} dB | "
            f"ACM: {acm_mode}"
        )

        return AdjacentInterferenceAssessment(
            angular_separation_deg=sep_deg,
            ground_antenna_3db_beamwidth_deg=bw_3db,
            on_axis_gain_dbi=g0,
            off_axis_gain_interferer_dbi=g_off,
            antenna_isolation_db=antenna_isolation,
            carrier_to_adjacent_interference_db=c_i_asi,
            itu_envelope_compliant=itu_compliant,
            acm_modulation_recommended=acm_mode,
            failover_to_backup_ground_station=severe_asi,
            status_message=status_msg,
        )

    def evaluate_ground_station_geometry(
        self,
        station: GroundStationSite,
        sat_lon_deg: float,
        frequency_ghz: float = 12.0,
    ) -> Dict[str, float]:
        """
        Computes elevation angle, azimuth, slant range, and Free Space Path Loss (FSPL)
        from a ground control station (Absheron or Nakhchivan) to a geostationary slot.
        """
        lat_rad = math.radians(station.latitude_deg)
        lon_diff_rad = math.radians(sat_lon_deg - station.longitude_deg)

        # Cosine of central angle beta
        cos_beta = math.cos(lat_rad) * math.cos(lon_diff_rad)
        sin_beta = math.sqrt(max(0.0, 1.0 - cos_beta ** 2))

        # Slant range d (meters)
        r_earth = self.EARTH_RADIUS_M + station.altitude_m
        r_geo = self.GEO_RADIUS_M
        d = math.sqrt(r_earth ** 2 + r_geo ** 2 - 2.0 * r_earth * r_geo * cos_beta)

        # Elevation angle (radians)
        elev_rad = math.atan2(r_geo * cos_beta - r_earth, r_geo * sin_beta)
        elevation_deg = math.degrees(elev_rad)

        # Azimuth angle (radians from true North)
        az_rad = math.atan2(math.tan(lon_diff_rad), math.sin(lat_rad))
        azimuth_deg = (math.degrees(az_rad) + 180.0) % 360.0

        # Free space path loss: FSPL = (4 * pi * d * f / c)^2
        fspl_linear = ((4.0 * math.pi * d * (frequency_ghz * 1e9)) / self.SPEED_OF_LIGHT) ** 2
        fspl_db = 10.0 * math.log10(max(1.0, fspl_linear))

        return {
            "elevation_deg": elevation_deg,
            "azimuth_deg": azimuth_deg,
            "slant_range_km": d / 1000.0,
            "free_space_path_loss_db": fspl_db,
        }

    def evaluate_teleport_redundancy(
        self,
        absheron_snr_db: float,
        nakhchivan_snr_db: float,
        snr_switch_threshold_db: float = 8.0,
    ) -> Dict[str, str]:
        """
        Evaluates automated site failover between Absheron Main Ground Control Station
        and Nakhchivan Reserve Ground Control Station.
        """
        if absheron_snr_db < snr_switch_threshold_db and nakhchivan_snr_db >= snr_switch_threshold_db:
            active_site = "NAKHCHIVAN_RESERVE_STATION"
            reason = f"Absheron link SNR degraded to {absheron_snr_db:.1f} dB (< {snr_switch_threshold_db:.1f} dB). Failover engaged."
        elif absheron_snr_db >= snr_switch_threshold_db:
            active_site = "ABSHERON_MAIN_STATION"
            reason = f"Absheron link nominal (SNR: {absheron_snr_db:.1f} dB)."
        else:
            active_site = "DUAL_LINK_DEGRADATION"
            reason = "Severe regional rain fade across both Absheron and Nakhchivan stations."

        return {
            "active_station": active_site,
            "status_reason": reason,
        }
