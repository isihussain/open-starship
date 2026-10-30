"""
Trajectory simulation and guidance solver for Starship flip-and-burn maneuver.

Implements a 3-DoF coupled translational-rotational flight dynamic model,
quartic Runge-Kutta numerical integration, and closed-loop thrust-vectoring guidance.
"""

from dataclasses import dataclass
import math
from typing import Optional, List, Tuple

from .models import StarshipVehicle, FlightState
from .aerodynamics import AerodynamicModel, Atmosphere
from .telemetry import TelemetryRecord, TelemetryLogger


@dataclass
class SimulationResult:
    """
    Simulation termination outcome and performance metrics.
    """
    success: bool
    touchdown_time_s: float
    final_altitude_m: float
    final_velocity_z_mps: float
    final_velocity_x_mps: float
    final_pitch_deg: float
    propellant_used_kg: float
    propellant_remaining_kg: float
    max_lateral_accel_g: float
    max_axial_accel_g: float
    max_heat_flux_w_m2: float
    message: str


class TrajectoryOptimizer:
    """
    Solves and simulates the Starship landing flip maneuver from belly-flop
    to vertical touchdown.
    """

    def __init__(
        self,
        vehicle: Optional[StarshipVehicle] = None,
        atmosphere: Optional[Atmosphere] = None,
        aero_model: Optional[AerodynamicModel] = None,
    ):
        self.vehicle = vehicle or StarshipVehicle()
        self.atmosphere = atmosphere or Atmosphere()
        self.aero_model = aero_model or AerodynamicModel(
            vehicle_length=self.vehicle.length,
            vehicle_diameter=self.vehicle.diameter,
        )

        # Control gains for pitch orientation:
        self.kp_pitch = 2.4
        self.kd_pitch = 1.6

        # Terminal deceleration limit for touchdown throttle scheduling:
        self.target_touchdown_accel = 14.5  # m/s^2 (~1.48 g)

    def _compute_derivatives(
        self,
        state: FlightState,
        throttle: float,
        gimbal_rad: float,
        active_engines: int = 3,
    ) -> Tuple[float, float, float, float, float, float, float]:
        """
        Computes 3-DoF state derivatives (dx/dt, dz/dt, dvx/dt, dvz/dt, dtheta/dt, domega/dt, dprop/dt).
        """
        # Clamp inputs:
        th = max(0.0, min(1.0, throttle))
        clamped_gimbal = max(
            -self.vehicle.engines.max_gimbal_rad,
            min(self.vehicle.engines.max_gimbal_rad, gimbal_rad)
        )

        curr_mass = self.vehicle.dry_mass + state.propellant_mass
        f_thrust = th * active_engines * self.vehicle.engines.max_thrust_per_engine

        # Aerodynamic forces:
        aero = self.aero_model.compute_forces(
            vx=state.vx,
            vz=state.vz,
            theta=state.theta,
            altitude=state.z,
            atmosphere=self.atmosphere,
        )

        # Thrust vector components in global inertial frame:
        # Body vector points at angle theta. Engine thrust vector angle is (theta - gimbal).
        thrust_angle = state.theta - clamped_gimbal
        f_thrust_x = f_thrust * math.sin(thrust_angle)
        f_thrust_z = f_thrust * math.cos(thrust_angle)

        # Gravitational force (downward -Z):
        f_grav_z = -curr_mass * self.atmosphere.gravitational_accel

        # Net forces:
        f_net_x = f_thrust_x + aero["fx_aero"]
        f_net_z = f_thrust_z + aero["fz_aero"] + f_grav_z

        ax = f_net_x / curr_mass
        az = f_net_z / curr_mass

        # Rotational dynamics:
        # Thrust gimbal creates pitching moment about center of mass:
        moment_thrust = -f_thrust * math.sin(clamped_gimbal) * self.vehicle.gimbal_moment_arm

        # Aerodynamic rotational damping:
        q_dyn = aero["dynamic_pressure"]
        moment_aero_damping = -0.15 * q_dyn * self.aero_model.area_broadside * self.vehicle.length * state.omega

        moment_net = moment_thrust + moment_aero_damping
        i_yy = self.vehicle.moment_of_inertia_pitch
        alpha_ang = moment_net / i_yy

        # Propellant mass burn rate:
        # m_dot = F_thrust / (Isp * g0)
        g0 = self.atmosphere.gravitational_accel
        isp = self.vehicle.engines.isp_sea_level
        m_dot = -(f_thrust / (isp * g0)) if (f_thrust > 0 and state.propellant_mass > 0) else 0.0

        return state.vx, state.vz, ax, az, state.omega, alpha_ang, m_dot

    def simulate(
        self,
        initial_state: Optional[FlightState] = None,
        dt: float = 0.02,
        max_duration_s: float = 40.0,
        logger: Optional[TelemetryLogger] = None,
    ) -> SimulationResult:
        """
        Executes forward integration of the flip-and-burn descent.
        """
        state = initial_state or FlightState()
        init_prop = state.propellant_mass
        t = 0.0

        max_lat_accel = 0.0
        max_ax_accel = 0.0
        max_heat_flux = 0.0

        while t < max_duration_s and state.z > 0.3:
            # 1. Guidance Law: Phase-based trajectory tracking
            # Phase 1: Dynamic flip rotation (0.0s to 2.2s)
            # 3 engines ignite for maximum gimbal torque authority to swing vehicle vertical
            if t < 2.2:
                active_engines = 3
                flip_progress = t / 2.2
                target_pitch = math.radians(90.0 - 80.0 * flip_progress)
                target_throttle = 0.80
            # Phase 2: High-g deceleration burn (2 engines active)
            # Decelerates descent velocity from ~-60 m/s down to ~-12 m/s
            elif state.vz < -14.0:
                active_engines = 2
                drift_bias = math.radians(max(-5.0, min(5.0, -0.6 * state.vx)))
                target_pitch = drift_bias
                v_target = -14.0
                vel_error = state.vz - v_target
                target_throttle = max(0.40, min(1.0, 0.75 - 0.03 * vel_error))
            # Phase 3: Single-engine precision terminal landing burn
            # 1 engine throttles between 40% and 100% around hover (~50%) to softly touch down
            else:
                active_engines = 1
                drift_bias = math.radians(max(-3.0, min(3.0, -0.5 * state.vx)))
                target_pitch = drift_bias

                # Smooth velocity glide slope into ground:
                if state.z > 20.0:
                    v_target = -math.sqrt(2.0 * max(0.5, 6.0 * (state.z - 2.0)))
                else:
                    v_target = -max(0.8, min(2.0, 1.2 * (state.z / 10.0) + 0.6))

                vel_error = state.vz - v_target
                curr_mass = self.vehicle.dry_mass + state.propellant_mass
                hover_th_1eng = (curr_mass * self.atmosphere.gravitational_accel) / self.vehicle.engines.max_thrust_per_engine
                target_throttle = max(0.40, min(1.0, hover_th_1eng - 0.08 * vel_error))

            # Pitch Gimbal Controller (PD):
            pitch_error = state.theta - target_pitch
            gimbal_cmd = self.kp_pitch * pitch_error + self.kd_pitch * state.omega
            gimbal_cmd = max(
                -self.vehicle.engines.max_gimbal_rad,
                min(self.vehicle.engines.max_gimbal_rad, gimbal_cmd)
            )

            # Check fuel exhaustion:
            if state.propellant_mass <= 0.0:
                target_throttle = 0.0
                state.propellant_mass = 0.0

            # 2. Compute telemetry snapshot:
            derivatives = self._compute_derivatives(state, target_throttle, gimbal_cmd, active_engines=active_engines)
            _, _, ax_curr, az_curr, _, _, _ = derivatives

            # Accelerations in vehicle body axes:
            cos_th = math.cos(state.theta)
            sin_th = math.sin(state.theta)
            accel_axial = ax_curr * sin_th + az_curr * cos_th
            accel_lat = ax_curr * cos_th - az_curr * sin_th

            g0 = self.atmosphere.gravitational_accel
            max_lat_accel = max(max_lat_accel, abs(accel_lat) / g0)
            max_ax_accel = max(max_ax_accel, abs(accel_axial) / g0)

            aero_info = self.aero_model.compute_forces(
                vx=state.vx,
                vz=state.vz,
                theta=state.theta,
                altitude=state.z,
                atmosphere=self.atmosphere,
            )
            heat_flux = aero_info["heat_flux_w_m2"]
            max_heat_flux = max(max_heat_flux, heat_flux)

            if logger is not None:
                total_m = self.vehicle.dry_mass + state.propellant_mass
                logger.log(
                    TelemetryRecord(
                        time_s=round(t, 4),
                        altitude_m=round(state.z, 3),
                        downrange_m=round(state.x, 3),
                        velocity_x_mps=round(state.vx, 3),
                        velocity_z_mps=round(state.vz, 3),
                        speed_mps=round(state.speed, 3),
                        pitch_deg=round(state.pitch_deg, 3),
                        pitch_rate_deg_s=round(state.omega_deg_s, 3),
                        throttle=round(target_throttle, 3),
                        gimbal_deg=round(math.degrees(gimbal_cmd), 3),
                        thrust_n=round(target_throttle * active_engines * self.vehicle.engines.max_thrust_per_engine, 1),
                        drag_n=round(aero_info["drag"], 1),
                        lift_n=round(aero_info["lift"], 1),
                        dynamic_pressure_pa=round(aero_info["dynamic_pressure"], 1),
                        heat_flux_w_m2=round(heat_flux, 1),
                        total_mass_kg=round(total_m, 1),
                        accel_lateral_mps2=round(accel_lat, 3),
                        accel_axial_mps2=round(accel_axial, 3),
                    )
                )

            # 3. 4th-Order Runge-Kutta (RK4) Integration:
            # k1
            k1_x, k1_z, k1_vx, k1_vz, k1_th, k1_om, k1_m = derivatives

            # k2
            s2 = FlightState(
                time=t + 0.5 * dt,
                x=state.x + 0.5 * dt * k1_x,
                z=state.z + 0.5 * dt * k1_z,
                vx=state.vx + 0.5 * dt * k1_vx,
                vz=state.vz + 0.5 * dt * k1_vz,
                theta=state.theta + 0.5 * dt * k1_th,
                omega=state.omega + 0.5 * dt * k1_om,
                propellant_mass=max(0.0, state.propellant_mass + 0.5 * dt * k1_m),
            )
            k2_x, k2_z, k2_vx, k2_vz, k2_th, k2_om, k2_m = self._compute_derivatives(
                s2, target_throttle, gimbal_cmd, active_engines=active_engines
            )

            # k3
            s3 = FlightState(
                time=t + 0.5 * dt,
                x=state.x + 0.5 * dt * k2_x,
                z=state.z + 0.5 * dt * k2_z,
                vx=state.vx + 0.5 * dt * k2_vx,
                vz=state.vz + 0.5 * dt * k2_vz,
                theta=state.theta + 0.5 * dt * k2_th,
                omega=state.omega + 0.5 * dt * k2_om,
                propellant_mass=max(0.0, state.propellant_mass + 0.5 * dt * k2_m),
            )
            k3_x, k3_z, k3_vx, k3_vz, k3_th, k3_om, k3_m = self._compute_derivatives(
                s3, target_throttle, gimbal_cmd, active_engines=active_engines
            )

            # k4
            s4 = FlightState(
                time=t + dt,
                x=state.x + dt * k3_x,
                z=state.z + dt * k3_z,
                vx=state.vx + dt * k3_vx,
                vz=state.vz + dt * k3_vz,
                theta=state.theta + dt * k3_th,
                omega=state.omega + dt * k3_om,
                propellant_mass=max(0.0, state.propellant_mass + dt * k3_m),
            )
            k4_x, k4_z, k4_vx, k4_vz, k4_th, k4_om, k4_m = self._compute_derivatives(
                s4, target_throttle, gimbal_cmd, active_engines=active_engines
            )

            # State update:
            state.x += (dt / 6.0) * (k1_x + 2 * k2_x + 2 * k3_x + k4_x)
            state.z += (dt / 6.0) * (k1_z + 2 * k2_z + 2 * k3_z + k4_z)
            state.vx += (dt / 6.0) * (k1_vx + 2 * k2_vx + 2 * k3_vx + k4_vx)
            state.vz += (dt / 6.0) * (k1_vz + 2 * k2_vz + 2 * k3_vz + k4_vz)
            state.theta += (dt / 6.0) * (k1_th + 2 * k2_th + 2 * k3_th + k4_th)
            state.omega += (dt / 6.0) * (k1_om + 2 * k2_om + 2 * k3_om + k4_om)
            state.propellant_mass = max(
                0.0,
                state.propellant_mass + (dt / 6.0) * (k1_m + 2 * k2_m + 2 * k3_m + k4_m)
            )

            t += dt

        # Evaluation criteria:
        vz_ok = abs(state.vz) <= 2.5
        pitch_ok = abs(state.pitch_deg) <= 5.0
        success = (state.z <= 0.5) and vz_ok and pitch_ok

        prop_used = init_prop - state.propellant_mass
        msg = "Touchdown achieved inside operational margins." if success else (
            f"Descent out of bounds: alt={state.z:.1f}m, vz={state.vz:.1f}m/s, pitch={state.pitch_deg:.1f}deg"
        )

        return SimulationResult(
            success=success,
            touchdown_time_s=round(t, 2),
            final_altitude_m=round(max(0.0, state.z), 2),
            final_velocity_z_mps=round(state.vz, 2),
            final_velocity_x_mps=round(state.vx, 2),
            final_pitch_deg=round(state.pitch_deg, 2),
            propellant_used_kg=round(prop_used, 1),
            propellant_remaining_kg=round(state.propellant_mass, 1),
            max_lateral_accel_g=round(max_lat_accel, 2),
            max_axial_accel_g=round(max_ax_accel, 2),
            max_heat_flux_w_m2=round(max_heat_flux, 1),
            message=msg,
        )
