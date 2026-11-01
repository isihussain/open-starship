"""
Engine-out asymmetric thrust compensation and real-time burn profile reshaping.

Mitigates multi-engine flameout and uncoordinated loss-of-thrust incidents
(e.g., LandSpace Zhuque-2 vernier/second-stage shutdowns and early Starship landing engine dropouts).

Calculates center-of-mass thrust alignment gimbal trim to neutralize asymmetric pitching/yawing
moments, up-throttles operational engines within safety margins, and reshapes burn duration
to guarantee terminal velocity arrest.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import math


@dataclass
class EngineTelemetry:
    """
    Sensor feedback and mounting location for a rocket engine.
    """
    engine_id: str
    offset_x_m: float                  # Radial distance from vehicle centerline [m]
    offset_y_m: float
    chamber_pressure_bar: float        # Combustion chamber pressure [bar]
    commanded_thrust_n: float
    measured_thrust_n: float
    max_rated_thrust_n: float = 2.2e6  # 2.2 MN per Raptor class engine
    min_throttle_ratio: float = 0.40
    max_throttle_ratio: float = 1.00


@dataclass
class VehicleState:
    """
    Vehicle mass and geometry properties at current flight second.
    """
    mass_kg: float
    gimbal_to_com_distance_m: float    # Distance along body axis from gimbal pivot to CoM [m]
    nominal_isp_s: float = 330.0       # Sea-level / low-altitude specific impulse [s]
    max_gimbal_limit_rad: float = math.radians(18.0)  # +/- 18 deg max gimbal authority


@dataclass
class CompensationPlan:
    """
    Gimbal trim angles, throttle commands, and burn duration update.
    """
    failed_engines: List[str]
    operational_engines: List[str]
    net_thrust_n: float
    thrust_to_weight_ratio: float
    gimbal_trims_rad: Dict[str, Tuple[float, float]]  # {engine_id: (pitch_trim, yaw_trim)}
    throttle_commands: Dict[str, float]               # {engine_id: throttle_ratio}
    reshaped_burn_duration_s: float
    attitude_controllable: bool
    gravity_arrest_possible: bool
    message: str


class EngineOutCompensator:
    """
    Detects engine loss, trims gimbal vectors through CoM, and recalculates burn timeline.
    """

    GRAVITY_ACCEL_MPS2 = 9.80665

    def __init__(
        self,
        min_chamber_pressure_bar: float = 60.0,
        thrust_loss_threshold_ratio: float = 0.65,
    ):
        self.min_pc_bar = min_chamber_pressure_bar
        self.thrust_loss_ratio = thrust_loss_threshold_ratio

    def evaluate(
        self,
        engines: List[EngineTelemetry],
        vehicle: VehicleState,
        target_delta_v_mps: float,
        nominal_burn_duration_s: float,
    ) -> CompensationPlan:
        """
        Calculates corrective gimbal trim angles and reshapes burn duration.
        """
        operational = []
        failed = []

        for eng in engines:
            # Detect flameout or pressure collapse
            pc_collapsed = eng.chamber_pressure_bar < self.min_pc_bar
            thrust_collapsed = eng.measured_thrust_n < (eng.commanded_thrust_n * self.thrust_loss_ratio)

            if pc_collapsed or thrust_collapsed:
                failed.append(eng.engine_id)
            else:
                operational.append(eng)

        op_ids = [e.engine_id for e in operational]

        # Vehicle weight in Newtons
        weight_n = vehicle.mass_kg * self.GRAVITY_ACCEL_MPS2

        if not operational:
            return CompensationPlan(
                failed_engines=failed,
                operational_engines=[],
                net_thrust_n=0.0,
                thrust_to_weight_ratio=0.0,
                gimbal_trims_rad={},
                throttle_commands={e.engine_id: 0.0 for e in engines},
                reshaped_burn_duration_s=0.0,
                attitude_controllable=False,
                gravity_arrest_possible=False,
                message="TOTAL PROPULSION LOSS: All engines failed or shut down.",
            )

        # Calculate required total thrust to arrest descent (targeting TWR >= 1.15 if possible)
        num_op = len(operational)
        total_max_thrust = sum(e.max_rated_thrust_n for e in operational)

        # Boost throttle on operational engines to compensate for lost engine
        target_thrust_n = max(weight_n * 1.18, weight_n + 150_000.0)
        target_per_engine = target_thrust_n / num_op

        throttle_cmds = {}
        for eng in operational:
            ratio = target_per_engine / eng.max_rated_thrust_n
            clamped_ratio = max(eng.min_throttle_ratio, min(eng.max_throttle_ratio, ratio))
            throttle_cmds[eng.engine_id] = round(clamped_ratio, 3)

        for fid in failed:
            throttle_cmds[fid] = 0.0

        # Calculate actual net thrust under compensated throttle
        net_thrust = sum(throttle_cmds[e.engine_id] * e.max_rated_thrust_n for e in operational)
        twr = net_thrust / weight_n
        gravity_arrest_possible = twr > 1.0

        # Calculate CoM offset torque and solve gimbal trim angles
        # To align thrust vector through CoM:
        # For engine at (x_i, y_i), vector to CoM is (-x_i, -y_i, L_com)
        # Required gimbal angle: tan(theta_x) = -x_i / L_com, tan(theta_y) = -y_i / L_com
        l_com = max(1.0, vehicle.gimbal_to_com_distance_m)
        gimbal_trims = {}
        controllable = True

        for eng in operational:
            # Pitch gimbal trims y offset; Yaw gimbal trims x offset
            trim_pitch = math.atan2(-eng.offset_y_m, l_com)
            trim_yaw = math.atan2(-eng.offset_x_m, l_com)

            if abs(trim_pitch) > vehicle.max_gimbal_limit_rad or abs(trim_yaw) > vehicle.max_gimbal_limit_rad:
                controllable = False

            gimbal_trims[eng.engine_id] = (round(trim_pitch, 4), round(trim_yaw, 4))

        # Burn duration reshaping using mass-flow and rocket equation
        # Mass flow rate m_dot = T / (Isp * g0)
        g0 = self.GRAVITY_ACCEL_MPS2
        effective_exhaust_vel = vehicle.nominal_isp_s * g0

        # Required fuel mass: delta_m = m_0 * (1 - exp(-delta_v / v_e))
        fraction = 1.0 - math.exp(-target_delta_v_mps / effective_exhaust_vel)
        propellant_needed_kg = vehicle.mass_kg * fraction

        total_mdot = net_thrust / effective_exhaust_vel
        if total_mdot > 0:
            reshaped_duration = propellant_needed_kg / total_mdot
        else:
            reshaped_duration = 0.0

        # Build diagnostic message
        if failed:
            msg = (
                f"ENGINE-OUT MITIGATION ACTIVE: Engines {failed} offline. "
                f"Remaining {num_op} engine(s) throttled to {list(throttle_cmds.values())}. "
                f"TWR={twr:.2f}, burn extended from {nominal_burn_duration_s:.1f}s to {reshaped_duration:.1f}s."
            )
        else:
            msg = f"Nominal propulsion state: {num_op} engine(s) active, TWR={twr:.2f}."

        return CompensationPlan(
            failed_engines=failed,
            operational_engines=op_ids,
            net_thrust_n=round(net_thrust, 1),
            thrust_to_weight_ratio=round(twr, 3),
            gimbal_trims_rad=gimbal_trims,
            throttle_commands=throttle_cmds,
            reshaped_burn_duration_s=round(reshaped_duration, 2),
            attitude_controllable=controllable,
            gravity_arrest_possible=gravity_arrest_possible,
            message=msg,
        )
