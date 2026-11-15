"""
Unit tests for Cryo-Slosh enhancements:
  - Second-harmonic (m=2) slosh pendulum acceleration
  - Annular ring baffle damping ratio calculation
  - Ullage self-pressurization & boil-off pressure rise model
  - Transfer line chill-down transient & vapor lock prevention
  - Multi-modal propellant mass gauging sensor fusion
"""

import unittest
from starship_cryo_slosh.tank import (
    HeaderTankGeometry,
    CryogenicFluid,
    UllageThermodynamicsModel,
)
from starship_cryo_slosh.pendulum_model import (
    EquivalentSloshModel,
    DualModeSloshState,
)
from starship_cryo_slosh.orbital_transfer import (
    OrbitalTransferSimulator,
    TransferConfiguration,
)
from starship_cryo_slosh.simulator import MultiModalPropellantGaugingModel


class TestSloshEnhancements(unittest.TestCase):
    def setUp(self):
        self.tank = HeaderTankGeometry(
            radius_m=1.55,
            z_position_vehicle_m=21.0,
            suction_inlet_z_local_m=-1.45,
            has_slosh_baffles=True,
        )
        self.fluid = CryogenicFluid.liquid_oxygen()
        self.model = EquivalentSloshModel(self.tank, self.fluid, initial_fluid_mass_kg=15_000.0)

    def test_dual_mode_slosh_acceleration(self):
        state = DualModeSloshState(
            phi1_rad=0.10,
            phi1_dot_rad_s=0.20,
            phi2_rad=0.04,
            phi2_dot_rad_s=0.10,
        )
        phi1_ddot, phi2_ddot = self.model.compute_dual_mode_accelerations(
            state=state,
            accel_lateral_mps2=1.5,
            accel_axial_mps2=12.0,
            vehicle_pitch_rate_deg_s=2.0,
        )
        self.assertIsInstance(phi1_ddot, float)
        self.assertIsInstance(phi2_ddot, float)
        # Higher mode has higher restoring and damping rates:
        self.assertNotEqual(phi1_ddot, 0.0)
        self.assertNotEqual(phi2_ddot, 0.0)

    def test_annular_baffle_damping_ratio(self):
        # With baffles enabled:
        damping = self.tank.compute_baffle_damping(fill_fraction=0.50)
        # Baffles should increase hydrodynamic damping above smooth wall baseline (0.018):
        self.assertGreater(damping, 0.018)

        # Clean wall tank:
        clean_tank = HeaderTankGeometry(
            radius_m=1.55,
            z_position_vehicle_m=21.0,
            suction_inlet_z_local_m=-1.45,
            has_slosh_baffles=False,
        )
        self.assertEqual(clean_tank.compute_baffle_damping(fill_fraction=0.50), 0.018)

    def test_ullage_self_pressurization(self):
        thermo = UllageThermodynamicsModel(
            tank=self.tank,
            fluid=self.fluid,
            ambient_heat_leak_w=400.0,
            relief_valve_limit_kpa=450.0,
        )
        report = thermo.evaluate_pressurization(fluid_mass_kg=12_000.0, current_pressure_kpa=280.0)
        self.assertGreater(report.pressure_rise_rate_kpa_per_s, 0.0)
        self.assertGreater(report.time_to_vent_relief_s, 10.0)
        self.assertGreater(report.boil_off_rate_kg_s, 0.0)

    def test_transfer_line_chilldown_evaluation(self):
        sim = OrbitalTransferSimulator()
        report = sim.evaluate_line_chilldown(
            fluid=self.fluid,
            line_length_m=10.0,
            pipe_initial_temp_k=295.0,
        )
        self.assertGreater(report.pipe_mass_kg, 10.0)
        self.assertGreater(report.chilldown_energy_joules, 1.0e5)
        self.assertGreater(report.cryogen_boiloff_for_chill_kg, 0.5)
        self.assertTrue(report.vapor_lock_cleared)

    def test_multimodal_propellant_gauging_fusion(self):
        gauging = MultiModalPropellantGaugingModel(
            tank_volume_m3=15.6,
            propellant_density_kg_m3=1141.0,
            pvt_sigma_percent=4.0,
            capacitive_sigma_percent=1.8,
        )
        pvt_reading = 14_800.0
        cap_reading = 15_100.0
        estimate = gauging.fuse_gauging_estimate(pvt_mass_kg=pvt_reading, capacitive_mass_kg=cap_reading)
        # Fused estimate should fall between the two readings:
        self.assertGreater(estimate.fused_mass_kg, min(pvt_reading, cap_reading))
        self.assertLess(estimate.fused_mass_kg, max(pvt_reading, cap_reading))
        # Fused uncertainty is strictly less than either individual sensor uncertainty:
        self.assertLess(estimate.uncertainty_percent, 1.8)
        self.assertTrue(estimate.sensor_concordance)


if __name__ == "__main__":
    unittest.main()
