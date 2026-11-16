import unittest
import math
from starship_flip_gnc.mars_entry_aerocapture import (
    MarsAtmosphere,
    MarsEntryCorridor,
    MarsEntryState,
    SRPHandoverCriteria,
    MarsTrajectoryProfile,
    MarsEntryAerocaptureSolver,
)


class TestMarsEntryAerocapture(unittest.TestCase):
    def setUp(self):
        self.atmo = MarsAtmosphere()
        self.solver = MarsEntryAerocaptureSolver()

    def test_mars_atmospheric_density_and_sound_speed(self):
        rho_surf = self.atmo.density(0.0)
        rho_30k = self.atmo.density(30000.0)
        rho_space = self.atmo.density(150000.0)

        self.assertAlmostEqual(rho_surf, 0.020, delta=0.002)
        self.assertGreater(rho_surf, rho_30k)
        self.assertEqual(rho_space, 0.0)

        speed_sound = self.atmo.speed_of_sound(0.0)
        self.assertGreater(speed_sound, 210.0)
        self.assertLess(speed_sound, 240.0)

    def test_mars_entry_corridor_validation(self):
        nominal_gamma = math.radians(-14.2)
        valid, msg = self.solver.check_corridor(nominal_gamma)
        self.assertTrue(valid)
        self.assertEqual(msg, "NOMINAL_MARS_ENTRY_CORRIDOR")

        shallow_gamma = math.radians(-9.0)  # Too shallow -> skip-out
        valid_shallow, msg_shallow = self.solver.check_corridor(shallow_gamma)
        self.assertFalse(valid_shallow)
        self.assertIn("OVERSHOOT", msg_shallow)

        steep_gamma = math.radians(-19.0)  # Too steep -> high g-load
        valid_steep, msg_steep = self.solver.check_corridor(steep_gamma)
        self.assertFalse(valid_steep)
        self.assertIn("UNDERSHOOT", msg_steep)

    def test_co2_shock_layer_heating(self):
        q_conv = self.solver.calculate_convective_heat_flux(0.005, 6500.0)
        self.assertGreater(q_conv, 100000.0)  # > 100 kW/m^2

        q_rad = self.solver.calculate_radiative_heat_flux(0.005, 6500.0)
        self.assertGreater(q_rad, 0.0)

        q_conv_vacuum = self.solver.calculate_convective_heat_flux(0.0, 7000.0)
        self.assertEqual(q_conv_vacuum, 0.0)

    def test_srp_handover_criteria(self):
        # Valid conditions: alt = 3500m, Mach = 1.8, dynamic pressure = 1200 Pa
        valid, msg = self.solver.evaluate_srp_handover(3500.0, 1.8, 1200.0, srp_thrust_n=1800000.0)
        self.assertTrue(valid)
        self.assertEqual(msg, "SRP_HANDOVER_PERMITTED")

        # Invalid altitude
        invalid_alt, _ = self.solver.evaluate_srp_handover(9500.0, 1.8, 1200.0)
        self.assertFalse(invalid_alt)

        # Invalid Mach
        invalid_mach, _ = self.solver.evaluate_srp_handover(3500.0, 6.5, 1200.0)
        self.assertFalse(invalid_mach)

    def test_mars_nominal_entry_trajectory(self):
        profile = self.solver.propagate_mars_entry(
            entry_altitude_m=125000.0,
            entry_velocity_ms=7200.0,
            entry_gamma_rad=math.radians(-12.5),
            bank_angle_rad=math.radians(45.0),
            dt=1.0,
            max_time_s=900.0,
            srp_target_altitude_m=4000.0,
        )

        self.assertTrue(profile.success)
        self.assertEqual(profile.outcome, "SUCCESS_SRP_HANDOVER")
        self.assertTrue(profile.srp_handover_achieved)
        self.assertLessEqual(profile.srp_altitude_m, 5000.0)
        self.assertGreater(profile.peak_convective_flux_w_m2, 100000.0)
        self.assertLess(profile.peak_g_load, 5.5)  # Within structural limits
        self.assertGreater(len(profile.states), 100)

    def test_mars_skip_out_trajectory(self):
        profile = self.solver.propagate_mars_entry(
            entry_altitude_m=125000.0,
            entry_velocity_ms=7500.0,
            entry_gamma_rad=math.radians(0.12),  # Positive flight path angle
            bank_angle_rad=0.0,
            dt=1.0,
            max_time_s=300.0,
        )
        self.assertFalse(profile.success)
        self.assertEqual(profile.outcome, "MARS_ATMOSPHERIC_SKIP_OUT")

    def test_mars_corridor_structural_overload(self):
        strict_corridor = MarsEntryCorridor(max_load_factor_g=1.5)
        strict_solver = MarsEntryAerocaptureSolver(corridor=strict_corridor)

        profile = strict_solver.propagate_mars_entry(
            entry_altitude_m=125000.0,
            entry_velocity_ms=7400.0,
            entry_gamma_rad=math.radians(-14.5),
            bank_angle_rad=0.0,
            dt=1.0,
            max_time_s=600.0,
        )
        self.assertFalse(profile.success)
        self.assertEqual(profile.outcome, "STRUCTURAL_LOAD_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
