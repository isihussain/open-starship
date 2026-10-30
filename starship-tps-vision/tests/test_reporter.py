import unittest
import tempfile
import os
from starship_tps_vision.synthetic import SyntheticTileGridGenerator
from starship_tps_vision.detector import TileDefectDetector
from starship_tps_vision.reporter import InspectionReporter


class TestReporter(unittest.TestCase):
    def test_json_and_markdown_generation(self):
        gen = SyntheticTileGridGenerator()
        obs = gen.generate_sector(num_tiles_axial=5, num_tiles_azimuthal=5, defect_rate=0.4)
        detector = TileDefectDetector()
        batch_result = detector.inspect_batch(obs)

        with tempfile.TemporaryDirectory() as tmpdir:
            json_p = os.path.join(tmpdir, "report.json")
            md_p = os.path.join(tmpdir, "report.md")

            InspectionReporter.export_json(batch_result, json_p)
            content = InspectionReporter.generate_markdown_report(batch_result, md_p)

            self.assertTrue(os.path.exists(json_p))
            self.assertTrue(os.path.exists(md_p))
            self.assertIn("Starship TPS Tile Inspection and Maintenance Work Order", content)


if __name__ == "__main__":
    unittest.main()
