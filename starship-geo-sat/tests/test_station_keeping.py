import unittest
from starship_geo_sat.station_keeping_prognostics import (
    StationKeepingPrognosticator,
    StationKeepingConfig,
    TankPVTReading,
    StationKeepingBudget,
    LifetimePrognosisReport,
)


class TestStationKeepingPrognostics(unittest.TestCase):
    def setUp(self):
        self.chem_config = StationKeepingConfig(
            slot_longitude_deg=42.0,  # Türksat slot
            dry_mass_kg=2200.0,
            current_propellant_kg=280.0,
            thruster_isp_s=310.0,
            solar_array_area_m2=40.0,
            radiation_pressure_cr=1.30,
        )
        self.prognosticator = StationKeepingPrognosticator(self.chem_config)

    def test_annual_station_keeping_budget(self):
        budget = self.prognosticator.compute_annual_budget()
        self.assertGreater(budget.annual_total_dv_ms, 48.0)
        self.assertLess(budget.annual_total_dv_ms, 58.0)
        self.assertGreater(budget.annual_propellant_consumption_kg, 25.0)

    def test_triaxial_ewsk_variation(self):
        ewsk_42e = self.prognosticator.calculate_triaxial_ewsk_requirement(42.0)
        ewsk_75e = self.prognosticator.calculate_triaxial_ewsk_requirement(75.1)
        self.assertGreaterEqual(ewsk_42e, 1.5)
        self.assertLessEqual(ewsk_42e, 6.0)
        self.assertGreaterEqual(ewsk_75e, 1.5)

    def test_pvt_propellant_gauging(self):
        reading = TankPVTReading(
            tank_pressure_bar=18.5,
            propellant_temp_k=293.15,
            tank_volume_m3=0.85,
            helium_mass_kg=1.20,
            propellant_density_kg_m3=1180.0,
        )
        mass_pvt = self.prognosticator.gauge_propellant_pvt(reading)
        self.assertGreater(mass_pvt, 100.0)
        self.assertLess(mass_pvt, 1000.0)

    def test_graveyard_disposal_requirements(self):
        delta_r_km, delta_v_grave, reserve_kg = (
            self.prognosticator.evaluate_graveyard_disposal_requirements()
        )
        self.assertGreater(delta_r_km, 235.0)
        self.assertGreater(delta_v_grave, 9.0)
        self.assertLess(delta_v_grave, 14.0)
        self.assertGreater(reserve_kg, 7.0)

    def test_healthy_mission_lifetime(self):
        report = self.prognosticator.forecast_mission_lifetime()
        self.assertEqual(report.eol_status, "HEALTHY_EXPEDITION")
        self.assertGreater(report.remaining_lifetime_years, 4.0)
        self.assertGreater(report.usable_propellant_kg, 200.0)

    def test_eol_warning_and_immediate_disposal(self):
        low_fuel_config = StationKeepingConfig(
            slot_longitude_deg=13.0,
            dry_mass_kg=2200.0,
            current_propellant_kg=35.0,  # Near graveyard reserve
            thruster_isp_s=310.0,
        )
        low_prog = StationKeepingPrognosticator(low_fuel_config)
        report_low = low_prog.forecast_mission_lifetime()
        self.assertEqual(report_low.eol_status, "EOL_WARNING_UNDER_2_YEARS")

        exhausted_config = StationKeepingConfig(
            slot_longitude_deg=13.0,
            dry_mass_kg=2200.0,
            current_propellant_kg=5.0,   # Fuel depleted below graveyard reserve
            thruster_isp_s=310.0,
        )
        exh_prog = StationKeepingPrognosticator(exhausted_config)
        report_exh = exh_prog.forecast_mission_lifetime()
        self.assertEqual(report_exh.eol_status, "IMMEDIATE_GRAVEYARD_DISPOSAL_REQUIRED")
        self.assertEqual(report_exh.remaining_lifetime_years, 0.0)

    def test_electric_propulsion_efficiency(self):
        electric_config = StationKeepingConfig(
            slot_longitude_deg=13.0,
            dry_mass_kg=2500.0,
            current_propellant_kg=280.0,
            thruster_isp_s=1800.0,  # Hall thruster (Eurostar Neo / Türksat 5A/5B)
            is_electric_propulsion=True,
        )
        electric_prog = StationKeepingPrognosticator(electric_config)
        chem_budget = self.prognosticator.compute_annual_budget()
        electric_budget = electric_prog.compute_annual_budget()

        # Electric propulsion consumes far less propellant mass annually
        self.assertLess(
            electric_budget.annual_propellant_consumption_kg,
            chem_budget.annual_propellant_consumption_kg * 0.25,
        )


if __name__ == "__main__":
    unittest.main()
