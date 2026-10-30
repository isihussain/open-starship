import unittest
from starship_cryo_slosh.simulator import SloshSimulator


class TestTelemetryCoupling(unittest.TestCase):
    def test_simulation_over_synthetic_profile(self):
        records = []
        # Generate 5 seconds of flip and vertical settling data:
        for i in range(100):
            t = i * 0.05
            # Flip occurs in first 2 seconds with high lateral acceleration:
            if t < 2.0:
                a_lat = 12.0 * (1.0 - t / 2.0)
                a_ax = 15.0
                w = 30.0 * (1.0 - t / 2.0)
            else:
                a_lat = 0.5
                a_ax = 10.0
                w = 0.0

            records.append({
                "time_s": t,
                "altitude_m": max(1.0, 400.0 - 50.0 * t),
                "pitch_rate_deg_s": w,
                "accel_lateral_mps2": a_lat,
                "accel_axial_mps2": a_ax,
                "total_mass_kg": 120_000.0,
            })

        sim = SloshSimulator()
        result, history = sim.simulate_telemetry(records)

        self.assertEqual(len(history), 99)
        self.assertIn(result.risk_level, ["SAFE", "WARNING", "CRITICAL_CAVITATION"])
        self.assertGreater(result.max_slosh_torque_nm, 0.0)
        self.assertGreater(result.max_com_shift_x_mm, 0.0)


if __name__ == "__main__":
    unittest.main()
