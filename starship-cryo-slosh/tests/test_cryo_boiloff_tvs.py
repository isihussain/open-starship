import unittest
from starship_cryo_slosh.cryo_boiloff_tvs import (
    CryoFluidProperties,
    MLISpec,
    DepotThermalState,
    DepotStorageReport,
    CryoBoiloffTVSSimulator,
)


class TestCryoBoiloffTVS(unittest.TestCase):
    def setUp(self):
        self.lox = CryoFluidProperties.liquid_oxygen()
        self.lch4 = CryoFluidProperties.liquid_methane()
        self.mli = MLISpec(layer_count=50, tank_surface_area_m2=150.0)
        self.sim = CryoBoiloffTVSSimulator(
            fluid=self.lox,
            mli_spec=self.mli,
            tank_volume_m3=60.0,
            target_pressure_bar=2.0,
            pressure_deadband_bar=0.15,
            relief_pressure_bar=2.80,
        )

    def test_mli_heat_flux_scaling(self):
        flux_50 = self.sim.calculate_mli_heat_flux_w_m2(90.18)
        sim_low_layers = CryoBoiloffTVSSimulator(
            mli_spec=MLISpec(layer_count=15, tank_surface_area_m2=150.0)
        )
        flux_15 = sim_low_layers.calculate_mli_heat_flux_w_m2(90.18)

        self.assertGreater(flux_50, 0.0)
        self.assertLess(flux_50, flux_15)  # More layers -> lower heat leak

    def test_structural_strut_heat_conduction(self):
        q_strut = self.sim.calculate_strut_conduction_watts(90.18)
        self.assertGreater(q_strut, 5.0)   # Over 5W
        self.assertLess(q_strut, 100.0)

    def test_saturation_pressure_clausius_clapeyron(self):
        p_sat = self.sim.compute_saturation_pressure_bar(self.lox.saturation_temp_k)
        self.assertAlmostEqual(p_sat, 1.013, delta=0.05)

        t_back = self.sim.compute_temperature_from_pressure_k(1.013)
        self.assertAlmostEqual(t_back, self.lox.saturation_temp_k, delta=0.2)

    def test_passive_storage_pressure_rise(self):
        # 10 days passive uncooled storage
        report = self.sim.simulate_storage(
            duration_days=10.0,
            enable_tvs=False,
            initial_pressure_bar=1.4,
            dt_seconds=3600.0,
        )
        self.assertGreater(report.max_tank_pressure_bar, 1.4)
        self.assertEqual(report.storage_outcome, "PASSIVE_STORAGE_UNCOOLED")

    def test_tvs_active_pressure_stabilization(self):
        # 14 days active TVS storage
        report = self.sim.simulate_storage(
            duration_days=14.0,
            enable_tvs=True,
            initial_pressure_bar=1.8,
            dt_seconds=1800.0,
        )
        self.assertEqual(report.storage_outcome, "NOMINAL_TVS_REGULATED")
        self.assertFalse(report.relief_valve_tripped)
        self.assertLess(report.max_tank_pressure_bar, self.sim.p_relief)
        self.assertGreater(report.final_propellant_kg, report.initial_propellant_kg * 0.95)

    def test_boiloff_loss_rate_comparison(self):
        report = self.sim.simulate_storage(
            duration_days=7.0,
            enable_tvs=True,
            initial_pressure_bar=1.9,
            dt_seconds=1800.0,
        )
        # Active TVS boiloff is less than 1.5% over a week
        self.assertLess(report.boiloff_loss_percent, 1.5)

    def test_lox_vs_lch4_thermal_storage(self):
        sim_methane = CryoBoiloffTVSSimulator(
            fluid=self.lch4,
            mli_spec=self.mli,
            tank_volume_m3=60.0,
        )
        report_methane = sim_methane.simulate_storage(
            duration_days=5.0,
            enable_tvs=True,
            initial_pressure_bar=1.8,
            dt_seconds=1800.0,
        )
        self.assertEqual(report_methane.fluid_name, "LCH4")
        self.assertEqual(report_methane.storage_outcome, "NOMINAL_TVS_REGULATED")


if __name__ == "__main__":
    unittest.main()
