"""
Equivalent mechanical pendulum slosh model for spherical propellant tanks.

Based on NASA SP-106 (Abramson/Dodge liquid propellant dynamics formulation).
Converts hydrodynamic fluid free-surface waves into an equivalent mechanical pendulum
coupled to vehicle translation and rotation.
"""

from dataclasses import dataclass
import math
from typing import Tuple

from .tank import HeaderTankGeometry, CryogenicFluid


@dataclass
class SloshState:
    """
    Instantaneous dynamic state of the sloshing propellant pendulum.
    """
    phi_rad: float = 0.0       # Pendulum deflection angle relative to tank centerline [rad]
    phi_dot_rad_s: float = 0.0 # Angular velocity of pendulum [rad/s]


class EquivalentSloshModel:
    """
    Mechanical pendulum representation of first-mode fluid sloshing.
    """

    def __init__(
        self,
        tank: HeaderTankGeometry,
        fluid: CryogenicFluid,
        initial_fluid_mass_kg: float,
    ):
        self.tank = tank
        self.fluid = fluid
        self.fluid_mass = initial_fluid_mass_kg

        # Calculate fill ratio and fluid volume:
        self.fluid_volume_m3 = self.fluid_mass / self.fluid.density_kg_m3
        self.fill_fraction = min(1.0, max(0.05, self.fluid_volume_m3 / self.tank.total_volume_m3))

        # Equivalent pendulum parameters (Abramson approximation for spherical tanks):
        # First slosh mass typically comprises 25% to 45% of total liquid mass
        r = self.tank.radius_m
        self.slosh_mass_ratio = 0.35 * math.tanh(2.16 * self.fill_fraction)
        self.m1 = self.fluid_mass * self.slosh_mass_ratio       # Sloshing active mass [kg]
        self.m0 = self.fluid_mass - self.m1                     # Fixed quiescent mass [kg]

        # Pendulum arm length:
        self.arm_length_lp = (r / 1.84) * math.tanh(1.84 * self.fill_fraction)
        self.arm_length_lp = max(0.15, min(r * 0.9, self.arm_length_lp))

        # Nominal fluid depth at rest:
        self.h_nominal = 2.0 * r * self.fill_fraction

    def compute_acceleration(
        self,
        state: SloshState,
        accel_lateral_mps2: float,
        accel_axial_mps2: float,
        vehicle_pitch_rate_deg_s: float,
        vehicle_pitch_accel_rad_s2: float = 0.0,
    ) -> float:
        """
        Computes angular acceleration d(phi_dot)/dt of the slosh pendulum.

        Governing differential equation:
          phi_ddot + 2 * zeta * omega_n * phi_dot + (g_eff / L_p) * sin(phi - phi_eq) = forcing
        """
        # Effective apparent gravity acting in vehicle body frame:
        # Note: accelerometer readings oppose gravity
        g_eff = math.hypot(accel_lateral_mps2, accel_axial_mps2)
        g_eff = max(0.1, g_eff)

        # Equilibrium free-surface tilt angle commanded by lateral acceleration:
        phi_eq = math.atan2(accel_lateral_mps2, max(0.01, accel_axial_mps2))

        # Slosh natural frequency:
        omega_n = math.sqrt(g_eff / self.arm_length_lp)

        # Hydrodynamic damping:
        zeta = self.tank.damping_ratio
        damping_term = 2.0 * zeta * omega_n * state.phi_dot_rad_s

        # Restoring gravity torque term:
        restoring_term = (g_eff / self.arm_length_lp) * math.sin(state.phi_rad - phi_eq)

        # Rotational coupling from vehicle angular acceleration:
        rot_coupling = vehicle_pitch_accel_rad_s2

        phi_ddot = -damping_term - restoring_term - rot_coupling
        return phi_ddot

    def evaluate_inlet_submergence(self, state: SloshState) -> Tuple[float, bool]:
        """
        Calculates liquid depth above the suction inlet and checks for gas ingestion.

        Returns:
            submergence_depth_m: Liquid depth above suction inlet [m].
            is_gas_ingested: True if depth is below threshold.
        """
        r = self.tank.radius_m
        # Inlet local position:
        z_inlet = self.tank.suction_inlet_z_local_m  # negative, e.g. -1.45m
        inlet_dist_from_bottom = r + z_inlet        # positive distance from bottom shell

        # When pendulum deflects by angle phi, liquid piles up on one side
        # and uncovers the opposite side. Surface drop delta_h at centerline:
        surface_deflection = r * abs(math.sin(state.phi_rad))
        submergence = max(0.0, self.h_nominal - inlet_dist_from_bottom - surface_deflection)

        is_ingested = submergence < self.tank.intake_submergence_threshold_m
        return submergence, is_ingested

    def compute_slosh_forces_and_torques(
        self,
        state: SloshState,
        phi_ddot: float,
        accel_lateral: float,
        accel_axial: float,
    ) -> Tuple[float, float, float]:
        """
        Computes dynamic slosh forces and pitching torque exerted on the vehicle structure.

        Returns:
            (force_lateral_n, force_axial_n, torque_pitch_nm)
        """
        sin_phi = math.sin(state.phi_rad)
        cos_phi = math.cos(state.phi_rad)

        # Slosh mass relative position vector:
        x_slosh = self.arm_length_lp * sin_phi
        z_slosh = -self.arm_length_lp * cos_phi

        # Slosh mass inertial forces:
        f_slosh_lat = self.m1 * (accel_lateral + self.arm_length_lp * phi_ddot * cos_phi)
        f_slosh_ax = self.m1 * accel_axial

        # Pitch disturbance torque about vehicle center of mass:
        # Distance from vehicle CoM to tank center is tank.z_position_vehicle_m
        arm_to_com = self.tank.z_position_vehicle_m
        torque_pitch = f_slosh_lat * arm_to_com

        return f_slosh_lat, f_slosh_ax, torque_pitch
