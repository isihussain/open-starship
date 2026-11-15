"""
Unit tests for GEO-SAT enhancements:
  - Lunisolar tidal third-body gravitational drift rate
  - Ground station Doppler frequency shift & antenna tracking rate
  - Equinox eclipse radiative cooldown and battery Depth-of-Discharge (DoD)
  - Hall-effect thruster cathode wear and mass utilization efficiency
  - Solar Array Drive Mechanism (SADM) stepper disturbance torque
"""

import unittest
from starship_geo_sat.inclined_orbit_dynamics import (
    InclinedOrbitDynamics,
    GroundStation,
)
from starship_geo_sat.eclipse_thermal_model import (
    EclipseThermalSimulator,
    BatteryBankSpec,
)
from starship_geo_sat.electric_orbit_raising import (
    ElectricOrbitRaisingSimulator,
)
from starship_geo_sat.reaction_wheel_desat import (
    ReactionWheelDesaturator,
)


class TestGeoEnhancements(unittest.TestCase):
    def test_lunisolar_drift_rate_calculation(self):
        orbit_dyn = InclinedOrbitDynamics()
        di_dt, draan_dt = orbit_dyn.compute_lunisolar_drift_rate(raan_deg=0.0)
        # Combined lunar and solar drift peaks around ~0.82 deg/year at raan = 0:
        self.assertAlmostEqual(di_dt, 0.82, places=2)
        self.assertAlmostEqual(draan_dt, 0.0, places=2)

    def test_ground_station_doppler_and_slew_rate(self):
        orbit_dyn = InclinedOrbitDynamics()
        gs = GroundStation(name="Test_Gateway", latitude_deg=40.0, longitude_deg=33.0)
        range_rate, doppler, slew_rate = orbit_dyn.compute_ground_station_doppler(
            gs=gs,
            uplink_freq_ghz=14.25,
            time_hours=6.0,
            inclination_deg=3.5,
        )
        self.assertIsInstance(range_rate, float)
        self.assertIsInstance(doppler, float)
        self.assertIsInstance(slew_rate, float)
        self.assertNotEqual(range_rate, 0.0)

    def test_equinox_eclipse_thermal_and_battery_dod(self):
        sim = EclipseThermalSimulator(
            battery=BatteryBankSpec(capacity_watt_hours=18_000.0, max_allowable_dod_percent=75.0),
            bus_power_consumption_watts=4500.0,
        )
        report = sim.simulate_eclipse(eclipse_duration_minutes=70.0)
        self.assertLess(report.final_solar_panel_temp_k, 200.0)
        self.assertGreater(report.final_solar_panel_temp_k, 50.0)
        self.assertGreater(report.depth_of_discharge_percent, 10.0)
        self.assertTrue(report.dod_within_safety_margin)
        self.assertGreater(report.recharge_duration_hours, 0.0)

    def test_hall_thruster_cathode_erosion(self):
        sim = ElectricOrbitRaisingSimulator()
        report = sim.evaluate_cathode_wear_and_efficiency(
            cumulative_firing_hours=4000.0,
            rated_cathode_lifetime_hours=8000.0,
        )
        self.assertAlmostEqual(report.erosion_fraction, 0.50, places=2)
        self.assertGreater(report.keeper_voltage_v, 14.5)
        self.assertGreater(report.mass_utilization_efficiency, 0.80)
        self.assertEqual(report.remaining_lifetime_hours, 4000.0)

    def test_sadm_stepping_disturbance_torque(self):
        desat = ReactionWheelDesaturator()
        peak_t, ripple_h = desat.compute_sadm_stepping_disturbance(
            step_frequency_hz=1.0,
            step_angle_deg=0.015,
            sadm_inertia_kg_m2=5.0,
        )
        self.assertGreater(peak_t, 0.0)
        self.assertGreater(ripple_h, 0.0)


if __name__ == "__main__":
    unittest.main()
