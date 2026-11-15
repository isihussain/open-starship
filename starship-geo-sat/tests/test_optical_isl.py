import unittest
from starship_geo_sat.optical_isl_crosslink import (
    OpticalISLTransceiver,
    OpticalISLConfig,
    JitterSpectrumProfile,
    OpticalLinkReport,
)


class TestOpticalISLTransceiver(unittest.TestCase):
    def setUp(self):
        self.config = OpticalISLConfig(
            wavelength_nm=1550.0,
            tx_power_w=3.0,
            tx_aperture_dia_m=0.15,
            rx_aperture_dia_m=0.15,
            optics_efficiency=0.65,
            data_rate_gbps=2.5,
        )
        self.transceiver = OpticalISLTransceiver(self.config)

    def test_carrier_frequency_and_aperture_gain(self):
        self.assertAlmostEqual(self.transceiver.carrier_freq_hz * 1e-12, 193.414, places=2)
        gain_lin, gain_dbi = self.transceiver.compute_aperture_gain(0.15)
        self.assertGreater(gain_dbi, 105.0)  # Over 105 dBi
        theta_urad = self.transceiver.compute_beam_divergence_urad(0.15)
        self.assertLess(theta_urad, 20.0)    # Less than 20 microradians

    def test_pointing_loss_micro_radian(self):
        loss_tight = self.transceiver.calculate_pointing_loss_db(1.0, 0.15)
        loss_loose = self.transceiver.calculate_pointing_loss_db(6.0, 0.15)
        self.assertLessEqual(loss_tight, 0.0)
        self.assertLess(loss_loose, loss_tight)  # More negative (higher attenuation)

    def test_reaction_wheel_jitter_generation(self):
        jitter_profile = self.transceiver.compute_reaction_wheel_jitter(
            wheel_rpm=4000.0,
            static_imbalance_g_mm=3.0,
        )
        self.assertGreater(jitter_profile.rms_jitter_urad, 1.0)
        self.assertGreater(jitter_profile.structural_amplification_q, 5.0)

    def test_optical_doppler_shift(self):
        shift_stationary = self.transceiver.calculate_optical_doppler_ghz(0.0)
        shift_relative = self.transceiver.calculate_optical_doppler_ghz(3.5)
        self.assertEqual(shift_stationary, 0.0)
        self.assertGreater(shift_relative, 2.0)  # > 2 GHz Doppler shift at 3.5 km/s

    def test_nominal_crosslink_budget(self):
        report = self.transceiver.evaluate_link_budget(
            distance_km=4500.0,
            relative_velocity_km_s=2.8,
            pointing_jitter_urad=1.8,
        )
        self.assertEqual(report.link_status, "LINK_CLOSED")
        self.assertGreater(report.link_margin_db, 3.0)
        self.assertLess(report.estimated_ber, 1e-8)
        self.assertGreater(report.carrier_frequency_thz, 190.0)

    def test_extreme_range_link_degradation(self):
        report = self.transceiver.evaluate_link_budget(
            distance_km=75000.0,
            relative_velocity_km_s=7.0,
            pointing_jitter_urad=8.5,
        )
        self.assertIn(report.link_status, ["ACQUISITION_LOSS", "MARGIN_DEGRADED"])
        self.assertLess(report.link_margin_db, 2.0)


if __name__ == "__main__":
    unittest.main()
