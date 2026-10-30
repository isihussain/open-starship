import unittest
import math
from starship_flip_gnc.models import StarshipVehicle, FlightState
from starship_flip_gnc.native_bridge import NativeFlightCoreBridge
from starship_flip_gnc.trajectory import TrajectoryOptimizer


class TestNativeBridge(unittest.TestCase):
    def setUp(self):
        self.bridge = NativeFlightCoreBridge()
        self.vehicle = StarshipVehicle()

    def test_native_core_compilation_and_execution(self):
        self.assertTrue(self.bridge.is_available, "Native C core should compile and load.")

        init_state = FlightState(x=0.0, z=500.0, vx=5.0, vz=-60.0, theta=math.pi / 2, omega=0.0)

        # Step with native C core:
        next_state = self.bridge.step_rk4(
            state=init_state,
            vehicle=self.vehicle,
            throttle=0.80,
            gimbal_rad=math.radians(5.0),
            active_engines=3,
            dt=0.02,
        )

        self.assertAlmostEqual(next_state.time, 0.02)
        self.assertLess(next_state.z, 500.0)
        self.assertLess(next_state.propellant_mass, init_state.propellant_mass)


if __name__ == "__main__":
    unittest.main()
