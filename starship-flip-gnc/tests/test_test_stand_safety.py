import unittest
from starship_flip_gnc.test_stand_safety import (
    TestStandSafetyInterlock,
    TestStandMode,
    HoldDownSensorReading,
)


class TestTestStandSafety(unittest.TestCase):
    def setUp(self):
        self.guard = TestStandSafetyInterlock(mode=TestStandMode.STATIC_FIRE)

    def test_nominal_static_fire(self):
        reading = HoldDownSensorReading(
            timestamp_s=2.5,
            vertical_acceleration_mps2=0.02,
            vertical_displacement_m=0.005,
            clamp_tension_force_n=5.5e6,
            umbilical_connected=True,
            engine_commanded_thrust_n=6.0e6,
        )
        status = self.guard.evaluate(reading)
        self.assertTrue(status.safe)
        self.assertFalse(status.abort_triggered)
        self.assertFalse(status.emergency_cutoff)

    def test_premature_liftoff_breakaway_abort(self):
        # Clamp breaks, vehicle begins accelerating upward off test stool
        reading = HoldDownSensorReading(
            timestamp_s=3.0,
            vertical_acceleration_mps2=1.45,  # Exceeds 0.50 m/s^2 limit
            vertical_displacement_m=0.055,    # 55 mm > 30 mm limit
            clamp_tension_force_n=2.0e5,      # Clamp tension collapsed
            umbilical_connected=False,        # Umbilical pulled
            engine_commanded_thrust_n=6.5e6,
        )
        status = self.guard.evaluate(reading)
        self.assertFalse(status.safe)
        self.assertTrue(status.abort_triggered)
        self.assertTrue(status.emergency_cutoff)
        self.assertTrue(status.vent_valves_open)
        self.assertIn("Upward acceleration", status.message)

    def test_flight_authorized_mode_bypasses_hold_down_limits(self):
        flight_guard = TestStandSafetyInterlock(mode=TestStandMode.FLIGHT_AUTHORIZED)
        reading = HoldDownSensorReading(
            timestamp_s=0.1,
            vertical_acceleration_mps2=12.0,  # Nominal flight ascent acceleration
            vertical_displacement_m=5.0,
            clamp_tension_force_n=0.0,
            umbilical_connected=False,
            engine_commanded_thrust_n=6.5e6,
        )
        status = flight_guard.evaluate(reading)
        self.assertTrue(status.safe)
        self.assertFalse(status.abort_triggered)


if __name__ == "__main__":
    unittest.main()
