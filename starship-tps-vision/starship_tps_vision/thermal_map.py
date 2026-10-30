"""
Aerothermal risk mapping across the Starship hull structure.

Correlates flight dynamic telemetry (peak heat flux, angle of attack, dynamic pressure)
with vehicle surface coordinates to weigh tile inspection severity.
"""

from dataclasses import dataclass
import math
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class HullThermalZone:
    """
    Segmented structural region on Starship hull.
    """
    zone_id: str
    name: str
    z_min_m: float
    z_max_m: float
    azimuth_min_deg: float  # Windward belly is centered at 0 deg (-90 to +90 deg)
    azimuth_max_deg: float
    base_thermal_factor: float
    acoustic_vibration_factor: float


class AerothermalRiskMap:
    """
    Maps flight telemetry extremes to localized hull tile inspection risk factors.
    """

    def __init__(self, peak_heat_flux_w_m2: float = 1.2e5, peak_q_dyn_pa: float = 4.5e4):
        self.peak_heat_flux = peak_heat_flux_w_m2
        self.peak_q_dyn = peak_q_dyn_pa
        self.zones = self._initialize_zones()

    def _initialize_zones(self) -> List[HullThermalZone]:
        return [
            # 1. Nose Cone Stagnation Region (highest convective heating)
            HullThermalZone(
                zone_id="ZONE_NOSE_STAGNATION",
                name="Nose Cone Stagnation Cap",
                z_min_m=20.0,
                z_max_m=25.0,
                azimuth_min_deg=-90.0,
                azimuth_max_deg=90.0,
                base_thermal_factor=2.5,
                acoustic_vibration_factor=1.2,
            ),
            # 2. Windward Forward Barrel (high plasma shear)
            HullThermalZone(
                zone_id="ZONE_WINDWARD_FWD",
                name="Windward Forward Barrel",
                z_min_m=5.0,
                z_max_m=20.0,
                azimuth_min_deg=-80.0,
                azimuth_max_deg=80.0,
                base_thermal_factor=1.8,
                acoustic_vibration_factor=1.3,
            ),
            # 3. Windward Mid Barrel
            HullThermalZone(
                zone_id="ZONE_WINDWARD_MID",
                name="Windward Mid Barrel",
                z_min_m=-10.0,
                z_max_m=5.0,
                azimuth_min_deg=-80.0,
                azimuth_max_deg=80.0,
                base_thermal_factor=1.5,
                acoustic_vibration_factor=1.4,
            ),
            # 4. Flap Aerodynamic Seal & Hinge Areas (high turbulent shear & acoustic stress)
            HullThermalZone(
                zone_id="ZONE_FLAP_HINGES",
                name="Aft Flap Hinge Fairings",
                z_min_m=-22.0,
                z_max_m=-16.0,
                azimuth_min_deg=-120.0,
                azimuth_max_deg=120.0,
                base_thermal_factor=1.7,
                acoustic_vibration_factor=2.4,
            ),
            # 5. Aft Engine Skirt (highest vibration and engine plume recirculation)
            HullThermalZone(
                zone_id="ZONE_AFT_SKIRT",
                name="Aft Engine Skirt",
                z_min_m=-25.0,
                z_max_m=-20.0,
                azimuth_min_deg=-180.0,
                azimuth_max_deg=180.0,
                base_thermal_factor=1.2,
                acoustic_vibration_factor=2.8,
            ),
            # 6. Leeward Shadow Region (low heating, lower inspection urgency)
            HullThermalZone(
                zone_id="ZONE_LEEWARD_SHADOW",
                name="Leeward Expansion Flank",
                z_min_m=-25.0,
                z_max_m=25.0,
                azimuth_min_deg=90.0,
                azimuth_max_deg=270.0,
                base_thermal_factor=0.6,
                acoustic_vibration_factor=1.0,
            ),
        ]

    @classmethod
    def from_telemetry(cls, telemetry_records: List[Any]) -> "AerothermalRiskMap":
        """
        Derives peak environmental loads from a flight telemetry time-series.
        """
        max_q = 0.0
        max_hf = 0.0
        for r in telemetry_records:
            q = r.dynamic_pressure_pa if hasattr(r, "dynamic_pressure_pa") else r.get("dynamic_pressure_pa", 0.0)
            hf = r.heat_flux_w_m2 if hasattr(r, "heat_flux_w_m2") else r.get("heat_flux_w_m2", 0.0)
            max_q = max(max_q, q)
            max_hf = max(max_hf, hf)

        return cls(peak_heat_flux_w_m2=max(100.0, max_hf), peak_q_dyn_pa=max(1000.0, max_q))

    def evaluate_tile_risk(self, z_hull_m: float, azimuth_deg: float) -> Tuple[str, float]:
        """
        Determines the structural zone and combined risk factor for a specific tile.

        Returns:
            (zone_id, risk_multiplier)
        """
        # Normalize azimuth into [-180, +180]
        az = (azimuth_deg + 180.0) % 360.0 - 180.0

        matched_zone = self.zones[-1]  # Default to leeward shadow
        for zone in self.zones[:-1]:
            if (zone.z_min_m <= z_hull_m <= zone.z_max_m) and (
                zone.azimuth_min_deg <= az <= zone.azimuth_max_deg
            ):
                matched_zone = zone
                break

        # Calculate environment-weighted multiplier:
        # Reference normalizers: 100 kW/m^2 heat flux, 30 kPa dynamic pressure
        thermal_scale = math.sqrt(self.peak_heat_flux / 100_000.0)
        acoustic_scale = math.sqrt(self.peak_q_dyn / 30_000.0)

        risk_score = (
            matched_zone.base_thermal_factor * thermal_scale +
            matched_zone.acoustic_vibration_factor * acoustic_scale
        ) / 2.0

        return matched_zone.zone_id, round(max(0.5, risk_score), 2)
