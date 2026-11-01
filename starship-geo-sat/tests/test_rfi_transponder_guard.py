import unittest
from starship_geo_sat.rfi_transponder_guard import (
    RFITransponderGuard,
    CarrierTelemetry,
    TransponderState,
    PayloadGuardAction,
)


class TestRFITransponderGuard(unittest.TestCase):
    def setUp(self):
        self.transponder = TransponderState(
            transponder_name="Ku_TP_12A",
            twta_saturated_output_power_watts=120.0,
            input_backoff_db=3.0,
        )
        self.guard = RFITransponderGuard(transponder=self.transponder)

    def test_nominal_carrier_transmission(self):
        carrier = CarrierTelemetry(
            carrier_id="TR_DVB_S2_MUX1",
            frequency_ghz=12.25,
            polarization="V",
            measured_input_power_dbw=-75.0,
            cross_polar_leakage_power_dbw=-106.0,  # XPI = 31 dB > 25 dB
            rain_rate_mm_per_hr=0.0,
        )
        action = self.guard.evaluate_carrier(carrier)

        self.assertFalse(action.xpi_violation)
        self.assertFalse(action.twta_saturated)
        self.assertEqual(action.rain_attenuation_db, 0.0)
        self.assertEqual(action.aupc_recommended_boost_db, 0.0)
        self.assertEqual(action.intermodulation_risk, "LOW")
        self.assertIn("nominal", action.status_message)

    def test_cross_polarization_interference_violation(self):
        # Ground dish mispointing leaks power into orthogonal channel (XPI = 18 dB < 25 dB)
        carrier = CarrierTelemetry(
            carrier_id="ROGUE_UPLINK_02",
            frequency_ghz=12.25,
            polarization="V",
            measured_input_power_dbw=-74.0,
            cross_polar_leakage_power_dbw=-92.0,  # XPI = 18 dB
            rain_rate_mm_per_hr=0.0,
        )
        action = self.guard.evaluate_carrier(carrier)

        self.assertTrue(action.xpi_violation)
        self.assertLess(action.cross_polar_isolation_db, 25.0)
        self.assertIn("XPI violation", action.status_message)

    def test_ka_band_rain_fade_aupc_compensation(self):
        # 30 GHz Ka-band uplink during heavy convective rain (45 mm/hr)
        carrier = CarrierTelemetry(
            carrier_id="ANKARA_KA_GW01",
            frequency_ghz=29.5,
            polarization="H",
            measured_input_power_dbw=-76.0,
            cross_polar_leakage_power_dbw=-105.0,
            rain_rate_mm_per_hr=45.0,
        )
        action = self.guard.evaluate_carrier(carrier)

        self.assertGreater(action.rain_attenuation_db, 8.0)
        self.assertGreater(action.aupc_recommended_boost_db, 8.0)
        self.assertIn("rain fade", action.status_message)

    def test_twta_saturation_and_intermodulation_risk(self):
        # High power rogue carrier pushes TWTA into saturation (P_in = -68 dBW vs P_sat_in = -72 dBW)
        carrier = CarrierTelemetry(
            carrier_id="OVERPOWER_TX",
            frequency_ghz=14.0,
            polarization="V",
            measured_input_power_dbw=-68.0,
            cross_polar_leakage_power_dbw=-100.0,
        )
        action = self.guard.evaluate_carrier(carrier)

        self.assertTrue(action.twta_saturated)
        self.assertEqual(action.intermodulation_risk, "CRITICAL")
        self.assertIn("TWTA saturated", action.status_message)


if __name__ == "__main__":
    unittest.main()
