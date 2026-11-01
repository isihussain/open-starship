import unittest
from starship_flip_gnc.touchdown_gate import (
    TouchdownValidationGate,
    AltimeterSensorSuite,
    TouchdownGateResult,
)


class TestTouchdownValidationGate(unittest.TestCase):
    def setUp(self):
        self.gate = TouchdownValidationGate(
            cutoff_altitude_threshold_m=0.40,
            min_contact_force_n=40_000.0,
            min_switches_required=2,
            max_sensor_divergence_m=2.0,
            default_hover_throttle=0.52,
        )

    def test_nominal_touchdown_permits_cutoff(self):
        sensors = AltimeterSensorSuite(
            timestamp_s=42.1,
            radar_altimeter_m=0.25,
            lidar_altimeter_m=0.28,
            ins_integrated_alt_m=0.26,
            contact_force_n=65_000.0,
            contact_switches_engaged=3,
        )
        result = self.gate.evaluate(sensors, commanded_engine_cutoff=True)
        self.assertTrue(result.cutoff_permitted)
        self.assertFalse(result.override_commanded)
        self.assertTrue(result.contact_verified)
        self.assertFalse(result.plume_reflection_detected)
        self.assertEqual(result.override_throttle, 0.0)

    def test_plume_backscatter_premature_cutoff_overridden(self):
        # Radar altimeter is tricked by dust/plume into reading 0.15m at 5.5m physical altitude
        sensors = AltimeterSensorSuite(
            timestamp_s=38.4,
            radar_altimeter_m=0.15,
            lidar_altimeter_m=5.40,
            ins_integrated_alt_m=5.25,
            contact_force_n=0.0,
            contact_switches_engaged=0,
        )
        result = self.gate.evaluate(sensors, commanded_engine_cutoff=True)
        self.assertFalse(result.cutoff_permitted)
        self.assertTrue(result.override_commanded)
        self.assertTrue(result.plume_reflection_detected)
        self.assertFalse(result.contact_verified)
        self.assertAlmostEqual(result.override_throttle, 0.52)
        self.assertGreater(result.fused_altitude_m, 5.0)
        self.assertIn("PREMATURE CUTOFF OVERRIDDEN", result.message)

    def test_descent_tracking_without_cutoff_command(self):
        sensors = AltimeterSensorSuite(
            timestamp_s=25.0,
            radar_altimeter_m=18.5,
            lidar_altimeter_m=18.6,
            ins_integrated_alt_m=18.4,
            contact_force_n=0.0,
            contact_switches_engaged=0,
        )
        result = self.gate.evaluate(sensors, commanded_engine_cutoff=False)
        self.assertFalse(result.cutoff_permitted)
        self.assertFalse(result.override_commanded)
        self.assertAlmostEqual(result.fused_altitude_m, 18.5)

    def test_partial_mechanical_contact_blocks_cutoff(self):
        # Altitude is near zero, compressive force is 50 kN, but only 1 switch is engaged (need 2)
        sensors = AltimeterSensorSuite(
            timestamp_s=41.9,
            radar_altimeter_m=0.30,
            lidar_altimeter_m=0.32,
            ins_integrated_alt_m=0.31,
            contact_force_n=50_000.0,
            contact_switches_engaged=1,
        )
        result = self.gate.evaluate(sensors, commanded_engine_cutoff=True)
        self.assertFalse(result.cutoff_permitted)
        self.assertTrue(result.override_commanded)
        self.assertFalse(result.contact_verified)


if __name__ == "__main__":
    unittest.main()
