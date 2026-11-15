import unittest
from starship_geo_sat.hotbird_fleet_operations import (
    HotbirdFleetCoordinator,
    OrbitalVectorState,
)


class TestHotbirdFleetOperations(unittest.TestCase):
    def setUp(self):
        self.coordinator = HotbirdFleetCoordinator()

    def test_fleet_catalog_completeness(self):
        catalog = self.coordinator.fleet_catalog
        # Verify all major iterations from Hot Bird 1 to 13G are registered
        self.assertIn("Hot Bird 1", catalog)
        self.assertIn("Hot Bird 2", catalog)
        self.assertIn("Hot Bird 3", catalog)
        self.assertIn("Hot Bird 6 / 13D", catalog)
        self.assertIn("Hot Bird 7", catalog)
        self.assertIn("Hot Bird 7A / 13E", catalog)
        self.assertIn("Hot Bird 8 / 13B", catalog)
        self.assertIn("Hot Bird 9 / 13C", catalog)
        self.assertIn("Hot Bird 10 / 33E", catalog)
        self.assertIn("Hot Bird 13F", catalog)
        self.assertIn("Hot Bird 13G", catalog)

        # Check Gen 4 features
        hb13g = catalog["Hot Bird 13G"]
        self.assertEqual(hb13g.generation, 4)
        self.assertEqual(hb13g.platform, "Eurostar Neo")
        self.assertTrue(hb13g.all_electric_propulsion)
        self.assertTrue(hb13g.has_egnos_sbas)

    def test_colocation_ei_separation_safe(self):
        # Two spacecraft co-located at 13°E with offset eccentricity/inclination vectors
        sat_a = OrbitalVectorState(
            satellite_name="Hot Bird 13F",
            ex=0.00035, ey=0.00010,
            ix=0.00045, iy=0.00015,
        )
        sat_b = OrbitalVectorState(
            satellite_name="Hot Bird 13G",
            ex=0.00010, ey=0.00030,
            ix=0.00015, iy=0.00045,
        )
        report = self.coordinator.evaluate_colocation_ei_separation(sat_a, sat_b, safety_clearance_km=10.0)

        self.assertFalse(report.collision_hazard_detected)
        self.assertTrue(report.safe_stationkeeping_clearance)
        self.assertGreater(report.minimum_radial_normal_distance_km, 10.0)
        self.assertIn("SAFE", report.status_message)

    def test_colocation_ei_separation_hazard(self):
        # Two spacecraft with nearly identical e and i vectors (conjunction risk in the same slot)
        sat_a = OrbitalVectorState(satellite_name="Sat_Alpha", ex=0.00020, ey=0.00020, ix=0.00030, iy=0.00030)
        sat_b = OrbitalVectorState(satellite_name="Sat_Beta", ex=0.000201, ey=0.000201, ix=0.000301, iy=0.000301)
        report = self.coordinator.evaluate_colocation_ei_separation(sat_a, sat_b, safety_clearance_km=15.0)

        self.assertTrue(report.collision_hazard_detected)
        self.assertFalse(report.safe_stationkeeping_clearance)
        self.assertLess(report.minimum_radial_normal_distance_km, 5.0)

    def test_post_eclipse_thermal_shock_hotbird3(self):
        # Historical Hot Bird 3 October 2006 anomaly: thermal surge severs one wing circuit
        report = self.coordinator.simulate_post_eclipse_thermal_shock(
            satellite_name="Hot Bird 3",
            duration_shadow_min=72.0,
            insulation_microcracked=True,
        )
        self.assertEqual(report.arcing_breakdown_risk, "CRITICAL")
        self.assertTrue(report.solar_wing_electrical_failure)
        self.assertTrue(report.emergency_load_shed_required)
        self.assertAlmostEqual(report.available_bus_power_fraction, 0.52, places=2)
        self.assertIn("EMERGENCY_LOAD_SHED", report.status_message)

    def test_post_eclipse_thermal_shock_nominal(self):
        # Nominal satellite with pristine dielectric insulation
        report = self.coordinator.simulate_post_eclipse_thermal_shock(
            satellite_name="Hot Bird 13F",
            duration_shadow_min=70.0,
            insulation_microcracked=False,
        )
        self.assertEqual(report.arcing_breakdown_risk, "LOW")
        self.assertFalse(report.solar_wing_electrical_failure)
        self.assertEqual(report.available_bus_power_fraction, 1.00)

    def test_vulcain2_launch_failure_hotbird7(self):
        # Ariane 5 ECA Flight V157 anomaly (Hot Bird 7 loss)
        diag = self.coordinator.evaluate_vulcain2_launch_failure(
            elapsed_time_s=456.0,
            nozzle_cooling_pressure_bar=10.5,
            nominal_nozzle_pressure_bar=85.0,
            yaw_attitude_error_deg=35.0,
        )
        self.assertEqual(diag["flight_outcome"], "RANGE_SAFETY_DESTRUCT_COMMANDED")
        self.assertIn("Hot Bird 7", diag["incident_reference"])

    def test_fleet_migration_to_eurostar_neo(self):
        # Zero-downtime broadcast migration to 13F & 13G with EGNOS GEO-4
        migration = self.coordinator.evaluate_fleet_migration_to_eurostar_neo(migrated_channel_count=980)
        self.assertEqual(migration.migration_status, "COMPLETED_ZERO_DOWNTIME")
        self.assertEqual(migration.channels_switched_zero_downtime, 980)
        self.assertEqual(migration.total_transponders_migrated, 160)
        self.assertTrue(migration.egnos_geo4_sbas_active)
        self.assertGreater(migration.sbas_l1_power_margin_db, 5.0)
        self.assertGreater(migration.sbas_l5_power_margin_db, 5.0)


if __name__ == "__main__":
    unittest.main()
