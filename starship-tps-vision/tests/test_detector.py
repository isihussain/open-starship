import unittest
from starship_tps_vision.synthetic import TileObservation, DefectType
from starship_tps_vision.detector import TileDefectDetector


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.detector = TileDefectDetector()

    def test_missing_tile_detection(self):
        obs = TileObservation(
            tile_id="T-01",
            z_hull_m=22.0,
            azimuth_deg=0.0,
            surface_area_ratio=0.05,
            crack_length_mm=0.0,
            max_inter_tile_gap_mm=20.0,
            ground_truth_defect=DefectType.MISSING_TILE,
        )
        res = self.detector.inspect_tile(obs)
        self.assertEqual(res.detected_defect, DefectType.MISSING_TILE)
        self.assertEqual(res.action_required, "REPLACE_IMMEDIATELY")
        self.assertIn(res.severity_level, ("CRITICAL", "HIGH"))

    def test_cracked_tile_detection(self):
        obs = TileObservation(
            tile_id="T-02",
            z_hull_m=10.0,
            azimuth_deg=0.0,
            surface_area_ratio=0.98,
            crack_length_mm=45.0,
            max_inter_tile_gap_mm=2.1,
            ground_truth_defect=DefectType.CRACKED_TILE,
        )
        res = self.detector.inspect_tile(obs)
        self.assertEqual(res.detected_defect, DefectType.CRACKED_TILE)
        self.assertEqual(res.action_required, "REPLACE_IMMEDIATELY")

    def test_nominal_tile_pass(self):
        obs = TileObservation(
            tile_id="T-03",
            z_hull_m=0.0,
            azimuth_deg=180.0,
            surface_area_ratio=1.0,
            crack_length_mm=0.0,
            max_inter_tile_gap_mm=2.0,
            ground_truth_defect=DefectType.NONE,
        )
        res = self.detector.inspect_tile(obs)
        self.assertEqual(res.detected_defect, DefectType.NONE)
        self.assertEqual(res.severity_level, "PASS")
        self.assertEqual(res.priority_score, 0.0)


if __name__ == "__main__":
    unittest.main()
