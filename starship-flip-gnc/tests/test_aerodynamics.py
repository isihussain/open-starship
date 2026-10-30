import unittest
import math
from starship_flip_gnc.aerodynamics import Atmosphere, AerodynamicModel


class TestAerodynamics(unittest.TestCase):
    def setUp(self):
        self.atmos = Atmosphere()
        self.aero = AerodynamicModel()

    def test_atmosphere_density_at_sea_level_and_altitude(self):
        rho0 = self.atmos.density(0.0)
        self.assertAlmostEqual(rho0, 1.225)

        rho_high = self.atmos.density(8500.0)
        self.assertAlmostEqual(rho_high, 1.225 / math.e, places=3)

    def test_drag_variation_with_orientation(self):
        # Vertical flight (nose down / axial flow):
        forces_axial = self.aero.compute_forces(
            vx=0.0, vz=-70.0, theta=0.0, altitude=500.0, atmosphere=self.atmos
        )
        # Belly flop (cross flow):
        forces_belly = self.aero.compute_forces(
            vx=0.0, vz=-70.0, theta=math.pi / 2, altitude=500.0, atmosphere=self.atmos
        )

        # Cross-flow drag must be significantly greater than axial drag
        self.assertGreater(forces_belly["drag"], forces_axial["drag"] * 3.0)
        self.assertGreater(forces_belly["dynamic_pressure"], 0.0)
        self.assertGreater(forces_belly["heat_flux_w_m2"], 0.0)


if __name__ == "__main__":
    unittest.main()
