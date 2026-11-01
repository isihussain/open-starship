import unittest
from starship_geo_sat.inclined_orbit_dynamics import (
    InclinedOrbitDynamics,
    OrbitalElements,
    GroundStation,
    InclinedOrbitReport,
)


class TestInclinedOrbitDynamics(unittest.TestCase):
    def setUp(self):
        self.dynamics = InclinedOrbitDynamics(
            spacecraft_dry_mass_kg=1200.0,
            specific_impulse_s=310.0,
            area_to_mass_ratio_m2_kg=0.03,
            reflectivity_coeff=1.3,
        )
        self.initial_orbit = OrbitalElements(nominal_longitude_deg=42.0)
        self.station = GroundStation(
            latitude_deg=39.789,
            longitude_deg=32.812,
            dish_diameter_m=9.0,
            beamwidth_3db_deg=0.17,
        )

    def test_nominal_zero_inclination_pointing(self):
        report = self.dynamics.propagate_drift(
            initial=self.initial_orbit,
            elapsed_years=0.0,
            station=self.station,
            current_time_hours=0.0,
            remaining_fuel_kg=25.0,
        )

        self.assertAlmostEqual(report.current_inclination_deg, 0.05, places=2)
        self.assertFalse(report.tracking_required)
        self.assertTrue(report.disposal_safe)
        self.assertLess(report.fixed_antenna_gain_loss_db, 0.5)

    def test_inclination_drift_triggers_tracking_requirement(self):
        # 4 years of secular lunisolar drift without N-S burns (~3.5 deg inclination)
        report = self.dynamics.propagate_drift(
            initial=self.initial_orbit,
            elapsed_years=4.0,
            station=self.station,
            current_time_hours=6.0,
            remaining_fuel_kg=20.0,
        )

        self.assertGreater(report.current_inclination_deg, 3.0)
        self.assertTrue(report.tracking_required)
        # Without tracking, off-axis loss exceeds 10 dB
        self.assertGreater(report.fixed_antenna_gain_loss_db, 10.0)
        self.assertTrue(report.disposal_safe)
        self.assertIn("INCLINED ORBIT ACTIVE", report.status_message)

    def test_graveyard_fuel_deficit_detection(self):
        # Spacecraft has only 1.0 kg fuel remaining, but graveyard disposal requires ~4.5 kg
        report = self.dynamics.propagate_drift(
            initial=self.initial_orbit,
            elapsed_years=10.0,
            station=self.station,
            current_time_hours=12.0,
            remaining_fuel_kg=1.0,
        )

        self.assertFalse(report.disposal_safe)
        self.assertGreater(report.graveyard_fuel_required_kg, 1.0)


if __name__ == "__main__":
    unittest.main()
