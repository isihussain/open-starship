"""
Unit tests for TPS Vision enhancements:
  - HexAxialCoord representation and distance
  - TileSpatialClusterAnalyzer (BFS connected components)
  - MultiSpectralObservation and MultiSpectralInspectionResult
  - InspectionMetricsEngine (Precision, Recall, F1 score)
"""

import unittest
from starship_tps_vision.synthetic import (
    HexAxialCoord,
    TileSpatialClusterAnalyzer,
    TileObservation,
    DefectType,
)
from starship_tps_vision.detector import (
    TileDefectDetector,
    TileInspectionResult,
    MultiSpectralObservation,
    MultiSpectralInspectionResult,
    InspectionMetricsEngine,
)


class TestVisionEnhancements(unittest.TestCase):
    def test_hex_axial_coordinates_and_distance(self):
        c1 = HexAxialCoord(0, 0)
        neighbors = c1.neighbors()
        self.assertEqual(len(neighbors), 6)
        for n in neighbors:
            self.assertEqual(c1.distance_to(n), 1)

        c2 = HexAxialCoord(3, -2)
        dist = c1.distance_to(c2)
        self.assertGreater(dist, 1)

    def test_tile_spatial_cluster_analyzer(self):
        # Create a 2-tile contiguous cluster and 1 isolated defect:
        obs = [
            TileObservation("T-R02-C04", 10.0, 0.0, 0.1, 0.0, 5.0, DefectType.MISSING_TILE),
            TileObservation("T-R02-C05", 10.0, 0.0, 0.1, 0.0, 5.0, DefectType.MISSING_TILE),
            TileObservation("T-R10-C10", 10.0, 0.0, 0.1, 0.0, 5.0, DefectType.CRACKED_TILE),
            TileObservation("T-R00-C00", 10.0, 0.0, 1.0, 0.0, 2.0, DefectType.NONE),
        ]
        clusters = TileSpatialClusterAnalyzer.find_defect_clusters(obs)
        self.assertGreaterEqual(len(clusters), 2)

    def test_multi_spectral_observation_structures(self):
        obs = MultiSpectralObservation(
            tile_id="T-R05-C02",
            surface_area_ratio=0.98,
            crack_length_mm=0.0,
            max_inter_tile_gap_mm=2.1,
            thermal_ir_temp_delta_k=14.5,
            acoustic_tap_compliance=3.2,
        )
        self.assertGreater(obs.thermal_ir_temp_delta_k, 10.0)
        self.assertGreater(obs.acoustic_tap_compliance, 2.5)

    def test_inspection_metrics_engine(self):
        detector = TileDefectDetector()
        obs_list = [
            TileObservation("T1", 0.0, 0.0, 0.05, 0.0, 10.0, DefectType.MISSING_TILE),
            TileObservation("T2", 0.0, 0.0, 0.99, 45.0, 2.0, DefectType.CRACKED_TILE),
            TileObservation("T3", 0.0, 0.0, 1.0, 0.0, 2.0, DefectType.NONE),
            TileObservation("T4", 0.0, 0.0, 1.0, 0.0, 2.0, DefectType.NONE),
        ]
        results = [detector.inspect_tile(o) for o in obs_list]
        metrics = InspectionMetricsEngine.evaluate_performance(results, obs_list)

        self.assertIn("precision", metrics)
        self.assertIn("recall", metrics)
        self.assertIn("f1_score", metrics)
        self.assertGreaterEqual(metrics["accuracy"], 0.75)


if __name__ == "__main__":
    unittest.main()
