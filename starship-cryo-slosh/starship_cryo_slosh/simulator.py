"""
Propellant slosh time-series simulator and ullage ingestion analyzer.

Integrates header tank fluid responses across flight telemetry records
and identifies cavitation/flameout risk zones during flip maneuvers.
"""

from dataclasses import dataclass, asdict
import math
import json
from typing import List, Dict, Any, Optional, Tuple

from .tank import HeaderTankAssembly, CryogenicFluid
from .pendulum_model import EquivalentSloshModel, SloshState


@dataclass
class SloshTelemetryPoint:
    """
    Instantaneous coupled slosh dynamics record.
    """
    time_s: float
    altitude_m: float
    lox_phi_deg: float
    lox_submergence_m: float
    lox_gas_ingestion: bool
    ch4_phi_deg: float
    ch4_submergence_m: float
    ch4_gas_ingestion: bool
    net_slosh_torque_nm: float
    com_shift_x_mm: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SloshSimulationResult:
    """
    Summary analysis of cryogenic slosh behavior during the flight maneuver.
    """
    total_duration_s: float
    lox_gas_ingestion_detected: bool
    lox_total_gas_exposure_time_s: float
    lox_min_submergence_m: float
    ch4_gas_ingestion_detected: bool
    ch4_total_gas_exposure_time_s: float
    ch4_min_submergence_m: float
    max_slosh_torque_nm: float
    max_com_shift_x_mm: float
    risk_level: str  # "SAFE", "WARNING", "CRITICAL_CAVITATION"
    summary_message: str


class SloshSimulator:
    """
    Executes coupled time-stepping simulation of LOX and CH4 header tanks
    against flight acceleration profiles.
    """

    def __init__(
        self,
        assembly: Optional[HeaderTankAssembly] = None,
        lox_mass_kg: float = 17_500.0,
        ch4_mass_kg: float = 7_500.0,
    ):
        self.assembly = assembly or HeaderTankAssembly.default_starship()
        self.lox_model = EquivalentSloshModel(
            tank=self.assembly.lox_tank,
            fluid=CryogenicFluid.liquid_oxygen(),
            initial_fluid_mass_kg=lox_mass_kg,
        )
        self.ch4_model = EquivalentSloshModel(
            tank=self.assembly.ch4_tank,
            fluid=CryogenicFluid.liquid_methane(),
            initial_fluid_mass_kg=ch4_mass_kg,
        )

    def simulate_telemetry(
        self,
        telemetry_records: List[Any],
    ) -> Tuple[SloshSimulationResult, List[SloshTelemetryPoint]]:
        """
        Runs numerical integration over telemetry records.

        Accepts either TelemetryRecord objects or dicts with keys:
          time_s, altitude_m, pitch_rate_deg_s, accel_lateral_mps2, accel_axial_mps2, total_mass_kg
        """
        if not telemetry_records:
            raise ValueError("Telemetry records list cannot be empty.")

        lox_state = SloshState(phi_rad=0.0, phi_dot_rad_s=0.0)
        ch4_state = SloshState(phi_rad=0.0, phi_dot_rad_s=0.0)

        history: List[SloshTelemetryPoint] = []

        lox_gas_time = 0.0
        ch4_gas_time = 0.0
        lox_min_sub = 999.0
        ch4_min_sub = 999.0
        max_torque = 0.0
        max_com_shift = 0.0

        for i in range(len(telemetry_records) - 1):
            curr = telemetry_records[i]
            nxt = telemetry_records[i + 1]

            # Support both dataclass and dictionary access:
            t = curr.time_s if hasattr(curr, "time_s") else curr["time_s"]
            alt = curr.altitude_m if hasattr(curr, "altitude_m") else curr["altitude_m"]
            a_lat = curr.accel_lateral_mps2 if hasattr(curr, "accel_lateral_mps2") else curr["accel_lateral_mps2"]
            a_ax = curr.accel_axial_mps2 if hasattr(curr, "accel_axial_mps2") else curr["accel_axial_mps2"]
            w_deg_s = curr.pitch_rate_deg_s if hasattr(curr, "pitch_rate_deg_s") else curr["pitch_rate_deg_s"]
            total_mass = curr.total_mass_kg if hasattr(curr, "total_mass_kg") else curr["total_mass_kg"]

            t_next = nxt.time_s if hasattr(nxt, "time_s") else nxt["time_s"]
            w_next = nxt.pitch_rate_deg_s if hasattr(nxt, "pitch_rate_deg_s") else nxt["pitch_rate_deg_s"]

            dt = max(1e-4, t_next - t)
            # Angular acceleration of vehicle body:
            vehicle_pitch_accel = math.radians((w_next - w_deg_s) / dt)

            # Evaluate submergence and gas ingestion:
            lox_sub, lox_ingested = self.lox_model.evaluate_inlet_submergence(lox_state)
            ch4_sub, ch4_ingested = self.ch4_model.evaluate_inlet_submergence(ch4_state)

            if lox_ingested:
                lox_gas_time += dt
            if ch4_ingested:
                ch4_gas_time += dt

            lox_min_sub = min(lox_min_sub, lox_sub)
            ch4_min_sub = min(ch4_min_sub, ch4_sub)

            # Forces and torques:
            phi_ddot_lox = self.lox_model.compute_acceleration(
                lox_state, a_lat, a_ax, w_deg_s, vehicle_pitch_accel
            )
            phi_ddot_ch4 = self.ch4_model.compute_acceleration(
                ch4_state, a_lat, a_ax, w_deg_s, vehicle_pitch_accel
            )

            _, _, torque_lox = self.lox_model.compute_slosh_forces_and_torques(
                lox_state, phi_ddot_lox, a_lat, a_ax
            )
            _, _, torque_ch4 = self.ch4_model.compute_forces_and_torques(
                ch4_state, phi_ddot_ch4, a_lat, a_ax
            ) if hasattr(self.ch4_model, "compute_forces_and_torques") else self.ch4_model.compute_slosh_forces_and_torques(
                ch4_state, phi_ddot_ch4, a_lat, a_ax
            )

            net_torque = torque_lox + torque_ch4
            max_torque = max(max_torque, abs(net_torque))

            # CoM shift in vehicle lateral axis (mm):
            dx_lox = self.lox_model.m1 * self.lox_model.arm_length_lp * math.sin(lox_state.phi_rad)
            dx_ch4 = self.ch4_model.m1 * self.ch4_model.arm_length_lp * math.sin(ch4_state.phi_rad)
            com_shift_mm = ((dx_lox + dx_ch4) / total_mass) * 1000.0
            max_com_shift = max(max_com_shift, abs(com_shift_mm))

            history.append(
                SloshTelemetryPoint(
                    time_s=round(t, 4),
                    altitude_m=round(alt, 2),
                    lox_phi_deg=round(math.degrees(lox_state.phi_rad), 2),
                    lox_submergence_m=round(lox_sub, 3),
                    lox_gas_ingestion=lox_ingested,
                    ch4_phi_deg=round(math.degrees(ch4_state.phi_rad), 2),
                    ch4_submergence_m=round(ch4_sub, 3),
                    ch4_gas_ingestion=ch4_ingested,
                    net_slosh_torque_nm=round(net_torque, 1),
                    com_shift_x_mm=round(com_shift_mm, 2),
                )
            )

            # RK4 Time Integration for LOX Tank:
            k1_v = phi_ddot_lox
            k1_x = lox_state.phi_dot_rad_s

            s2_lox = SloshState(lox_state.phi_rad + 0.5 * dt * k1_x, lox_state.phi_dot_rad_s + 0.5 * dt * k1_v)
            k2_v = self.lox_model.compute_acceleration(s2_lox, a_lat, a_ax, w_deg_s, vehicle_pitch_accel)
            k2_x = s2_lox.phi_dot_rad_s

            s3_lox = SloshState(lox_state.phi_rad + 0.5 * dt * k2_x, lox_state.phi_dot_rad_s + 0.5 * dt * k2_v)
            k3_v = self.lox_model.compute_acceleration(s3_lox, a_lat, a_ax, w_deg_s, vehicle_pitch_accel)
            k3_x = s3_lox.phi_dot_rad_s

            s4_lox = SloshState(lox_state.phi_rad + dt * k3_x, lox_state.phi_dot_rad_s + dt * k3_v)
            k4_v = self.lox_model.compute_acceleration(s4_lox, a_lat, a_ax, w_deg_s, vehicle_pitch_accel)
            k4_x = s4_lox.phi_dot_rad_s

            lox_state.phi_rad += (dt / 6.0) * (k1_x + 2 * k2_x + 2 * k3_x + k4_x)
            lox_state.phi_dot_rad_s += (dt / 6.0) * (k1_v + 2 * k2_v + 2 * k3_v + k4_v)

            # RK4 Time Integration for CH4 Tank:
            c1_v = phi_ddot_ch4
            c1_x = ch4_state.phi_dot_rad_s

            s2_ch4 = SloshState(ch4_state.phi_rad + 0.5 * dt * c1_x, ch4_state.phi_dot_rad_s + 0.5 * dt * c1_v)
            c2_v = self.ch4_model.compute_acceleration(s2_ch4, a_lat, a_ax, w_deg_s, vehicle_pitch_accel)
            c2_x = s2_ch4.phi_dot_rad_s

            s3_ch4 = SloshState(ch4_state.phi_rad + 0.5 * dt * c2_x, ch4_state.phi_dot_rad_s + 0.5 * dt * c2_v)
            c3_v = self.ch4_model.compute_acceleration(s3_ch4, a_lat, a_ax, w_deg_s, vehicle_pitch_accel)
            c3_x = s3_ch4.phi_dot_rad_s

            s4_ch4 = SloshState(ch4_state.phi_rad + dt * c3_x, ch4_state.phi_dot_rad_s + dt * c3_v)
            c4_v = self.ch4_model.compute_acceleration(s4_ch4, a_lat, a_ax, w_deg_s, vehicle_pitch_accel)
            c4_x = s4_ch4.phi_dot_rad_s

            ch4_state.phi_rad += (dt / 6.0) * (c1_x + 2 * c2_x + 2 * c3_x + c4_x)
            ch4_state.phi_dot_rad_s += (dt / 6.0) * (c1_v + 2 * c2_v + 2 * c3_v + c4_v)

        total_duration = history[-1].time_s - history[0].time_s if history else 0.0

        # Risk Classification:
        if lox_gas_time > 0.4 or ch4_gas_time > 0.4:
            risk = "CRITICAL_CAVITATION"
            msg = (
                f"Severe ullage gas ingestion detected: LOX suction uncovered for {lox_gas_time:.2f}s, "
                f"CH4 uncovered for {ch4_gas_time:.2f}s. Engine turbopump flameout probable."
            )
        elif lox_gas_time > 0.05 or ch4_gas_time > 0.05:
            risk = "WARNING"
            msg = (
                f"Transient suction uncover detected: LOX gas={lox_gas_time:.2f}s, "
                f"CH4 gas={ch4_gas_time:.2f}s. Baffle damping or flip profile smoothing advised."
            )
        else:
            risk = "SAFE"
            msg = (
                f"Suction submergence maintained across entire maneuver: "
                f"min LOX={lox_min_sub:.2f}m, min CH4={ch4_min_sub:.2f}m. Zero gas ingestion."
            )

        result = SloshSimulationResult(
            total_duration_s=round(total_duration, 2),
            lox_gas_ingestion_detected=lox_gas_time > 0.0,
            lox_total_gas_exposure_time_s=round(lox_gas_time, 3),
            lox_min_submergence_m=round(lox_min_sub, 3),
            ch4_gas_ingestion_detected=ch4_gas_time > 0.0,
            ch4_total_gas_exposure_time_s=round(ch4_gas_time, 3),
            ch4_min_submergence_m=round(ch4_min_sub, 3),
            max_slosh_torque_nm=round(max_torque, 1),
            max_com_shift_x_mm=round(max_com_shift, 2),
            risk_level=risk,
            summary_message=msg,
        )
        return result, history
