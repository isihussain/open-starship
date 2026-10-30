import unittest
import math
from starship_flip_gnc.models import StarshipVehicle, EngineCluster, FlightState


class TestModels(unittest.TestCase):
    def test_engine_cluster_defaults(self):
        engines = EngineCluster()
        self.assertEqual(engines.num_engines, 3)
        self.assertAlmostEqual(engines.max_thrust_total, 3 * 2.25e6)
        self.assertAlmostEqual(engines.min_thrust_total, 3 * 2.25e6 * 0.40)
        self.assertAlmostEqual(engines.max_gimbal_rad, math.radians(15.0))

    def test_vehicle_mass_and_inertia(self):
        vehicle = StarshipVehicle()
        self.assertAlmostEqual(vehicle.total_mass, 125_000.0)
        self.assertGreater(vehicle.moment_of_inertia_pitch, 0.0)
        self.assertAlmostEqual(vehicle.gimbal_moment_arm, 19.0)

    def test_flight_state_properties(self):
        state = FlightState(vx=30.0, vz=-40.0, theta=math.pi / 2, omega=0.1)
        self.assertAlmostEqual(state.speed, 50.0)
        self.assertAlmostEqual(state.pitch_deg, 90.0)
        self.assertAlmostEqual(state.omega_deg_s, math.degrees(0.1))


if __name__ == "__main__":
    unittest.main()
