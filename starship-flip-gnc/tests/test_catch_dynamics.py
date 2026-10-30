import unittest
from starship_flip_gnc.catch_dynamics import CatchEnvelope, MechazillaCatchSolver


class TestCatchDynamics(unittest.TestCase):
    def setUp(self):
        self.solver = MechazillaCatchSolver()

    def test_nominal_catch_success(self):
        res = self.solver.evaluate_capture(
            x_m=0.15,
            z_m=45.10,
            vx_mps=0.05,
            vz_mps=-0.25,
            pitch_deg=0.4,
            vehicle_mass_kg=115_000.0,
        )
        self.assertTrue(res.caught)
        self.assertLess(res.lateral_error_m, 0.5)
        self.assertLess(res.vertical_error_m, 0.35)
        self.assertIn("successful", res.message)

    def test_excessive_lateral_drift_abort(self):
        res = self.solver.evaluate_capture(
            x_m=1.80,  # 1.8m off-center > 0.5m limit
            z_m=45.0,
            vx_mps=0.0,
            vz_mps=-0.20,
            pitch_deg=0.0,
            vehicle_mass_kg=115_000.0,
        )
        self.assertFalse(res.caught)
        self.assertIn("lateral offset", res.message)

    def test_excessive_descent_velocity_abort(self):
        res = self.solver.evaluate_capture(
            x_m=0.0,
            z_m=45.0,
            vx_mps=0.0,
            vz_mps=-1.80,  # -1.8 m/s > 0.4 m/s limit
            pitch_deg=0.0,
            vehicle_mass_kg=115_000.0,
        )
        self.assertFalse(res.caught)
        self.assertIn("descent rate", res.message)


if __name__ == "__main__":
    unittest.main()
