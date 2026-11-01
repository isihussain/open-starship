import unittest
from starship_geo_sat.electric_orbit_raising import (
    ElectricOrbitRaisingSimulator,
    EORThrusterConfig,
    SolarArraySpec,
    EORProgressReport,
)


class TestElectricOrbitRaisingSimulator(unittest.TestCase):
    def setUp(self):
        self.thruster = EORThrusterConfig(
            total_thrust_n=0.45,
            specific_impulse_s=1650.0,
            duty_cycle_fraction=0.92,
            initial_wet_mass_kg=3500.0,
        )
        self.array = SolarArraySpec(
            bol_power_watts=12_000.0,
            radiation_damage_coefficient=0.048,
        )
        self.sim = ElectricOrbitRaisingSimulator(
            thruster=self.thruster,
            array=self.array,
        )

    def test_spiral_transfer_progress_and_radiation_damage(self):
        # Run a 20-day snapshot with 5-day steps
        history = self.sim.simulate_transfer(
            gto_perigee_km=250.0,
            gto_apogee_km=35_786.0,
            gto_inclination_deg=27.0,
            simulation_step_days=5.0,
            max_duration_days=25.0,
        )

        self.assertGreater(len(history), 2)
        first_step = history[0]
        last_step = history[-1]

        # Perigee should rise as orbit circularizes
        self.assertGreater(last_step.current_perigee_altitude_km, first_step.current_perigee_altitude_km)
        # Fuel consumed should increase
        self.assertGreater(last_step.propellant_consumed_kg, first_step.propellant_consumed_kg)
        # Radiation damage accumulates and reduces solar array power
        self.assertGreater(last_step.cumulative_1mev_fluence, 0.0)
        self.assertLess(last_step.solar_array_power_watts, self.array.bol_power_watts)
        self.assertGreater(last_step.power_degradation_percent, 0.0)

    def test_belt_fluence_rate_peaking(self):
        # Check that peak fluence occurs near inner and outer belt altitudes
        rate_low = self.sim._estimate_belt_fluence_rate(300.0)       # Low LEO
        rate_inner = self.sim._estimate_belt_fluence_rate(3000.0)    # Inner proton belt peak
        rate_outer = self.sim._estimate_belt_fluence_rate(20_000.0)  # Outer electron belt peak
        rate_geo = self.sim._estimate_belt_fluence_rate(35_786.0)    # GEO altitude

        self.assertGreater(rate_inner, rate_low)
        self.assertGreater(rate_outer, rate_geo)


if __name__ == "__main__":
    unittest.main()
