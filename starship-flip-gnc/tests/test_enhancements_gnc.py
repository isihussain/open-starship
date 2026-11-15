"""
Unit tests for Starship GNC enhancements:
  - StandardAtmosphere1976 (USSA76)
  - RadiativeEquilibriumThermalModel
  - DrydenTurbulenceModel
  - Variable mass & principal inertia tensor
  - Quaternion attitude representation & error kinematics
  - Gain-scheduled bandwidth controller
  - Dynamic tip-over stability validator
  - 3D spherical cone gimbal limiting & cosine loss
  - Minimum-norm pseudoinverse control allocation
  - Hydro-pneumatic chopstick pin impact dynamics
  - Telemetry HMAC-SHA256 cryptographic signing
"""

import unittest
import math

from starship_flip_gnc.aerodynamics import (
    StandardAtmosphere1976,
    RadiativeEquilibriumThermalModel,
    DrydenTurbulenceModel,
)
from starship_flip_gnc.models import StarshipVehicle
from starship_flip_gnc.quaternion_attitude import Quaternion, AttitudeKinematics
from starship_flip_gnc.trajectory import TrajectoryOptimizer
from starship_flip_gnc.touchdown_gate import TouchdownValidationGate
from starship_flip_gnc.engine_out_recovery import EngineOutCompensator, EngineTelemetry, VehicleState
from starship_flip_gnc.actuator_fault_allocator import ActuatorFaultAllocator, ActuatorTelemetry, TorqueDemand
from starship_flip_gnc.catch_dynamics import MechazillaCatchSolver
from starship_flip_gnc.telemetry import TelemetryIntegritySigner


class TestGNCEnhancements(unittest.TestCase):
    def test_ussa76_atmosphere_layers(self):
        ussa = StandardAtmosphere1976()
        sea_level = ussa.evaluate(0.0)
        self.assertAlmostEqual(sea_level.temperature_k, 288.15, places=1)
        self.assertAlmostEqual(sea_level.pressure_pa, 101325.0, places=0)
        self.assertAlmostEqual(sea_level.density_kg_m3, 1.225, places=2)
        self.assertGreater(sea_level.speed_of_sound_mps, 340.0)

        tropopause = ussa.evaluate(15000.0)
        self.assertAlmostEqual(tropopause.temperature_k, 216.65, places=1)
        self.assertLess(tropopause.density_kg_m3, sea_level.density_kg_m3 * 0.25)

    def test_radiative_equilibrium_surface_temperature(self):
        model = RadiativeEquilibriumThermalModel(surface_emissivity=0.88)
        # Cold ambient:
        self.assertEqual(model.compute_surface_temperature_k(0.0), 288.15)
        # Peak convective heating: 250 kW/m^2
        t_peak = model.compute_surface_temperature_k(250_000.0)
        # Should be between 1400 K and 1600 K
        self.assertGreater(t_peak, 1400.0)
        self.assertLess(t_peak, 1600.0)

    def test_dryden_turbulence_intensity(self):
        turb = DrydenTurbulenceModel(severity_intensity="MODERATE", wind_speed_at_20ft_mps=15.0)
        lu, lw, sigma_u = turb.compute_turbulence_intensity(altitude_m=50.0)
        self.assertEqual(lw, 50.0)
        self.assertGreater(lu, lw)
        self.assertGreater(sigma_u, 0.0)

    def test_variable_mass_full_inertia_tensor(self):
        vehicle = StarshipVehicle()
        i_full = vehicle.compute_full_inertia_tensor(propellant_mass=25_000.0)
        i_empty = vehicle.compute_full_inertia_tensor(propellant_mass=0.0)
        # Pitch inertia with full landing propellant exceeds dry empty inertia:
        self.assertGreater(i_full[0], i_empty[0])
        # Axisymmetric cylinder: I_pitch == I_yaw:
        self.assertEqual(i_full[0], i_full[1])
        # Roll inertia is much lower than pitch inertia:
        self.assertLess(i_full[2], i_full[0] * 0.1)

    def test_quaternion_multiplication_and_error(self):
        q1 = Quaternion.from_euler_pitch(math.radians(30.0))
        q2 = Quaternion.from_euler_pitch(math.radians(60.0))
        q_prod = q1.multiply(q2)
        roll, pitch, yaw = q_prod.to_euler_angles_deg()
        self.assertAlmostEqual(pitch, 90.0, places=1)
        self.assertAlmostEqual(roll, 0.0, places=1)

        err_roll, err_pitch, err_yaw = AttitudeKinematics.compute_attitude_error(q1, q2)
        self.assertAlmostEqual(err_pitch, math.radians(-30.0), places=3)

    def test_gain_scheduled_bandwidth_controller(self):
        optimizer = TrajectoryOptimizer()
        kp_high, kd_high = optimizer.compute_scheduled_gains(altitude_m=500.0)
        kp_touchdown, kd_touchdown = optimizer.compute_scheduled_gains(altitude_m=2.0)
        # Gains tighten as ground approaches:
        self.assertGreater(kp_touchdown, kp_high)
        self.assertGreater(kd_touchdown, kd_high)

    def test_touchdown_tipover_stability_validator(self):
        gate = TouchdownValidationGate()
        # Nominal upright touchdown (1 deg tilt, zero lateral drift):
        stable, eff_tilt, msg = gate.validate_tipover_stability(pitch_deg=1.0, horizontal_velocity_mps=0.1)
        self.assertTrue(stable)
        self.assertIn("verified", msg)

        # Extreme tilt and high lateral drift (15 deg tilt, 3.5 m/s drift):
        unstable, eff_tilt_bad, msg_bad = gate.validate_tipover_stability(pitch_deg=12.0, horizontal_velocity_mps=4.0)
        self.assertFalse(unstable)
        self.assertIn("HAZARD", msg_bad)

    def test_3d_spherical_cone_gimbal_limiter(self):
        comp = EngineOutCompensator()
        v_state = VehicleState(
            mass_kg=110_000.0,
            gimbal_to_com_distance_m=12.0,
            max_gimbal_limit_rad=math.radians(12.0),
        )
        engines = [
            EngineTelemetry("eng1", 0.0, 0.0, 220.0, 2.0e6, 2.0e6),
            EngineTelemetry("eng2", -3.2, 0.0, 220.0, 2.0e6, 2.0e6),
        ]
        plan = comp.evaluate(engines, v_state, target_delta_v_mps=30.0, nominal_burn_duration_s=8.0)
        self.assertIsNotNone(plan)
        self.assertGreater(plan.thrust_to_weight_ratio, 0.0)

    def test_minimum_norm_control_allocator(self):
        alloc = ActuatorFaultAllocator()
        actuators = [
            ActuatorTelemetry("aft_port", 0.0, 0.0, 15.0),
            ActuatorTelemetry("aft_starboard", 0.0, 0.0, 15.0),
            ActuatorTelemetry("fwd_port", 0.0, 0.0, 10.0),
            ActuatorTelemetry("fwd_starboard", 0.0, 0.0, 10.0),
        ]
        demand = TorqueDemand(pitch_nm=15_000.0, yaw_nm=0.0, roll_nm=5_000.0)
        result = alloc.allocate(demand, q_dyn_pa=10_000.0, actuators=actuators)
        self.assertIsNotNone(result)
        self.assertIn("aft_port", result.surface_commands_rad)

    def test_hydro_pneumatic_pin_dynamics(self):
        solver = MechazillaCatchSolver()
        disp, peak_f, energy = solver.compute_hydro_pneumatic_pin_response(
            vehicle_mass_kg=115_000.0,
            vz_mps=-0.35,
        )
        self.assertGreater(disp, 0.05)
        self.assertGreater(peak_f, 1.0e6)
        self.assertGreater(energy, 0.0)

    def test_telemetry_hmac_sha256_signer(self):
        secret = "starbase_avionics_secret_key_2026"
        record = {"time_s": 12.5, "altitude_m": 42.1, "vz_mps": -2.3}
        sig = TelemetryIntegritySigner.sign_record(record, secret)
        self.assertTrue(TelemetryIntegritySigner.verify_record(record, sig, secret))

        # Tampered record:
        tampered = {"time_s": 12.5, "altitude_m": 42.1, "vz_mps": -99.9}
        self.assertFalse(TelemetryIntegritySigner.verify_record(tampered, sig, secret))


if __name__ == "__main__":
    unittest.main()
