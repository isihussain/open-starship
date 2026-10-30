import unittest
from starship_cryo_slosh.tank import HeaderTankGeometry, CryogenicFluid, HeaderTankAssembly


class TestTank(unittest.TestCase):
    def test_cryogenic_fluid_properties(self):
        lox = CryogenicFluid.liquid_oxygen()
        ch4 = CryogenicFluid.liquid_methane()

        self.assertAlmostEqual(lox.density_kg_m3, 1141.0)
        self.assertAlmostEqual(ch4.density_kg_m3, 422.0)
        self.assertGreater(lox.density_kg_m3, ch4.density_kg_m3)

    def test_header_tank_geometry_and_baffles(self):
        tank_clean = HeaderTankGeometry(
            radius_m=1.5,
            z_position_vehicle_m=20.0,
            suction_inlet_z_local_m=-1.4,
            has_slosh_baffles=False,
        )
        tank_baffled = HeaderTankGeometry(
            radius_m=1.5,
            z_position_vehicle_m=20.0,
            suction_inlet_z_local_m=-1.4,
            has_slosh_baffles=True,
        )

        self.assertGreater(tank_clean.total_volume_m3, 14.0)
        self.assertGreater(tank_baffled.damping_ratio, tank_clean.damping_ratio * 4.0)

    def test_default_assembly(self):
        assembly = HeaderTankAssembly.default_starship()
        self.assertAlmostEqual(assembly.lox_tank.radius_m, 1.55)
        self.assertAlmostEqual(assembly.ch4_tank.radius_m, 1.60)
        self.assertGreater(assembly.lox_tank.z_position_vehicle_m, assembly.ch4_tank.z_position_vehicle_m)


if __name__ == "__main__":
    unittest.main()
