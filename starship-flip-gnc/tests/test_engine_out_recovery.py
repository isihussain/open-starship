import unittest
import math
from starship_flip_gnc.engine_out_recovery import (
    EngineOutCompensator,
    EngineTelemetry,
    VehicleState,
    CompensationPlan,
)


class TestEngineOutCompensator(unittest.TestCase):
    def setUp(self):
        self.compensator = EngineOutCompensator(
            min_chamber_pressure_bar=60.0,
            thrust_loss_threshold_ratio=0.65,
        )
        self.vehicle = VehicleState(
            mass_kg=115_000.0,  # 115 tons landing mass (~1.13 MN weight)
            gimbal_to_com_distance_m=18.0,
            nominal_isp_s=330.0,
            max_gimbal_limit_rad=math.radians(18.0),
        )

    def test_nominal_three_engine_configuration(self):
        engines = [
            EngineTelemetry("center", 0.0, 0.0, 220.0, 1.2e6, 1.2e6),
            EngineTelemetry("outer_port", -1.8, 0.0, 220.0, 1.2e6, 1.2e6),
            EngineTelemetry("outer_starboard", 1.8, 0.0, 220.0, 1.2e6, 1.2e6),
        ]
        plan = self.compensator.evaluate(
            engines=engines,
            vehicle=self.vehicle,
            target_delta_v_mps=150.0,
            nominal_burn_duration_s=12.0,
        )

        self.assertEqual(len(plan.failed_engines), 0)
        self.assertEqual(len(plan.operational_engines), 3)
        self.assertTrue(plan.attitude_controllable)
        self.assertTrue(plan.gravity_arrest_possible)
        self.assertGreater(plan.thrust_to_weight_ratio, 1.1)
        self.assertIn("Nominal propulsion", plan.message)

    def test_single_engine_out_gimbal_trim_and_burn_extension(self):
        # outer_port suffers turbopump flameout: chamber pressure collapses to 12 bar
        engines = [
            EngineTelemetry("center", 0.0, 0.0, 220.0, 1.2e6, 1.2e6),
            EngineTelemetry("outer_port", -1.8, 0.0, 12.0, 1.2e6, 0.05e6),
            EngineTelemetry("outer_starboard", 1.8, 0.0, 220.0, 1.2e6, 1.2e6),
        ]
        plan = self.compensator.evaluate(
            engines=engines,
            vehicle=self.vehicle,
            target_delta_v_mps=150.0,
            nominal_burn_duration_s=12.0,
        )

        self.assertIn("outer_port", plan.failed_engines)
        self.assertEqual(len(plan.operational_engines), 2)
        self.assertEqual(plan.throttle_commands["outer_port"], 0.0)

        # Operational engines throttle up to maintain required TWR
        self.assertGreaterEqual(plan.throttle_commands["center"], 0.40)
        self.assertGreaterEqual(plan.throttle_commands["outer_starboard"], 0.40)

        # Gimbal trim on outer_starboard offsets asymmetric moment
        # outer_starboard is at x = +1.8m, yaw trim should be negative (points thrust vector through CoM)
        trim_pitch, trim_yaw = plan.gimbal_trims_rad["outer_starboard"]
        self.assertAlmostEqual(trim_pitch, 0.0, places=3)
        self.assertLess(trim_yaw, 0.0)
        self.assertLess(abs(trim_yaw), self.vehicle.max_gimbal_limit_rad)

        self.assertTrue(plan.attitude_controllable)
        self.assertTrue(plan.gravity_arrest_possible)
        self.assertIn("ENGINE-OUT MITIGATION ACTIVE", plan.message)

    def test_insufficient_thrust_to_weight_flagged(self):
        # Overweight vehicle where 2 engines fail and single remaining engine maxes out below weight
        heavy_vehicle = VehicleState(
            mass_kg=250_000.0,  # 250 tons (~2.45 MN weight)
            gimbal_to_com_distance_m=20.0,
        )
        engines = [
            EngineTelemetry("center", 0.0, 0.0, 220.0, 2.2e6, 2.2e6),
            EngineTelemetry("outer_port", -1.8, 0.0, 10.0, 2.2e6, 0.0),
            EngineTelemetry("outer_starboard", 1.8, 0.0, 10.0, 2.2e6, 0.0),
        ]
        plan = self.compensator.evaluate(
            engines=engines,
            vehicle=heavy_vehicle,
            target_delta_v_mps=150.0,
            nominal_burn_duration_s=12.0,
        )

        self.assertEqual(len(plan.failed_engines), 2)
        # 1 engine max 2.2 MN < 2.45 MN weight -> cannot arrest gravity
        self.assertFalse(plan.gravity_arrest_possible)
        self.assertLess(plan.thrust_to_weight_ratio, 1.0)

    def test_total_propulsion_loss(self):
        engines = [
            EngineTelemetry("center", 0.0, 0.0, 5.0, 1.2e6, 0.0),
            EngineTelemetry("outer_port", -1.8, 0.0, 5.0, 1.2e6, 0.0),
            EngineTelemetry("outer_starboard", 1.8, 0.0, 5.0, 1.2e6, 0.0),
        ]
        plan = self.compensator.evaluate(
            engines=engines,
            vehicle=self.vehicle,
            target_delta_v_mps=150.0,
            nominal_burn_duration_s=12.0,
        )

        self.assertEqual(len(plan.failed_engines), 3)
        self.assertEqual(len(plan.operational_engines), 0)
        self.assertFalse(plan.attitude_controllable)
        self.assertFalse(plan.gravity_arrest_possible)
        self.assertIn("TOTAL PROPULSION LOSS", plan.message)


if __name__ == "__main__":
    unittest.main()
