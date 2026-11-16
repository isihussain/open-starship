"""
Unit tests for Loss-of-Signal (LOS) Autonomous Flight Control and Satellite Deployment Controller.
"""

import unittest
from starship_geo_sat.loss_of_signal_contingency import (
    LossOfSignalContingencyController,
    AntennaTelemetry,
    AscentInertialState,
    AFTSCorridorLimits,
)


class TestLossOfSignalContingency(unittest.TestCase):

    def setUp(self):
        self.controller = LossOfSignalContingencyController()

    def test_nominal_rf_communication(self):
        """Verify nominal RF status when telemetry link is active and valid."""
        rf = AntennaTelemetry(
            timestamp_s=120.0,
            primary_rf_active=True,
            secondary_rf_active=True,
            primary_snr_db=18.5,
            secondary_snr_db=16.2,
            last_uplink_heartbeat_s=119.8,
        )
        state = AscentInertialState(
            timestamp_s=120.0,
            altitude_m=45_000.0,
            downrange_km=85.0,
            crossrange_km=0.8,
            inertial_velocity_mps=1650.0,
            axial_acceleration_mps2=28.4,
            attitude_pitch_deg=42.0,
            attitude_yaw_rate_deg_s=0.1,
        )
        assessment = self.controller.evaluate(rf, state)

        self.assertFalse(assessment.loss_of_signal_confirmed)
        self.assertEqual(assessment.flight_mode, "NOMINAL_RF_SUPERVISED")
        self.assertFalse(assessment.ground_command_lockout_active)
        self.assertTrue(assessment.afts_corridor_cleared)
        self.assertFalse(assessment.afts_flight_termination_commanded)
        self.assertFalse(assessment.payload_separation_commanded)

    def test_total_antenna_failure_triggers_autonomous_ins(self):
        """Verify autonomous INS continuation and ground lockout when both antennas fail."""
        rf = AntennaTelemetry(
            timestamp_s=150.0,
            primary_rf_active=False,
            secondary_rf_active=False,
            primary_snr_db=-99.0,
            secondary_snr_db=-99.0,
            last_uplink_heartbeat_s=140.0,  # 10s outage > 3s threshold
        )
        state = AscentInertialState(
            timestamp_s=150.0,
            altitude_m=72_000.0,
            downrange_km=160.0,
            crossrange_km=1.2,
            inertial_velocity_mps=2400.0,
            axial_acceleration_mps2=32.1,
            attitude_pitch_deg=28.0,
            attitude_yaw_rate_deg_s=0.2,
        )
        assessment = self.controller.evaluate(rf, state)

        self.assertTrue(assessment.loss_of_signal_confirmed)
        self.assertEqual(assessment.flight_mode, "AUTONOMOUS_INS_MISSION_CONTINUATION")
        self.assertTrue(assessment.ground_command_lockout_active)
        self.assertTrue(assessment.afts_corridor_cleared)
        self.assertFalse(assessment.afts_flight_termination_commanded)
        self.assertEqual(assessment.uplink_outage_duration_s, 10.0)

    def test_afts_autonomous_termination_on_corridor_breach(self):
        """Verify AFTS independently terminates flight when crossrange boundary is breached."""
        rf = AntennaTelemetry(
            timestamp_s=180.0,
            primary_rf_active=False,
            secondary_rf_active=False,
            primary_snr_db=-99.0,
            secondary_snr_db=-99.0,
            last_uplink_heartbeat_s=170.0,
        )
        state = AscentInertialState(
            timestamp_s=180.0,
            altitude_m=95_000.0,
            downrange_km=250.0,
            crossrange_km=48.5,  # Exceeds 40 km limit
            inertial_velocity_mps=3100.0,
            axial_acceleration_mps2=25.0,
            attitude_pitch_deg=18.0,
            attitude_yaw_rate_deg_s=0.4,
        )
        assessment = self.controller.evaluate(rf, state)

        self.assertTrue(assessment.loss_of_signal_confirmed)
        self.assertEqual(assessment.flight_mode, "AFTS_AUTONOMOUS_TERMINATION")
        self.assertFalse(assessment.afts_corridor_cleared)
        self.assertTrue(assessment.afts_flight_termination_commanded)
        self.assertFalse(assessment.payload_separation_commanded)

    def test_afts_autonomous_termination_on_excessive_tumble(self):
        """Verify AFTS terminates flight if rocket tumbles during antenna blackout."""
        rf = AntennaTelemetry(
            timestamp_s=90.0,
            primary_rf_active=False,
            secondary_rf_active=False,
            primary_snr_db=-99.0,
            secondary_snr_db=-99.0,
            last_uplink_heartbeat_s=80.0,
        )
        state = AscentInertialState(
            timestamp_s=90.0,
            altitude_m=32_000.0,
            downrange_km=40.0,
            crossrange_km=2.0,
            inertial_velocity_mps=1100.0,
            axial_acceleration_mps2=18.0,
            attitude_pitch_deg=55.0,
            attitude_yaw_rate_deg_s=14.5,  # Exceeds 10.0 deg/s threshold
        )
        assessment = self.controller.evaluate(rf, state)

        self.assertEqual(assessment.flight_mode, "AFTS_AUTONOMOUS_TERMINATION")
        self.assertTrue(assessment.afts_flight_termination_commanded)

    def test_orbital_insertion_and_autonomous_payload_separation(self):
        """Verify orbital insertion criteria and autonomous payload release during total LOS."""
        rf = AntennaTelemetry(
            timestamp_s=520.0,
            primary_rf_active=False,
            secondary_rf_active=False,
            primary_snr_db=-99.0,
            secondary_snr_db=-99.0,
            last_uplink_heartbeat_s=480.0,
        )
        state = AscentInertialState(
            timestamp_s=520.0,
            altitude_m=185_000.0,
            downrange_km=1400.0,
            crossrange_km=3.5,
            inertial_velocity_mps=7820.0,  # Orbital insertion velocity
            axial_acceleration_mps2=0.0,   # SECO engine cutoff
            attitude_pitch_deg=0.0,
            attitude_yaw_rate_deg_s=0.02,
        )
        assessment = self.controller.evaluate(rf, state, post_sep_elapsed_s=0.0)

        self.assertTrue(assessment.loss_of_signal_confirmed)
        self.assertTrue(assessment.orbital_insertion_verified)
        self.assertTrue(assessment.payload_separation_commanded)
        self.assertTrue(assessment.satellite_microswitch_tripped)
        # Solar array deployment awaits drift clearance time
        self.assertFalse(assessment.satellite_solar_arrays_deployed)
        self.assertFalse(assessment.satellite_rf_carrier_active)
        self.assertGreater(assessment.specific_orbital_energy_mj_kg, -32.0)

    def test_satellite_autonomous_wake_and_solar_deployment(self):
        """Verify satellite deploys arrays and starts RF broadcast after separation coast."""
        rf = AntennaTelemetry(
            timestamp_s=1500.0,
            primary_rf_active=False,
            secondary_rf_active=False,
            primary_snr_db=-99.0,
            secondary_snr_db=-99.0,
            last_uplink_heartbeat_s=480.0,
        )
        state = AscentInertialState(
            timestamp_s=1500.0,
            altitude_m=190_000.0,
            downrange_km=5200.0,
            crossrange_km=4.1,
            inertial_velocity_mps=7810.0,
            axial_acceleration_mps2=0.0,
            attitude_pitch_deg=0.0,
            attitude_yaw_rate_deg_s=0.01,
        )
        # 950 seconds elapsed after separation (> 900s limit)
        assessment = self.controller.evaluate(rf, state, post_sep_elapsed_s=950.0)

        self.assertTrue(assessment.orbital_insertion_verified)
        self.assertTrue(assessment.payload_separation_commanded)
        self.assertTrue(assessment.satellite_microswitch_tripped)
        self.assertTrue(assessment.satellite_solar_arrays_deployed)
        self.assertTrue(assessment.satellite_rf_carrier_active)

    def test_degraded_snr_triggers_autonomous_mode(self):
        """Verify low SNR links transition to autonomous mode to ignore corrupted packets."""
        rf = AntennaTelemetry(
            timestamp_s=210.0,
            primary_rf_active=True,
            secondary_rf_active=True,
            primary_snr_db=-14.5,
            secondary_snr_db=-13.8,
            last_uplink_heartbeat_s=209.5,
        )
        state = AscentInertialState(
            timestamp_s=210.0,
            altitude_m=110_000.0,
            downrange_km=450.0,
            crossrange_km=1.8,
            inertial_velocity_mps=4200.0,
            axial_acceleration_mps2=29.0,
            attitude_pitch_deg=12.0,
            attitude_yaw_rate_deg_s=0.05,
        )
        assessment = self.controller.evaluate(rf, state)

        self.assertTrue(assessment.loss_of_signal_confirmed)
        self.assertEqual(assessment.flight_mode, "AUTONOMOUS_INS_MISSION_CONTINUATION")
        self.assertTrue(assessment.ground_command_lockout_active)


if __name__ == "__main__":
    unittest.main()
