import unittest
import math
from starship_flip_gnc.aerodynamics import Atmosphere, AerodynamicModel, WindModel


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

    def test_wind_model_shear_profile(self):
        wind = WindModel(ref_wind_speed=10.0, ref_altitude=10.0, shear_exponent=0.14)
        wx_low, wz_low = wind.compute_wind(altitude_m=10.0, time_s=0.0)
        wx_high, wz_high = wind.compute_wind(altitude_m=100.0, time_s=0.0)

        self.assertAlmostEqual(wx_low, 10.0, places=3)
        self.assertGreater(wx_high, wx_low)
        self.assertEqual(wz_low, 0.0)

    def test_wind_model_discrete_gust(self):
        wind = WindModel(
            ref_wind_speed=0.0,
            gust_amplitude=15.0,
            gust_start_time=2.0,
            gust_duration=4.0
        )
        # Before gust:
        w_before, _ = wind.compute_wind(altitude_m=50.0, time_s=1.0)
        self.assertEqual(w_before, 0.0)

        # Peak of gust at midpoint (t = 4.0s, delta = 2.0s = T/2, 1 - cos(pi) = 2 -> speed = A):
        w_peak, _ = wind.compute_wind(altitude_m=50.0, time_s=4.0)
        self.assertAlmostEqual(w_peak, 15.0, places=3)

        # After gust:
        w_after, _ = wind.compute_wind(altitude_m=50.0, time_s=7.0)
        self.assertEqual(w_after, 0.0)

    def test_aerodynamic_forces_with_crosswind(self):
        # Stationary vehicle falling straight down at -50 m/s with 20 m/s crosswind in +X
        forces_no_wind = self.aero.compute_forces(
            vx=0.0, vz=-50.0, theta=0.0, altitude=200.0, atmosphere=self.atmos,
            wind_vx=0.0, wind_vz=0.0
        )
        forces_with_wind = self.aero.compute_forces(
            vx=0.0, vz=-50.0, theta=0.0, altitude=200.0, atmosphere=self.atmos,
            wind_vx=20.0, wind_vz=0.0
        )

        # Crosswind must create a lateral aerodynamic force
        self.assertEqual(forces_no_wind["fx_aero"], 0.0)
        self.assertNotEqual(forces_with_wind["fx_aero"], 0.0)
        self.assertGreater(forces_with_wind["dynamic_pressure"], forces_no_wind["dynamic_pressure"])


if __name__ == "__main__":
    unittest.main()
