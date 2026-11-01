"""
Aerodynamic control surface jam detection and torque authority reallocation.

Mitigates grid-fin and flap lockup failures (e.g., i-Space Hyperbola-1 Y5, August 2021),
where structural or thermal debris jammed a control surface hinge, causing uncompensated
parasitic roll/pitch moments and vehicle loss.

Detects actuator jam via motor current saturation and position tracking divergence,
isolates the frozen surface, calculates parasitic aerodynamic torque, and reallocates
deflection commands across remaining active flaps and reaction control thrusters (RCS).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import math


@dataclass
class ActuatorTelemetry:
    """
    Sensor feedback for a single aerodynamic control surface actuator.
    """
    name: str
    commanded_angle_rad: float
    measured_angle_rad: float
    motor_current_a: float
    rated_current_limit_a: float = 45.0
    stall_current_threshold_a: float = 40.0
    max_deflection_rad: float = 0.5236       # +/- 30 degrees (pi/6 rad)
    min_deflection_rad: float = -0.5236


@dataclass
class TorqueDemand:
    """
    Three-axis torque demand vector from flight guidance [N*m].
    """
    pitch_nm: float
    yaw_nm: float
    roll_nm: float


@dataclass
class AllocationResult:
    """
    Actuator surface commands and secondary trim thruster output.
    """
    surface_commands_rad: Dict[str, float]
    jammed_surfaces: List[str]
    parasitic_torque_nm: Tuple[float, float, float]
    achieved_aerodynamic_torque_nm: Tuple[float, float, float]
    rcs_assist_torque_nm: Tuple[float, float, float]
    residual_error_nm: Tuple[float, float, float]
    reallocation_converged: bool
    status_message: str


class ActuatorFaultAllocator:
    """
    Detects jammed aerodynamic surfaces and reallocates three-axis control torque.
    """

    # Surface effectiveness matrix: torque generated per radian deflection at dynamic pressure q = 10 kPa
    # Order: [pitch, yaw, roll]
    DEFAULT_EFFECTIVENESS = {
        "aft_port": (120_000.0, 40_000.0, 180_000.0),
        "aft_starboard": (120_000.0, -40_000.0, -180_000.0),
        "fwd_port": (-140_000.0, 30_000.0, 120_000.0),
        "fwd_starboard": (-140_000.0, -30_000.0, -120_000.0),
    }

    def __init__(
        self,
        divergence_threshold_rad: float = 0.08,  # ~4.6 deg tracking error
        current_saturation_cycles_to_fault: int = 3,
        reference_q_dyn_pa: float = 10_000.0,
        max_rcs_torque_nm: float = 50_000.0,
    ):
        self.divergence_thresh = divergence_threshold_rad
        self.fault_cycle_limit = current_saturation_cycles_to_fault
        self.ref_q = reference_q_dyn_pa
        self.max_rcs = max_rcs_torque_nm
        self.saturation_counters: Dict[str, int] = {
            name: 0 for name in self.DEFAULT_EFFECTIVENESS
        }
        self.jammed_status: Dict[str, bool] = {
            name: False for name in self.DEFAULT_EFFECTIVENESS
        }
        self.jammed_angles: Dict[str, float] = {
            name: 0.0 for name in self.DEFAULT_EFFECTIVENESS
        }

    def update_telemetry(self, telemetry_list: List[ActuatorTelemetry]):
        """
        Monitors motor current and position discrepancy to detect mechanical jams.
        """
        for telem in telemetry_list:
            name = telem.name
            if name not in self.saturation_counters:
                continue

            tracking_err = abs(telem.commanded_angle_rad - telem.measured_angle_rad)
            high_current = telem.motor_current_a >= telem.stall_current_threshold_a

            if high_current and (tracking_err >= self.divergence_thresh):
                self.saturation_counters[name] += 1
                if self.saturation_counters[name] >= self.fault_cycle_limit:
                    self.jammed_status[name] = True
                    self.jammed_angles[name] = telem.measured_angle_rad
            else:
                self.saturation_counters[name] = max(0, self.saturation_counters[name] - 1)

    def allocate(
        self,
        demand: TorqueDemand,
        q_dyn_pa: float,
        actuators: List[ActuatorTelemetry],
    ) -> AllocationResult:
        """
        Calculates deflections for unjammed surfaces and RCS trim to meet requested torque.
        """
        self.update_telemetry(actuators)

        # Scale effectiveness by dynamic pressure ratio q / q_ref (bounded to avoid div by zero)
        q_scale = max(0.01, q_dyn_pa / self.ref_q)

        # Calculate parasitic torque from frozen surfaces
        p_parasitic = 0.0
        y_parasitic = 0.0
        r_parasitic = 0.0
        jammed_names = []

        for name, is_jam in self.jammed_status.items():
            if is_jam:
                jammed_names.append(name)
                ang = self.jammed_angles[name]
                p_eff, y_eff, r_eff = self.DEFAULT_EFFECTIVENESS[name]
                p_parasitic += p_eff * ang * q_scale
                y_parasitic += y_eff * ang * q_scale
                r_parasitic += r_eff * ang * q_scale

        # Net torque required from operational surfaces
        p_target = demand.pitch_nm - p_parasitic
        y_target = demand.yaw_nm - y_parasitic
        r_target = demand.roll_nm - r_parasitic

        active_surfaces = [name for name in self.DEFAULT_EFFECTIVENESS if not self.jammed_status[name]]

        commands: Dict[str, float] = {}
        for name in self.DEFAULT_EFFECTIVENESS:
            if self.jammed_status[name]:
                commands[name] = self.jammed_angles[name]  # Disengage drive; surface is fixed
            else:
                commands[name] = 0.0

        if not active_surfaces:
            # All aero surfaces failed: handover entire torque to RCS
            rcs_p = max(-self.max_rcs, min(self.max_rcs, demand.pitch_nm - p_parasitic))
            rcs_y = max(-self.max_rcs, min(self.max_rcs, demand.yaw_nm - y_parasitic))
            rcs_r = max(-self.max_rcs, min(self.max_rcs, demand.roll_nm - r_parasitic))
            res_p = demand.pitch_nm - (p_parasitic + rcs_p)
            res_y = demand.yaw_nm - (y_parasitic + rcs_y)
            res_r = demand.roll_nm - (r_parasitic + rcs_r)
            return AllocationResult(
                surface_commands_rad=commands,
                jammed_surfaces=jammed_names,
                parasitic_torque_nm=(round(p_parasitic, 1), round(y_parasitic, 1), round(r_parasitic, 1)),
                achieved_aerodynamic_torque_nm=(round(p_parasitic, 1), round(y_parasitic, 1), round(r_parasitic, 1)),
                rcs_assist_torque_nm=(round(rcs_p, 1), round(rcs_y, 1), round(rcs_r, 1)),
                residual_error_nm=(round(res_p, 1), round(res_y, 1), round(res_r, 1)),
                reallocation_converged=False,
                status_message="CRITICAL: All aerodynamic surfaces jammed. Full RCS handover commanded.",
            )

        # Solve linear pseudo-inverse allocation for active surfaces:
        # B * delta = tau_target, where B is 3 x N_active
        # Simple least-squares with clamped limits [-30 deg, +30 deg]
        # Build matrix B
        b_cols = []
        for name in active_surfaces:
            pe, ye, re = self.DEFAULT_EFFECTIVENESS[name]
            b_cols.append([pe * q_scale, ye * q_scale, re * q_scale])

        delta_active = self._solve_least_squares(b_cols, [p_target, y_target, r_target])

        # Clamp to actuator saturation limits [-0.5236, 0.5236]
        max_rad = 0.5236
        clamped_deltas = []
        for d in delta_active:
            clamped = max(-max_rad, min(max_rad, d))
            clamped_deltas.append(clamped)

        for i, name in enumerate(active_surfaces):
            commands[name] = round(clamped_deltas[i], 4)

        # Calculate achieved aero torque
        aero_p = p_parasitic
        aero_y = y_parasitic
        aero_r = r_parasitic
        for i, name in enumerate(active_surfaces):
            pe, ye, re = self.DEFAULT_EFFECTIVENESS[name]
            d = clamped_deltas[i]
            aero_p += pe * d * q_scale
            aero_y += ye * d * q_scale
            aero_r += re * d * q_scale

        # Unmet torque assigned to RCS reaction thrusters
        deficit_p = demand.pitch_nm - aero_p
        deficit_y = demand.yaw_nm - aero_y
        deficit_r = demand.roll_nm - aero_r

        rcs_p = max(-self.max_rcs, min(self.max_rcs, deficit_p))
        rcs_y = max(-self.max_rcs, min(self.max_rcs, deficit_y))
        rcs_r = max(-self.max_rcs, min(self.max_rcs, deficit_r))

        res_p = demand.pitch_nm - (aero_p + rcs_p)
        res_y = demand.yaw_nm - (aero_y + rcs_y)
        res_r = demand.roll_nm - (aero_r + rcs_r)

        converged = (abs(res_p) < 5_000.0) and (abs(res_y) < 5_000.0) and (abs(res_r) < 5_000.0)

        if jammed_names:
            msg = (
                f"FAULT MITIGATED: Jammed surfaces [{', '.join(jammed_names)}] isolated. "
                f"Torque reallocated across {len(active_surfaces)} active surfaces with RCS trim."
            )
        else:
            msg = "Nominal aerodynamic control allocation."

        return AllocationResult(
            surface_commands_rad=commands,
            jammed_surfaces=jammed_names,
            parasitic_torque_nm=(round(p_parasitic, 1), round(y_parasitic, 1), round(r_parasitic, 1)),
            achieved_aerodynamic_torque_nm=(round(aero_p, 1), round(aero_y, 1), round(aero_r, 1)),
            rcs_assist_torque_nm=(round(rcs_p, 1), round(rcs_y, 1), round(rcs_r, 1)),
            residual_error_nm=(round(res_p, 1), round(res_y, 1), round(res_r, 1)),
            reallocation_converged=converged,
            status_message=msg,
        )

    @staticmethod
    def _solve_least_squares(b_cols: List[List[float]], target: List[float]) -> List[float]:
        """
        Solves B * delta = target for minimum-norm delta using normal equations (B^T * B + lambda*I)^-1 * B^T * target.
        """
        # B has 3 rows and n cols: B[r][c] = b_cols[c][r]
        n = len(b_cols)
        # Compute A = B^T * B (n x n)
        a_mat = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                dot = 0.0
                for r in range(3):
                    dot += b_cols[i][r] * b_cols[j][r]
                # Regularization (Tikhonov) to avoid singularity
                if i == j:
                    dot += 1e-4
                a_mat[i][j] = dot

        # Compute rhs = B^T * target (n)
        rhs = [0.0] * n
        for i in range(n):
            val = 0.0
            for r in range(3):
                val += b_cols[i][r] * target[r]
            rhs[i] = val

        # Solve A * x = rhs via Gaussian elimination
        return ActuatorFaultAllocator._gaussian_solve(a_mat, rhs)

    @staticmethod
    def _gaussian_solve(a: List[List[float]], b: List[float]) -> List[float]:
        n = len(b)
        # Deep copy
        m = [row[:] for row in a]
        y = b[:]

        for i in range(n):
            # Pivot
            max_row = i
            for k in range(i + 1, n):
                if abs(m[k][i]) > abs(m[max_row][i]):
                    max_row = k
            m[i], m[max_row] = m[max_row], m[i]
            y[i], y[max_row] = y[max_row], y[i]

            pivot = m[i][i]
            if abs(pivot) < 1e-9:
                continue

            for k in range(i + 1, n):
                factor = m[k][i] / pivot
                for j in range(i, n):
                    m[k][j] -= factor * m[i][j]
                y[k] -= factor * y[i]

        # Back substitution
        x = [0.0] * n
        for i in range(n - 1, -1, -1):
            pivot = m[i][i]
            if abs(pivot) < 1e-9:
                x[i] = 0.0
                continue
            sum_known = sum(m[i][j] * x[j] for j in range(i + 1, n))
            x[i] = (y[i] - sum_known) / pivot

        return x
