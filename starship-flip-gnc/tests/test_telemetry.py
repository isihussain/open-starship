import unittest
import tempfile
import os
from starship_flip_gnc.telemetry import TelemetryRecord, TelemetryLogger


class TestTelemetry(unittest.TestCase):
    def test_json_and_csv_export(self):
        logger = TelemetryLogger()
        sample = TelemetryRecord(
            time_s=1.0,
            altitude_m=400.0,
            downrange_m=12.5,
            velocity_x_mps=2.0,
            velocity_z_mps=-60.0,
            speed_mps=60.03,
            pitch_deg=75.0,
            pitch_rate_deg_s=-5.0,
            throttle=0.85,
            gimbal_deg=4.2,
            thrust_n=5.5e6,
            drag_n=1.2e5,
            lift_n=2.0e4,
            dynamic_pressure_pa=2400.0,
            heat_flux_w_m2=12000.0,
            total_mass_kg=123000.0,
            accel_lateral_mps2=1.5,
            accel_axial_mps2=15.0,
        )
        logger.log(sample)

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "telem.json")
            csv_path = os.path.join(tmpdir, "telem.csv")

            logger.export_json(json_path)
            logger.export_csv(csv_path)

            self.assertTrue(os.path.exists(json_path))
            self.assertTrue(os.path.exists(csv_path))

            loaded = TelemetryLogger.load_json(json_path)
            self.assertEqual(len(loaded), 1)
            self.assertAlmostEqual(loaded[0].altitude_m, 400.0)


if __name__ == "__main__":
    unittest.main()
