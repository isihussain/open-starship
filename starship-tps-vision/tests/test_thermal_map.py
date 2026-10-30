import unittest
from starship_tps_vision.thermal_map import AerothermalRiskMap


class TestThermalMap(unittest.TestCase):
    def test_default_risk_mapping(self):
        risk_map = AerothermalRiskMap()
        # Stagnation zone on windward nose:
        zone_nose, score_nose = risk_map.evaluate_tile_risk(z_hull_m=22.0, azimuth_deg=0.0)
        self.assertEqual(zone_nose, "ZONE_NOSE_STAGNATION")
        self.assertGreater(score_nose, 1.0)

        # Leeward shadow:
        zone_lee, score_lee = risk_map.evaluate_tile_risk(z_hull_m=0.0, azimuth_deg=180.0)
        self.assertEqual(zone_lee, "ZONE_LEEWARD_SHADOW")
        self.assertLess(score_lee, score_nose)

    def test_from_telemetry(self):
        records = [
            {"dynamic_pressure_pa": 20000.0, "heat_flux_w_m2": 50000.0},
            {"dynamic_pressure_pa": 65000.0, "heat_flux_w_m2": 180000.0},
        ]
        risk_map = AerothermalRiskMap.from_telemetry(records)
        self.assertAlmostEqual(risk_map.peak_q_dyn, 65000.0)
        self.assertAlmostEqual(risk_map.peak_heat_flux, 180000.0)


if __name__ == "__main__":
    unittest.main()
