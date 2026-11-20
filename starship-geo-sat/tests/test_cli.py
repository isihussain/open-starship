"""
Unit tests for starship-geo-sat command-line interface.
"""

import json
import tempfile
import unittest
from pathlib import Path

from starship_geo_sat.cli import main


class TestGeoSatCLI(unittest.TestCase):

    def test_cli_station_keeping_mode(self):
        """Test default station-keeping prognosis mode."""
        exit_code = main(["--mode", "station-keeping", "--slot", "42.0", "--propellant", "250.0"])
        self.assertEqual(exit_code, 0)

    def test_cli_launch_abort_mode(self):
        """Test upper-stage launch abort detection mode."""
        exit_code = main(["--mode", "launch-abort", "--chamber-pressure", "34.5", "--velocity", "9800.0"])
        self.assertEqual(exit_code, 0)

    def test_cli_los_blackout_mode(self):
        """Test loss-of-signal blackout assessment mode."""
        exit_code = main(["--mode", "los-blackout", "--velocity", "7825.0", "--altitude", "185000.0"])
        self.assertEqual(exit_code, 0)

    def test_cli_optical_isl_mode(self):
        """Test optical inter-satellite crosslink link budget mode."""
        exit_code = main(["--mode", "optical-isl", "--distance", "4500.0"])
        self.assertEqual(exit_code, 0)

    def test_cli_json_export(self):
        """Test JSON output export across evaluations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "geo_cli_out.json"
            exit_code = main([
                "--mode", "station-keeping",
                "--slot", "42.0",
                "--export-json", str(out_file),
            ])
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_file.exists())

            with open(out_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertEqual(data["mode"], "station-keeping")
            self.assertEqual(data["slot_longitude_deg"], 42.0)
            self.assertIn("remaining_lifetime_years", data)
            self.assertIn("usable_propellant_kg", data)


if __name__ == "__main__":
    unittest.main()
