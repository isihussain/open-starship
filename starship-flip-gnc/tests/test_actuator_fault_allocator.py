import unittest
from starship_flip_gnc.actuator_fault_allocator import (
    ActuatorFaultAllocator,
    ActuatorTelemetry,
    TorqueDemand,
    AllocationResult,
)


class TestActuatorFaultAllocator(unittest.TestCase):
    def setUp(self):
        self.allocator = ActuatorFaultAllocator(
            divergence_threshold_rad=0.08,
            current_saturation_cycles_to_fault=3,
            reference_q_dyn_pa=10_000.0,
            max_rcs_torque_nm=50_000.0,
        )

    def test_nominal_control_allocation(self):
        # All 4 actuators responsive, low motor current
        telemetry = [
            ActuatorTelemetry("aft_port", 0.05, 0.048, 12.0),
            ActuatorTelemetry("aft_starboard", 0.05, 0.051, 11.5),
            ActuatorTelemetry("fwd_port", -0.02, -0.019, 9.0),
            ActuatorTelemetry("fwd_starboard", -0.02, -0.021, 8.8),
        ]
        demand = TorqueDemand(pitch_nm=12_000.0, yaw_nm=0.0, roll_nm=0.0)
        result = self.allocator.allocate(demand, q_dyn_pa=10_000.0, actuators=telemetry)

        self.assertEqual(len(result.jammed_surfaces), 0)
        self.assertTrue(result.reallocation_converged)
        self.assertIn("Nominal", result.status_message)
        self.assertAlmostEqual(result.parasitic_torque_nm[0], 0.0)

    def test_actuator_jam_detection_and_reallocation(self):
        # aft_port jams at 0.20 rad while commanded to return to 0.0 rad
        # motor current hits stall threshold (42 A > 40 A)
        telemetry = [
            ActuatorTelemetry("aft_port", 0.0, 0.20, 43.5),
            ActuatorTelemetry("aft_starboard", 0.0, 0.0, 10.0),
            ActuatorTelemetry("fwd_port", 0.0, 0.0, 8.5),
            ActuatorTelemetry("fwd_starboard", 0.0, 0.0, 9.2),
        ]
        demand = TorqueDemand(pitch_nm=0.0, yaw_nm=0.0, roll_nm=0.0)

        # Step 1 & 2: under threshold cycles, not yet flagged
        self.allocator.allocate(demand, 10_000.0, telemetry)
        self.allocator.allocate(demand, 10_000.0, telemetry)
        self.assertFalse(self.allocator.jammed_status["aft_port"])

        # Step 3: cycle 3 reaches fault threshold
        result = self.allocator.allocate(demand, 10_000.0, telemetry)
        self.assertTrue(self.allocator.jammed_status["aft_port"])
        self.assertIn("aft_port", result.jammed_surfaces)
        self.assertIn("FAULT MITIGATED", result.status_message)

        # Parasitic torque from aft_port jammed at 0.20 rad should be non-zero
        self.assertGreater(result.parasitic_torque_nm[0], 10_000.0)

        # Operational surfaces should deflect to counteract the jammed surface
        self.assertNotEqual(result.surface_commands_rad["aft_starboard"], 0.0)
        self.assertTrue(result.reallocation_converged)

    def test_total_surface_jam_triggers_rcs_handover(self):
        # Force all surfaces jammed
        for name in self.allocator.jammed_status:
            self.allocator.jammed_status[name] = True
            self.allocator.jammed_angles[name] = 0.0

        telemetry = [
            ActuatorTelemetry("aft_port", 0.0, 0.0, 45.0),
            ActuatorTelemetry("aft_starboard", 0.0, 0.0, 45.0),
            ActuatorTelemetry("fwd_port", 0.0, 0.0, 45.0),
            ActuatorTelemetry("fwd_starboard", 0.0, 0.0, 45.0),
        ]
        demand = TorqueDemand(pitch_nm=25_000.0, yaw_nm=-10_000.0, roll_nm=15_000.0)
        result = self.allocator.allocate(demand, 10_000.0, telemetry)

        self.assertEqual(len(result.jammed_surfaces), 4)
        self.assertIn("CRITICAL: All aerodynamic surfaces jammed", result.status_message)
        # RCS should take over the full torque demand
        self.assertAlmostEqual(result.rcs_assist_torque_nm[0], 25_000.0)
        self.assertAlmostEqual(result.rcs_assist_torque_nm[1], -10_000.0)
        self.assertAlmostEqual(result.rcs_assist_torque_nm[2], 15_000.0)


if __name__ == "__main__":
    unittest.main()
