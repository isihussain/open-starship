import unittest
from starship_geo_sat.azercosmos_orbital_coordination import (
    AzercosmosOrbitalCoordinator,
    GroundStationSite,
    SatelliteSlot,
)
from starship_geo_sat.azersky_debris_conjunction import (
    AzerSkyDebrisAnalyzer,
    AzerSkyOrbitSpec,
    DebrisImpactTelemetry,
)


class TestAzercosmosOrbitalCoordination(unittest.TestCase):
    def setUp(self):
        self.coordinator = AzercosmosOrbitalCoordinator()
        self.absheron_teleport = GroundStationSite(
            name="Absheron Main Ground Control Station",
            latitude_deg=40.4093,
            longitude_deg=49.8671,
            altitude_m=50.0,
            antenna_diameter_m=9.0,
            tier_rating="Tier 4",
        )
        self.user_vsat = GroundStationSite(
            name="Regional VSAT Terminal",
            latitude_deg=40.0,
            longitude_deg=45.0,
            altitude_m=100.0,
            antenna_diameter_m=1.2,
        )

    def test_angular_separation(self):
        sep = self.coordinator.compute_angular_separation()
        self.assertAlmostEqual(sep, 0.9, places=2)

    def test_antenna_beamwidth_vs_separation(self):
        # 1.2m dish at 11.7 GHz has beamwidth ~1.5° > 0.9° separation
        bw_small = self.coordinator.compute_antenna_beamwidth(11.7, 1.2)
        self.assertGreater(bw_small, 0.9)

        # 9.0m teleport dish at 11.7 GHz has beamwidth ~0.2° << 0.9° separation
        bw_teleport = self.coordinator.compute_antenna_beamwidth(11.7, 9.0)
        self.assertLess(bw_teleport, 0.3)

    def test_adjacent_interference_small_aperture(self):
        assessment = self.coordinator.evaluate_adjacent_interference(
            earth_station=self.user_vsat,
            carrier_freq_ghz=11.7,
        )
        self.assertAlmostEqual(assessment.angular_separation_deg, 0.9, places=2)
        self.assertGreater(assessment.ground_antenna_3db_beamwidth_deg, 0.9)
        self.assertIn("ACM:", assessment.status_message)
        # Sidelobe discrimination is lower for 1.2m dish
        self.assertLess(assessment.antenna_isolation_db, 25.0)

    def test_adjacent_interference_teleport_high_throughput(self):
        assessment = self.coordinator.evaluate_adjacent_interference(
            earth_station=self.absheron_teleport,
            carrier_freq_ghz=11.7,
        )
        # 9m teleport dish provides substantial isolation
        self.assertGreater(assessment.antenna_isolation_db, 25.0)
        self.assertTrue(assessment.itu_envelope_compliant)
        self.assertIn("32APSK", assessment.acm_modulation_recommended)

    def test_ground_station_geometry_absheron(self):
        geom = self.coordinator.evaluate_ground_station_geometry(
            station=self.absheron_teleport,
            sat_lon_deg=46.0,
            frequency_ghz=12.0,
        )
        # Absheron elevation to 46.0°E is approx 43.5°
        self.assertGreater(geom["elevation_deg"], 40.0)
        self.assertLess(geom["elevation_deg"], 50.0)
        # Slant range is approximately 37,000 - 38,000 km
        self.assertGreater(geom["slant_range_km"], 36000.0)
        self.assertLess(geom["slant_range_km"], 40000.0)
        # Path loss is > 200 dB
        self.assertGreater(geom["free_space_path_loss_db"], 200.0)

    def test_teleport_redundancy_failover(self):
        # Nominal condition
        res_nominal = self.coordinator.evaluate_teleport_redundancy(
            absheron_snr_db=14.5,
            nakhchivan_snr_db=14.0,
        )
        self.assertEqual(res_nominal["active_station"], "ABSHERON_MAIN_STATION")

        # Heavy rain over Absheron triggers failover to Nakhchivan
        res_failover = self.coordinator.evaluate_teleport_redundancy(
            absheron_snr_db=5.2,
            nakhchivan_snr_db=13.8,
        )
        self.assertEqual(res_failover["active_station"], "NAKHCHIVAN_RESERVE_STATION")


class TestAzerSkyDebrisConjunction(unittest.TestCase):
    def setUp(self):
        self.analyzer = AzerSkyDebrisAnalyzer()

    def test_orbit_velocity_and_period(self):
        vel = self.analyzer.compute_orbital_velocity()
        # 695 km altitude circular speed is approx 7.51 km/s (7500 - 7520 m/s)
        self.assertGreater(vel, 7490.0)
        self.assertLess(vel, 7530.0)

        period = self.analyzer.compute_orbital_period_minutes()
        # Period is approx 98.6 - 98.8 minutes
        self.assertAlmostEqual(period, 98.7, delta=0.5)

    def test_microdebris_penetration_and_power_loss_classification(self):
        # 10 mm (1 cm) aluminum particle at 14.2 km/s (typical SSO crossing speed)
        # Historical event: March 17, 2023 at 19:34 UTC
        telemetry = DebrisImpactTelemetry(
            event_timestamp_utc="2023-03-17T19:34:00Z",
            estimated_particle_diameter_mm=10.0,
            relative_velocity_km_s=14.2,
            debris_density_g_cm3=2.8,
            measured_bus_voltage_volts=0.0,
            ssn_tracked_object_count=1,  # Single intact body tracked by US SSN
            rf_signal_strength_dbm=-140.0,
        )
        report = self.analyzer.diagnose_anomaly(telemetry)

        # Kinetic energy should exceed 100 kJ
        self.assertGreater(report.kinetic_energy_joules, 100000.0)
        # Penetration depth should easily breach 1.6 mm aluminum bus wall
        self.assertGreater(report.hypervelocity_penetration_mm, 10.0)
        self.assertTrue(report.bus_skin_breached)
        self.assertTrue(report.power_harness_severed)
        self.assertEqual(report.anomaly_classification, "HYPERVELOCITY_MICRODEBRIS_COLLISION")
        self.assertIn("SPOT-6_TWIN_HANDOFF", report.service_continuity_plan)

    def test_explosive_fragmentation_classification(self):
        # If US SSN tracked object count indicates multiple fragments
        telemetry = DebrisImpactTelemetry(
            event_timestamp_utc="2023-03-17T19:34:00Z",
            estimated_particle_diameter_mm=150.0,
            relative_velocity_km_s=14.2,
            measured_bus_voltage_volts=0.0,
            ssn_tracked_object_count=45,  # Debris cloud
        )
        report = self.analyzer.diagnose_anomaly(telemetry)
        self.assertEqual(report.anomaly_classification, "CATASTROPHIC_EXPLOSIVE_FRAGMENTATION")


if __name__ == "__main__":
    unittest.main()
