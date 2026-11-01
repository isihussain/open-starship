import unittest
from starship_geo_sat.reaction_wheel_desat import (
    ReactionWheelDesaturator,
    WheelAssemblyState,
    SolarPressureProperties,
    DesaturationPlan,
)


class TestReactionWheelDesaturator(unittest.TestCase):
    def setUp(self):
        self.desaturator = ReactionWheelDesaturator(
            thruster_thrust_n=1.0,
            moment_arm_m=1.6,
            thruster_isp_s=220.0,
            max_allowable_dv_mps=0.005,
        )
        self.srp = SolarPressureProperties(
            total_area_m2=38.0,
            center_of_pressure_offset_m=0.18,
            solar_flux_w_m2=1361.0,
            reflectivity_factor=1.35,
        )

    def test_solar_radiation_torque_calculation(self):
        torque = self.desaturator.calculate_srp_torque_nm(self.srp)
        # S/c * (1+Cr) * A * r_offset ~ (1361 / 3e8) * 1.35 * 38 * 0.18 ~ 4.2e-5 N*m
        self.assertGreater(torque, 1.0e-5)
        self.assertLess(torque, 1.0e-4)

    def test_momentum_accumulation_under_threshold(self):
        wheels = WheelAssemblyState(hx_nms=5.0, hy_nms=4.0, hz_nms=2.0, wheel_capacity_nms=35.0)
        torque = self.desaturator.calculate_srp_torque_nm(self.srp)
        updated = self.desaturator.accumulate_momentum(wheels, torque, duration_hours=24.0)

        plan = self.desaturator.plan_desaturation(updated)
        self.assertFalse(plan.desaturation_required)
        self.assertEqual(plan.pulse_duration_s, 0.0)
        self.assertIn("nominal", plan.status_message)

    def test_desaturation_triggered_and_orbital_deadband_respected(self):
        # Force saturated wheels (30 N*m*s > 80% of 35 N*m*s = 28 N*m*s)
        saturated = WheelAssemblyState(hx_nms=22.0, hy_nms=20.0, hz_nms=10.0, wheel_capacity_nms=35.0)
        plan = self.desaturator.plan_desaturation(saturated)

        self.assertTrue(plan.desaturation_required)
        self.assertGreater(plan.pulse_duration_s, 0.5)
        self.assertGreater(plan.propellant_consumed_grams, 1.0)
        self.assertTrue(plan.station_keeping_deadband_safe)
        self.assertLess(plan.net_translational_dv_mps, 0.005)
        self.assertIn("MOMENTUM DESATURATION COMMANDED", plan.status_message)


if __name__ == "__main__":
    unittest.main()
