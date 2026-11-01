"""
Ballistic Instantaneous Impact Point (IIP) and population corridor geofence predictor.

Mitigates inland booster drop hazards (e.g., CNSA Long March inland launch corridor spent stages
falling on inhabited villages, and uncontrolled upper-stage orbital decays).

Projects real-time instantaneous vacuum/drag impact coordinates, bounds uncertainty with
a 3-sigma dispersion ellipse, evaluates intersection against populated exclusion geofences,
and calculates corrective divert steering vectors to divert spent stages into safe zones.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import math


@dataclass
class GeofencePolygon:
    """
    Rectangular ground corridor or exclusion polygon in topocentric coordinates [km].
    """
    name: str
    is_populated_exclusion: bool  # True: inhabited zone to protect; False: designated drop zone
    x_min_km: float
    x_max_km: float
    y_min_km: float
    y_max_km: float

    def contains(self, x_km: float, y_km: float) -> bool:
        return (self.x_min_km <= x_km <= self.x_max_km) and (self.y_min_km <= y_km <= self.y_max_km)

    def intersects_box(self, x1: float, x2: float, y1: float, y2: float) -> bool:
        return not (x2 < self.x_min_km or x1 > self.x_max_km or y2 < self.y_min_km or y1 > self.y_max_km)


@dataclass
class KinematicVector:
    """
    Vehicle flight coordinates and velocities relative to launch pad origin.
    """
    altitude_m: float
    downrange_km: float
    crossrange_km: float
    vx_mps: float                 # Downrange velocity [m/s]
    vy_mps: float                 # Crossrange velocity [m/s]
    vz_mps: float                 # Vertical velocity [m/s]
    ballistic_coefficient: float = 850.0  # m / (Cd * A) [kg/m^2]


@dataclass
class DebrisFootprintReport:
    """
    Instantaneous impact coordinates, 3-sigma uncertainty bounds, and corridor safety.
    """
    iip_downrange_km: float
    iip_crossrange_km: float
    time_to_impact_s: float
    dispersion_major_km: float   # 3-sigma downrange dispersion radius
    dispersion_minor_km: float   # 3-sigma crossrange dispersion radius
    safe: bool
    breached_exclusions: List[str]
    divert_correction_mps: Tuple[float, float]  # Required (dv_x, dv_y) to redirect to safe drop zone
    afts_destruct_required: bool
    status_message: str


class DebrisHazardPredictor:
    """
    Monitors instantaneous impact point and enforces containment within safe drop corridors.
    """

    GRAVITY_MPS2 = 9.80665

    def __init__(
        self,
        zones: List[GeofencePolygon],
        safe_drop_center_km: Tuple[float, float] = (350.0, 0.0),
        atmospheric_scale_height_m: float = 8500.0,
    ):
        self.zones = zones
        self.safe_target_km = safe_drop_center_km
        self.scale_height = atmospheric_scale_height_m

    def compute_iip(self, kin: KinematicVector) -> Tuple[float, float, float]:
        """
        Calculates instantaneous ballistic impact point and fall time.
        z(t) = z0 + vz*t - 0.5*g*t^2 = 0
        """
        z0 = max(0.0, kin.altitude_m)
        vz = kin.vz_mps
        g = self.GRAVITY_MPS2

        # Quadratic formula for positive root (time to ground impact)
        discriminant = vz * vz + 2.0 * g * z0
        if discriminant < 0:
            t_fall = 0.0
        else:
            t_fall = (vz + math.sqrt(discriminant)) / g

        # Drag retardation approximation based on ballistic coefficient
        # Drag factor reduces vacuum ballistic range by ~8% to 15% depending on ballistic coeff
        drag_damping = max(0.82, 1.0 - (120.0 / max(100.0, kin.ballistic_coefficient)))

        x_iip = kin.downrange_km + (kin.vx_mps * t_fall * drag_damping) / 1000.0
        y_iip = kin.crossrange_km + (kin.vy_mps * t_fall * drag_damping) / 1000.0

        return x_iip, y_iip, t_fall

    def evaluate_trajectory(self, kin: KinematicVector) -> DebrisFootprintReport:
        """
        Evaluates whether 3-sigma debris footprint breaches any populated exclusion zone.
        """
        x_iip, y_iip, t_fall = self.compute_iip(kin)

        # 3-sigma dispersion modeled from wind shear and separation delta-v uncertainty
        # Dispersion expands with time-of-fall
        sigma_downrange_km = max(1.5, 0.035 * abs(kin.vx_mps) * math.sqrt(max(1.0, t_fall)) / 100.0)
        sigma_crossrange_km = max(1.0, 0.020 * abs(kin.vy_mps) * math.sqrt(max(1.0, t_fall)) / 100.0)

        major_3sigma_km = round(3.0 * sigma_downrange_km, 2)
        minor_3sigma_km = round(3.0 * sigma_crossrange_km, 2)

        # Bounding box of 3-sigma ellipse
        x1 = x_iip - major_3sigma_km
        x2 = x_iip + major_3sigma_km
        y1 = y_iip - minor_3sigma_km
        y2 = y_iip + minor_3sigma_km

        breached = []
        for zone in self.zones:
            if zone.is_populated_exclusion:
                if zone.intersects_box(x1, x2, y1, y2):
                    breached.append(zone.name)

        safe = len(breached) == 0

        # Divert calculation: velocity adjustment needed to shift IIP to designated safe drop target
        dx_target_km = self.safe_target_km[0] - x_iip
        dy_target_km = self.safe_target_km[1] - y_iip

        if t_fall > 1.0:
            # dv = dx / (t_fall * drag_damping)
            dv_x = (dx_target_km * 1000.0) / t_fall
            dv_y = (dy_target_km * 1000.0) / t_fall
        else:
            dv_x = 0.0
            dv_y = 0.0

        # AFTS triggered if breach cannot be averted within remaining fall time
        afts_required = (not safe) and (t_fall < 25.0 or math.hypot(dv_x, dv_y) > 400.0)

        if not safe:
            msg = (
                f"CORRIDOR VIOLATION DETECTED: 3-sigma debris footprint breaches exclusion zones {breached}. "
                f"IIP=({x_iip:.1f}, {y_iip:.1f}) km, time_to_impact={t_fall:.1f}s. "
                f"Divert vector required: dv=({dv_x:.1f}, {dv_y:.1f}) m/s."
            )
        else:
            msg = f"Debris trajectory clear: IIP=({x_iip:.1f}, {y_iip:.1f}) km inside permissible corridor."

        return DebrisFootprintReport(
            iip_downrange_km=round(x_iip, 2),
            iip_crossrange_km=round(y_iip, 2),
            time_to_impact_s=round(t_fall, 2),
            dispersion_major_km=major_3sigma_km,
            dispersion_minor_km=minor_3sigma_km,
            safe=safe,
            breached_exclusions=breached,
            divert_correction_mps=(round(dv_x, 2), round(dv_y, 2)),
            afts_destruct_required=afts_required,
            status_message=msg,
        )
