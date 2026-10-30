import unittest
from starship_cryo_slosh.tank import CryogenicFluid
from starship_cryo_slosh.orbital_transfer import (
    TransferConfiguration,
    OrbitalTransferSimulator,
)


class TestOrbitalTransfer(unittest.TestCase):
    def setUp(self):
        self.sim = OrbitalTransferSimulator()
        self.lox = CryogenicFluid.liquid_oxygen()
        self.ch4 = CryogenicFluid.liquid_methane()

    def test_bond_number_settling_evaluation(self):
        bo, is_settled = self.sim.evaluate_bond_number(tank_radius_m=4.5, fluid=self.lox)
        self.assertGreater(bo, 50.0)
        self.assertTrue(is_settled)

    def test_lox_propellant_transfer(self):
        res = self.sim.simulate_transfer(fluid=self.lox, target_mass_kg=50_000.0)
        self.assertTrue(res.success)
        self.assertEqual(res.mass_transferred_kg, 50_000.0)
        self.assertGreater(res.average_flow_rate_kg_s, 50.0)
        self.assertGreater(res.transfer_efficiency_percent, 95.0)

    def test_zero_delta_p_transfer_failure(self):
        bad_config = TransferConfiguration(
            tanker_ullage_pressure_kpa=200.0,
            depot_ullage_pressure_kpa=250.0,  # Negative delta P
        )
        bad_sim = OrbitalTransferSimulator(config=bad_config)
        res = bad_sim.simulate_transfer(fluid=self.ch4, target_mass_kg=20_000.0)
        self.assertFalse(res.success)
        self.assertIn("exceed", res.message)


if __name__ == "__main__":
    unittest.main()
