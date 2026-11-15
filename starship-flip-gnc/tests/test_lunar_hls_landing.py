import unittest
from starship_flip_gnc.lunar_hls_landing import (
    LunarHLSPlumeSolver,
    LunarLandingState,
    PlumeErosionReport,
    EjectaRiskAssessment,
)


class TestLunarHLSPlumeSolver(unittest.TestCase):
    def setUp(self):
        self.solver = LunarHLSPlumeSolver(
            landing_mass_kg=95000.0,
            nozzle_exit_radius_m=1.15,
            number_of_active_thrusters=4,
            max_total_thrust_n=800000.0,
        )

    def test_surface_shear_stress_scaling(self):
        thrust = 200000.0
        shear_high = self.solver.compute_surface_shear_stress(50.0, thrust)
        shear_low = self.solver.compute_surface_shear_stress(2.0, thrust)

        self.assertGreater(shear_low, shear_high)
        self.assertGreater(shear_low, 0.0)

    def test_regolith_critical_shear_threshold(self):
        self.assertEqual(self.solver.CRITICAL_SHEAR_PA, 0.08)

    def test_dust_optical_transmission(self):
        trans_clear = self.solver.evaluate_dust_optical_transmission(0.0, 10.0)
        trans_dusty = self.solver.evaluate_dust_optical_transmission(15.0, 10.0)

        self.assertEqual(trans_clear, 1.0)
        self.assertLess(trans_dusty, 0.80)
        self.assertGreaterEqual(trans_dusty, 0.01)

    def test_nominal_lunar_touchdown(self):
        states, erosion_rep, risk_rep = self.solver.run_terminal_landing(
            initial_altitude_m=50.0,
            initial_vertical_velocity_ms=-8.0,
            initial_horizontal_velocity_ms=2.0,
            target_touchdown_vz_ms=-1.0,
            dt=0.05,
        )

        self.assertGreater(len(states), 50)
        self.assertTrue(risk_rep.touchdown_stable)
        self.assertLessEqual(abs(risk_rep.touchdown_velocity_ms), 2.5)
        self.assertLessEqual(erosion_rep.final_crater_depth_m, 0.35)
        self.assertIn(risk_rep.final_trn_mode, ["NOMINAL_OPTICAL_TRN", "DEGRADED_IMU_DEAD_RECKONING"])

    def test_cratering_and_mass_erosion(self):
        states, erosion_rep, risk_rep = self.solver.run_terminal_landing(
            initial_altitude_m=30.0,
            initial_vertical_velocity_ms=-5.0,
            initial_horizontal_velocity_ms=0.5,
            dt=0.05,
        )

        self.assertTrue(erosion_rep.erosion_active)
        self.assertGreater(erosion_rep.total_eroded_mass_kg, 1.0)
        self.assertGreater(erosion_rep.peak_shear_stress_pa, self.solver.CRITICAL_SHEAR_PA)

    def test_ejecta_risk_assessment(self):
        states, erosion_rep, risk_rep = self.solver.run_terminal_landing(
            initial_altitude_m=40.0,
            initial_vertical_velocity_ms=-6.0,
            initial_horizontal_velocity_ms=1.0,
            dt=0.05,
        )

        self.assertIn(risk_rep.landing_gear_abrasion_risk, ["LOW", "MODERATE", "CRITICAL"])
        self.assertGreater(risk_rep.peak_particle_velocity_ms, 0.0)
        self.assertGreater(risk_rep.peak_kinetic_energy_j, 0.0)

    def test_high_altitude_minimal_erosion(self):
        shear_at_100m = self.solver.compute_surface_shear_stress(100.0, 150000.0)
        self.assertLess(shear_at_100m, 0.05)


if __name__ == "__main__":
    unittest.main()
