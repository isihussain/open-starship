import unittest
import math
from starship_flip_gnc.models import StarshipVehicle, FlightState
from starship_flip_gnc.trajectory import TrajectoryOptimizer
from starship_flip_gnc.telemetry import TelemetryLogger


class TestTrajectory(unittest.TestCase):
    def test_simulation_run_and_touchdown(self):
        vehicle = StarshipVehicle()
        optimizer = TrajectoryOptimizer(vehicle=vehicle)
        logger = TelemetryLogger()

        initial_state = FlightState(z=450.0, vz=-65.0, theta=math.pi / 2)
        result = optimizer.simulate(initial_state=initial_state, dt=0.02, logger=logger)

        # Simulation must finish with altitude near ground level and reasonable descent velocity
        self.assertLessEqual(result.final_altitude_m, 1.0)
        self.assertLess(abs(result.final_velocity_z_mps), 3.0)
        self.assertLess(abs(result.final_pitch_deg), 6.0)
        self.assertGreater(result.propellant_used_kg, 0.0)
        self.assertGreater(len(logger.records), 100)


if __name__ == "__main__":
    unittest.main()
