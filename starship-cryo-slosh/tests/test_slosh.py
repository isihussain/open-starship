import unittest
import math
from starship_cryo_slosh.tank import HeaderTankGeometry, CryogenicFluid
from starship_cryo_slosh.pendulum_model import EquivalentSloshModel, SloshState


class TestSloshModel(unittest.TestCase):
    def setUp(self):
        self.tank = HeaderTankGeometry(
            radius_m=1.5,
            z_position_vehicle_m=20.0,
            suction_inlet_z_local_m=-1.4,
            intake_submergence_threshold_m=0.15,
        )
        self.fluid = CryogenicFluid.liquid_oxygen()
        self.model = EquivalentSloshModel(
            tank=self.tank,
            fluid=self.fluid,
            initial_fluid_mass_kg=15000.0,
        )

    def test_pendulum_properties(self):
        self.assertGreater(self.model.m1, 0.0)
        self.assertGreater(self.model.m0, self.model.m1)
        self.assertGreater(self.model.arm_length_lp, 0.1)

    def test_quiescent_inlet_submergence(self):
        # Resting state (phi = 0):
        state = SloshState(phi_rad=0.0, phi_dot_rad_s=0.0)
        submergence, is_ingested = self.model.evaluate_inlet_submergence(state)
        self.assertGreater(submergence, self.tank.intake_submergence_threshold_m)
        self.assertFalse(is_ingested)

    def test_extreme_slosh_causes_gas_ingestion(self):
        # At landing residual propellant levels (~4000 kg LOX in header tank),
        # high slosh deflection during flip uncovers bottom suction pipe:
        model_low_prop = EquivalentSloshModel(
            tank=self.tank,
            fluid=self.fluid,
            initial_fluid_mass_kg=4000.0,
        )
        state_extreme = SloshState(phi_rad=math.radians(60.0), phi_dot_rad_s=0.0)
        submergence, is_ingested = model_low_prop.evaluate_inlet_submergence(state_extreme)
        self.assertTrue(is_ingested)

    def test_acceleration_and_torque_generation(self):
        state = SloshState(phi_rad=math.radians(10.0), phi_dot_rad_s=0.2)
        phi_ddot = self.model.compute_acceleration(
            state, accel_lateral_mps2=5.0, accel_axial_mps2=15.0, vehicle_pitch_rate_deg_s=10.0
        )
        f_lat, f_ax, torque = self.model.compute_slosh_forces_and_torques(
            state, phi_ddot, accel_lateral=5.0, accel_axial=15.0
        )
        self.assertNotEqual(torque, 0.0)


if __name__ == "__main__":
    unittest.main()
