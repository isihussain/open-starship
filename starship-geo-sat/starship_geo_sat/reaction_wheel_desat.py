"""
Zero-magnetic-field reaction wheel momentum desaturation and thruster pulse scheduler.

Mitigates geostationary attitude control constraints (e.g., Türksat 6A indigenous platform, 2024),
where Earth's geomagnetic field at 35,786 km is negligible (~100 nT), rendering magnetic torquers
useless. Accumulation of solar radiation pressure (SRP) torque requires pulsed thruster firings
without violating station-keeping orbital box deadbands (+/-0.05 deg).

Models solar pressure disturbance accumulation, evaluates wheel saturation margins,
and computes minimum-propellant pure-torque thruster pulse sequences.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict
import math


@dataclass
class WheelAssemblyState:
    """
    Four-wheel pyramid reaction wheel telemetry [N*m*s].
    """
    hx_nms: float
    hy_nms: float
    hz_nms: float
    wheel_capacity_nms: float = 35.0          # Max saturation momentum per wheel
    saturation_threshold_percent: float = 80.0 # Trigger desaturation at 80% capacity


@dataclass
class SolarPressureProperties:
    """
    Solar array and reflector cross-section causing solar radiation torque.
    """
    total_area_m2: float = 38.0
    center_of_pressure_offset_m: float = 0.18  # Offset from center of mass [m]
    solar_flux_w_m2: float = 1361.0            # Solar constant at 1 AU
    reflectivity_factor: float = 1.35


@dataclass
class DesaturationPlan:
    """
    Calculated thruster pulses, propellant consumption, and net orbital disturbance.
    """
    desaturation_required: bool
    momentum_to_dump_nms: Tuple[float, float, float]
    pulse_duration_s: float
    thruster_pair_names: List[str]
    propellant_consumed_grams: float
    residual_momentum_nms: Tuple[float, float, float]
    net_translational_dv_mps: float            # Zero if pure torque couple
    station_keeping_deadband_safe: bool
    status_message: str


class ReactionWheelDesaturator:
    """
    Manages reaction wheel momentum in weak magnetic environments via coupled thruster firings.
    """

    SPEED_OF_LIGHT = 299_792_458.0
    STANDARD_GRAVITY = 9.80665

    def __init__(
        self,
        thruster_thrust_n: float = 1.0,        # 1-Newton monopropellant / bipropellant RCS thruster
        moment_arm_m: float = 1.6,             # Distance from spacecraft CoM to thruster axis [m]
        thruster_isp_s: float = 220.0,         # Hydrazine RCS Isp
        max_allowable_dv_mps: float = 0.005,   # Max delta-v leakage per desat maneuver
    ):
        self.thrust_n = thruster_thrust_n
        self.moment_arm = moment_arm_m
        self.isp = thruster_isp_s
        self.max_dv = max_allowable_dv_mps

    def calculate_srp_torque_nm(self, srp: SolarPressureProperties) -> float:
        """
        Calculates instantaneous solar radiation pressure disturbance torque [N*m].
        P_srp = (S / c) * (1 + Cr) * A
        tau = r_offset * P_srp
        """
        p_radiation = (srp.solar_flux_w_m2 / self.SPEED_OF_LIGHT) * srp.reflectivity_factor * srp.total_area_m2
        torque = srp.center_of_pressure_offset_m * p_radiation
        return torque

    def accumulate_momentum(
        self,
        current: WheelAssemblyState,
        srp_torque_nm: float,
        duration_hours: float,
    ) -> WheelAssemblyState:
        """
        Integrates secular solar torque accumulation over hours.
        """
        dt_seconds = duration_hours * 3600.0
        delta_h = srp_torque_nm * dt_seconds

        # Assume worst-case pitch/roll axis accumulation
        new_hx = current.hx_nms + (delta_h * 0.707)
        new_hy = current.hy_nms + (delta_h * 0.707)
        new_hz = current.hz_nms + (delta_h * 0.10)

        return WheelAssemblyState(
            hx_nms=new_hx,
            hy_nms=new_hy,
            hz_nms=new_hz,
            wheel_capacity_nms=current.wheel_capacity_nms,
            saturation_threshold_percent=current.saturation_threshold_percent,
        )

    def plan_desaturation(self, wheels: WheelAssemblyState) -> DesaturationPlan:
        """
        Determines if wheels breach saturation limit and schedules a pure-torque couple burn.
        """
        h_mag = math.sqrt(wheels.hx_nms**2 + wheels.hy_nms**2 + wheels.hz_nms**2)
        limit = wheels.wheel_capacity_nms * (wheels.saturation_threshold_percent / 100.0)

        needs_dump = h_mag >= limit

        if not needs_dump:
            return DesaturationPlan(
                desaturation_required=False,
                momentum_to_dump_nms=(0.0, 0.0, 0.0),
                pulse_duration_s=0.0,
                thruster_pair_names=[],
                propellant_consumed_grams=0.0,
                residual_momentum_nms=(round(wheels.hx_nms, 2), round(wheels.hy_nms, 2), round(wheels.hz_nms, 2)),
                net_translational_dv_mps=0.0,
                station_keeping_deadband_safe=True,
                status_message=f"Wheel momentum nominal: {h_mag:.2f} N*m*s < threshold {limit:.2f} N*m*s.",
            )

        # Torque per thruster couple: tau_couple = 2 * F * L (two opposed thrusters)
        torque_couple = 2.0 * self.thrust_n * self.moment_arm

        # Desired target: dump down to 20% capacity
        target_h = wheels.wheel_capacity_nms * 0.20
        delta_h_to_dump = max(0.0, h_mag - target_h)

        # Pulse duration: t = delta_h / tau_couple
        pulse_time = delta_h_to_dump / torque_couple

        # Propellant mass consumed: m = 2 * (F * t) / (Isp * g0)
        mass_flow_rate = (2.0 * self.thrust_n) / (self.isp * self.STANDARD_GRAVITY)
        fuel_kg = mass_flow_rate * pulse_time
        fuel_grams = fuel_kg * 1000.0

        # Residual momentum after balanced burn:
        ratio = target_h / max(0.01, h_mag)
        res_x = wheels.hx_nms * ratio
        res_y = wheels.hy_nms * ratio
        res_z = wheels.hz_nms * ratio

        # Pure torque couple has zero nominal translational force (F1 + F2 = 0)
        # Residual thruster plume misalignment leakage (<0.5% imbalance):
        dv_leakage = (0.005 * self.thrust_n * pulse_time) / 1500.0  # 1500 kg satellite mass
        deadband_ok = dv_leakage <= self.max_dv

        msg = (
            f"MOMENTUM DESATURATION COMMANDED: Wheel momentum {h_mag:.1f} N*m*s exceeded {limit:.1f} N*m*s. "
            f"Fired dual thruster couple for {pulse_time:.2f}s ({fuel_grams:.1f}g fuel). "
            f"Residual momentum={target_h:.1f} N*m*s. Net delta-v={dv_leakage*1000:.3f} mm/s (Deadband safe={deadband_ok})."
        )

        return DesaturationPlan(
            desaturation_required=True,
            momentum_to_dump_nms=(round(wheels.hx_nms - res_x, 2), round(wheels.hy_nms - res_y, 2), round(wheels.hz_nms - res_z, 2)),
            pulse_duration_s=round(pulse_time, 3),
            thruster_pair_names=["RCS_PITCH_POS", "RCS_PITCH_NEG"],
            propellant_consumed_grams=round(fuel_grams, 2),
            residual_momentum_nms=(round(res_x, 2), round(res_y, 2), round(res_z, 2)),
            net_translational_dv_mps=round(dv_leakage, 6),
            station_keeping_deadband_safe=deadband_ok,
            status_message=msg,
        )
