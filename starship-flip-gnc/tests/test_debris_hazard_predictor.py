import unittest
from starship_flip_gnc.debris_hazard_predictor import (
    DebrisHazardPredictor,
    GeofencePolygon,
    KinematicVector,
    DebrisFootprintReport,
)


class TestDebrisHazardPredictor(unittest.TestCase):
    def setUp(self):
        self.zones = [
            GeofencePolygon(
                name="Guizhou_Inhabited_Township_A",
                is_populated_exclusion=True,
                x_min_km=180.0,
                x_max_km=240.0,
                y_min_km=-30.0,
                y_max_km=30.0,
            ),
            GeofencePolygon(
                name="Shaanxi_Industrial_Corridor",
                is_populated_exclusion=True,
                x_min_km=280.0,
                x_max_km=320.0,
                y_min_km=-15.0,
                y_max_km=45.0,
            ),
            GeofencePolygon(
                name="Designated_Desert_Drop_Zone",
                is_populated_exclusion=False,
                x_min_km=400.0,
                x_max_km=550.0,
                y_min_km=-60.0,
                y_max_km=60.0,
            ),
        ]
        self.predictor = DebrisHazardPredictor(
            zones=self.zones,
            safe_drop_center_km=(480.0, 0.0),
        )

    def test_safe_trajectory_outside_inhabited_zones(self):
        # Spent stage trajectory heading towards designated desert drop zone at ~470 km
        kin = KinematicVector(
            altitude_m=65_000.0,
            downrange_km=120.0,
            crossrange_km=0.0,
            vx_mps=2400.0,
            vy_mps=0.0,
            vz_mps=450.0,
            ballistic_coefficient=900.0,
        )
        report = self.predictor.evaluate_trajectory(kin)

        self.assertTrue(report.safe)
        self.assertEqual(len(report.breached_exclusions), 0)
        self.assertFalse(report.afts_destruct_required)
        self.assertIn("Debris trajectory clear", report.status_message)
        self.assertGreater(report.iip_downrange_km, 350.0)

    def test_inland_corridor_exclusion_breach_detected(self):
        # Spent stage trajectory tracking directly into Guizhou township exclusion zone
        kin = KinematicVector(
            altitude_m=42_000.0,
            downrange_km=90.0,
            crossrange_km=5.0,
            vx_mps=1350.0,
            vy_mps=0.0,
            vz_mps=-100.0,  # Already descending
            ballistic_coefficient=800.0,
        )
        report = self.predictor.evaluate_trajectory(kin)

        self.assertFalse(report.safe)
        self.assertIn("Guizhou_Inhabited_Township_A", report.breached_exclusions)
        self.assertIn("CORRIDOR VIOLATION DETECTED", report.status_message)

        # Divert vector to shift IIP from ~200 km to safe target 480 km
        dv_x, dv_y = report.divert_correction_mps
        self.assertGreater(dv_x, 0.0)

    def test_imminent_impact_triggers_afts(self):
        # Low altitude, rapid descent directly into exclusion zone, not enough time to divert
        kin = KinematicVector(
            altitude_m=2_500.0,
            downrange_km=200.0,
            crossrange_km=0.0,
            vx_mps=200.0,
            vy_mps=0.0,
            vz_mps=-180.0,
            ballistic_coefficient=750.0,
        )
        report = self.predictor.evaluate_trajectory(kin)

        self.assertFalse(report.safe)
        self.assertLess(report.time_to_impact_s, 25.0)
        self.assertTrue(report.afts_destruct_required)

    def test_ballistic_coefficient_drag_effect(self):
        # Compare high drag vs low drag trajectory from identical initial state
        kin_light = KinematicVector(
            altitude_m=50_000.0, downrange_km=50.0, crossrange_km=0.0,
            vx_mps=1500.0, vy_mps=0.0, vz_mps=200.0, ballistic_coefficient=200.0
        )
        kin_heavy = KinematicVector(
            altitude_m=50_000.0, downrange_km=50.0, crossrange_km=0.0,
            vx_mps=1500.0, vy_mps=0.0, vz_mps=200.0, ballistic_coefficient=1200.0
        )
        x_light, _, _ = self.predictor.compute_iip(kin_light)
        x_heavy, _, _ = self.predictor.compute_iip(kin_heavy)

        # Heavier stage (higher ballistic coefficient) penetrates atmosphere with less drag deceleration
        self.assertGreater(x_heavy, x_light)


if __name__ == "__main__":
    unittest.main()
