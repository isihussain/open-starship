import unittest
from starship_tps_vision.synthetic import SyntheticTileGridGenerator, DefectType


class TestSynthetic(unittest.TestCase):
    def test_grid_generation_counts_and_defects(self):
        gen = SyntheticTileGridGenerator(random_seed=123)
        obs = gen.generate_sector(num_tiles_axial=10, num_tiles_azimuthal=10, defect_rate=0.20)

        self.assertEqual(len(obs), 100)
        # Verify that both intact and defect tiles are generated
        defects = [o.ground_truth_defect for o in obs if o.ground_truth_defect != DefectType.NONE]
        self.assertGreater(len(defects), 5)

        for o in obs:
            self.assertGreaterEqual(o.surface_area_ratio, 0.0)
            self.assertLessEqual(o.surface_area_ratio, 1.0)
            self.assertGreater(o.max_inter_tile_gap_mm, 0.0)


if __name__ == "__main__":
    unittest.main()
