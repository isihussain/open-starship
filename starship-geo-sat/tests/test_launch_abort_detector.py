import unittest
from starship_geo_sat.launch_abort_detector import (
    LaunchAbortDetector,
    PropulsionTelemetry,
    AbortAssessment,
)


class TestLaunchAbortDetector(unittest.TestCase):
    def setUp(self):
        self.detector = LaunchAbortDetector(
            min_pc_ratio=0.80,
            min_turbopump_speed_ratio=0.75,
            min_valve_opening_percent=60.0,
            target_gto_velocity_mps=10_200.0,
        )

    def test_nominal_cryogenic_third_stage_burn(self):
        telem = PropulsionTelemetry(
            timestamp_s=680.0,
            chamber_pressure_bar=34.8,
            nominal_chamber_pressure_bar=35.0,
            turbopump_speed_rpm=61_500.0,
            nominal_turbopump_speed_rpm=62_000.0,
            lox_valve_position_percent=99.5,
            axial_acceleration_mps2=21.0,
            altitude_km=210.0,
            inertial_velocity_mps=9500.0,
        )
        assessment = self.detector.evaluate(telem)

        self.assertTrue(assessment.nominal_thrust)
        self.assertFalse(assessment.abort_triggered)
        self.assertFalse(assessment.spacecraft_safing_commanded)
        self.assertIn("nominal envelope", assessment.status_message)

    def test_lox_turbopump_valve_failure_triggers_suborbital_abort(self):
        # Ariane 4 H10-3 oxygen valve collapse (Türksat 1A scenario)
        telem = PropulsionTelemetry(
            timestamp_s=710.0,
            chamber_pressure_bar=12.5,        # Dropped below 80% (35 * 0.8 = 28 bar)
            nominal_chamber_pressure_bar=35.0,
            turbopump_speed_rpm=38_000.0,     # Pump cavitating
            nominal_turbopump_speed_rpm=62_000.0,
            lox_valve_position_percent=25.0,  # Valve failed shut
            axial_acceleration_mps2=1.5,
            altitude_km=195.0,
            inertial_velocity_mps=7400.0,     # Severe shortfall from 10,200 m/s
        )
        assessment = self.detector.evaluate(telem)

        self.assertFalse(assessment.nominal_thrust)
        self.assertTrue(assessment.abort_triggered)
        self.assertTrue(assessment.spacecraft_safing_commanded)
        self.assertTrue(assessment.telemetry_burst_active)
        self.assertGreater(assessment.injection_shortfall_mps, 2000.0)
        self.assertGreater(assessment.time_to_impact_s, 100.0)
        self.assertIn("SUBORBITAL ABORT DETECTED", assessment.status_message)


if __name__ == "__main__":
    unittest.main()
