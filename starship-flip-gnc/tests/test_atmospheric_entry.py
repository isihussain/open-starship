import unittest
import math
from starship_flip_gnc.atmospheric_entry import (
    AtmosphericEntrySolver,
    EntryCorridorLimits,
    EntryState,
    EntryTrajectoryProfile,
)


class TestAtmosphericEntry(unittest.TestCase):
    def setUp(self):
        self.solver = AtmosphericEntrySolver(
            vehicle_mass_kg=120000.0,
            reference_area_m2=125.0,
            nose_radius_m=5.0,
            lift_coefficient=0.60,
            drag_coefficient=1.20,
        )

    def test_atmospheric_density_profile(self):
        rho_sl = self.solver.get_atmospheric_density(0.0)
        rho_20k = self.solver.get_atmospheric_density(20000.0)
        rho_60k = self.solver.get_atmospheric_density(60000.0)
        rho_space = self.solver.get_atmospheric_density(140000.0)

        self.assertAlmostEqual(rho_sl, 1.225, delta=0.01)
        self.assertGreater(rho_sl, rho_20k)
        self.assertGreater(rho_20k, rho_60k)
        self.assertEqual(rho_space, 0.0)

    def test_stagnation_heat_flux_sutton_graves(self):
        q_dot_hypersonic = self.solver.calculate_stagnation_heat_flux(60000.0, 7200.0)
        self.assertGreater(q_dot_hypersonic, 100000.0)  # Over 100 kW/m^2

        q_dot_vacuum = self.solver.calculate_stagnation_heat_flux(150000.0, 7500.0)
        self.assertEqual(q_dot_vacuum, 0.0)

        q_dot_stationary = self.solver.calculate_stagnation_heat_flux(0.0, 0.0)
        self.assertEqual(q_dot_stationary, 0.0)

    def test_plasma_blackout_cutoff(self):
        f_p_hypersonic, blackout_hypersonic = self.solver.calculate_plasma_cutoff_frequency(65000.0, 7500.0)
        self.assertGreater(f_p_hypersonic, 2.0e9)  # Above 2 GHz
        self.assertTrue(blackout_hypersonic)

        f_p_subsonic, blackout_subsonic = self.solver.calculate_plasma_cutoff_frequency(10000.0, 300.0)
        self.assertEqual(f_p_subsonic, 0.0)
        self.assertFalse(blackout_subsonic)

    def test_corridor_entry_validation(self):
        nominal_angle = math.radians(-1.45)
        valid, msg = self.solver.check_corridor_entry(nominal_angle)
        self.assertTrue(valid)
        self.assertEqual(msg, "NOMINAL_ENTRY_CORRIDOR")

        shallow_angle = math.radians(-0.80)  # Too shallow -> skip-out
        valid_shallow, msg_shallow = self.solver.check_corridor_entry(shallow_angle)
        self.assertFalse(valid_shallow)
        self.assertIn("OVERSHOOT", msg_shallow)

        steep_angle = math.radians(-2.50)  # Too steep -> high g-load
        valid_steep, msg_steep = self.solver.check_corridor_entry(steep_angle)
        self.assertFalse(valid_steep)
        self.assertIn("UNDERSHOOT", msg_steep)

    def test_nominal_entry_trajectory_propagation(self):
        profile = self.solver.propagate_entry(
            entry_altitude_m=120000.0,
            entry_velocity_ms=7500.0,
            entry_gamma_rad=math.radians(-1.45),
            bank_angle_schedule_rad=math.radians(35.0),
            dt=1.0,
            max_time_s=1200.0,
            target_handover_altitude_m=15000.0,
        )

        self.assertTrue(profile.success)
        self.assertEqual(profile.outcome, "SUCCESS_SUBSONIC_HANDOVER")
        self.assertLessEqual(profile.terminal_altitude_m, 16000.0)
        self.assertGreater(profile.peak_heat_flux_w_m2, 100000.0)
        self.assertLess(profile.peak_g_load, 4.5)  # Within structural limit
        self.assertGreater(profile.total_heat_load_j_m2, 1e7)
        self.assertGreater(profile.blackout_duration_s, 50.0)
        self.assertGreater(len(profile.states), 100)

    def test_skip_out_trajectory(self):
        profile = self.solver.propagate_entry(
            entry_altitude_m=120000.0,
            entry_velocity_ms=7800.0,
            entry_gamma_rad=math.radians(0.10),  # Positive flight path angle -> direct skip out
            bank_angle_schedule_rad=0.0,
            dt=1.0,
            max_time_s=300.0,
            target_handover_altitude_m=15000.0,
        )
        self.assertFalse(profile.success)
        self.assertEqual(profile.outcome, "ATMOSPHERIC_SKIP_OUT")

    def test_custom_corridor_load_limits(self):
        strict_limits = EntryCorridorLimits(max_load_factor_g=1.2)
        strict_solver = AtmosphericEntrySolver(corridor_limits=strict_limits)

        profile = strict_solver.propagate_entry(
            entry_altitude_m=120000.0,
            entry_velocity_ms=7500.0,
            entry_gamma_rad=math.radians(-1.50),
            bank_angle_schedule_rad=0.0,
            dt=1.0,
            max_time_s=600.0,
            target_handover_altitude_m=15000.0,
        )
        self.assertFalse(profile.success)
        self.assertEqual(profile.outcome, "STRUCTURAL_LOAD_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
