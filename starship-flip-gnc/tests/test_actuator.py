"""
Unit tests for TVC actuator dynamics, rate limiting, and mass depletion kinematics.
"""

import unittest
import math
from starship_flip_gnc.models import StarshipVehicle, TVCActuator, FlightState
from starship_flip_gnc.trajectory import TrajectoryOptimizer
from starship_flip_gnc.telemetry import TelemetryLogger


class TestTVCActuatorAndMassDepletion(unittest.TestCase):
    def test_actuator_slew_rate_limiting(self):
        """Verify actuator clamps rate of angle change to max_rate_rad_s."""
        max_rate_deg_s = 20.0
        actuator = TVCActuator(
            max_angle_rad=math.radians(15.0),
            max_rate_rad_s=math.radians(max_rate_deg_s),
            time_constant_s=0.01,  # fast response to isolate slew rate limiter
        )

        dt = 0.05
        # Large step command of +15 degrees
        actual = actuator.step(math.radians(15.0), dt=dt)
        actual_deg = math.degrees(actual)

        # In 0.05 s, at 20 deg/s max rate, maximum angle cannot exceed 1.0 deg
        self.assertLessEqual(actual_deg, 1.0001)
        self.assertGreater(actual_deg, 0.5)

    def test_actuator_hard_angle_limits(self):
        """Verify actuator never exceeds max_angle_rad regardless of command."""
        actuator = TVCActuator(max_angle_rad=math.radians(15.0))
        # Step for 5 seconds toward 45 degrees
        for _ in range(100):
            actuator.step(math.radians(45.0), dt=0.05)

        self.assertAlmostEqual(math.degrees(actuator.current_angle_rad), 15.0, places=4)

    def test_actuator_reset(self):
        """Verify actuator reset returns to specified deflection."""
        actuator = TVCActuator()
        actuator.step(math.radians(10.0), dt=1.0)
        self.assertGreater(actuator.current_angle_rad, 0.0)

        actuator.reset(0.0)
        self.assertEqual(actuator.current_angle_rad, 0.0)

    def test_dynamic_mass_depletion_and_inertia_monotonicity(self):
        """Verify total mass and moment of inertia strictly decrease as propellant is consumed."""
        vehicle = StarshipVehicle()

        mass_full = vehicle.compute_total_mass(25_000.0)
        mass_half = vehicle.compute_total_mass(12_500.0)
        mass_empty = vehicle.compute_total_mass(0.0)

        self.assertEqual(mass_full, 125_000.0)
        self.assertEqual(mass_half, 112_500.0)
        self.assertEqual(mass_empty, 100_000.0)

        i_full = vehicle.compute_moment_of_inertia_pitch(25_000.0)
        i_half = vehicle.compute_moment_of_inertia_pitch(12_500.0)
        i_empty = vehicle.compute_moment_of_inertia_pitch(0.0)

        self.assertGreater(i_full, i_half)
        self.assertGreater(i_half, i_empty)

        # Center of mass shifts aft as nose header propellant is consumed:
        com_full = vehicle.compute_center_of_mass_z(25_000.0)
        com_empty = vehicle.compute_center_of_mass_z(0.0)
        self.assertAlmostEqual(com_full, -5.0)
        self.assertLess(com_empty, com_full)

    def test_simulation_records_actuator_and_mass_telemetry(self):
        """Verify simulation records both commanded and actual gimbal angle plus propellant mass."""
        vehicle = StarshipVehicle()
        optimizer = TrajectoryOptimizer(vehicle=vehicle)
        logger = TelemetryLogger()

        initial_state = FlightState(z=450.0, vz=-65.0, theta=math.pi / 2, propellant_mass=25_000.0)
        result = optimizer.simulate(initial_state=initial_state, dt=0.02, logger=logger)

        self.assertTrue(result.success)
        self.assertGreater(len(logger.records), 50)

        first = logger.records[0]
        last = logger.records[-1]

        self.assertGreater(first.propellant_mass_kg, last.propellant_mass_kg)
        self.assertTrue(hasattr(first, "gimbal_cmd_deg"))
        self.assertTrue(hasattr(first, "propellant_mass_kg"))


if __name__ == "__main__":
    unittest.main()
