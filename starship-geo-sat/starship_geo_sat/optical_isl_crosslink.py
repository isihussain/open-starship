"""
Optical Inter-Satellite Link (OISL) transceiver and PAT tracking loop simulator.

Models space optical communication cross-links (Starlink Gen2, SDA Tranche, EDRS, GEO relays):
  - 1550 nm C-band Erbium-Doped Fiber Amplifier (EDFA) link budget
  - Micro-radian (urad) Fast Steering Mirror (FSM) pointing jitter rejection
  - Reaction wheel micro-vibration harmonic structural disturbance propagation
  - Orbital relative velocity optical Doppler shift calculation (GHz scale)
  - Receiver photon sensitivity and Bit Error Rate (BER) evaluation
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import math


@dataclass
class OpticalISLConfig:
    """Hardware parameters for laser communication terminal (LCT)."""
    wavelength_nm: float = 1550.0            # C-band telecom laser (nm)
    tx_power_w: float = 3.0                  # Optical laser output power (W)
    tx_aperture_dia_m: float = 0.15          # Transmitter telescope primary diameter (m)
    rx_aperture_dia_m: float = 0.15          # Receiver telescope primary diameter (m)
    optics_efficiency: float = 0.65          # Optical train efficiency (couplers, mirrors)
    data_rate_gbps: float = 2.5              # Transmission data rate (Gbps)
    receiver_sensitivity_photons_per_bit: float = 65.0  # APD/coherent detector threshold


@dataclass
class JitterSpectrumProfile:
    """Satellite bus micro-vibration disturbance spectrum."""
    wheel_speed_rpm: float
    static_imbalance_g_mm: float             # Dynamic balance quality
    structural_amplification_q: float        # Q-factor at mounting interface
    rms_jitter_urad: float                   # Net pointing jitter in microradians


@dataclass
class OpticalLinkReport:
    """End-to-end optical communication link evaluation."""
    link_distance_km: float
    relative_velocity_km_s: float
    carrier_frequency_thz: float
    transmitter_gain_dbi: float
    free_space_path_loss_db: float
    pointing_jitter_urad: float
    pointing_loss_db: float
    received_optical_power_dbm: float
    receiver_sensitivity_dbm: float
    link_margin_db: float
    doppler_frequency_shift_ghz: float
    estimated_ber: float
    link_status: str                         # "LINK_CLOSED", "MARGIN_DEGRADED", "ACQUISITION_LOSS"


class OpticalISLTransceiver:
    """
    Evaluates free-space laser cross-links between satellites.

    Physics formulations:
      Divergence angle (diffraction-limited Airy disk):
        theta_div = 1.22 * lambda / D_tx [rad]

      Telescope Gain:
        G = (pi * D / lambda)^2

      Free space loss:
        L_fs = (lambda / (4 * pi * R))^2

      Pointing loss (Gaussian beam pointing error):
        L_point = exp(-0.5 * G_tx * sigma_jitter^2)

      Photons per second:
        N_photons = P_rx / (h_planck * nu)
        Photons/bit = N_photons / DataRate
    """

    SPEED_OF_LIGHT = 299792458.0             # m/s
    PLANCK_CONSTANT = 6.62607015e-34         # J * s
    BOLTZMANN_CONSTANT = 1.380649e-23

    def __init__(self, config: Optional[OpticalISLConfig] = None):
        self.config = config or OpticalISLConfig()
        self.wavelength_m = self.config.wavelength_nm * 1e-9
        self.carrier_freq_hz = self.SPEED_OF_LIGHT / self.wavelength_m

    def compute_aperture_gain(self, diameter_m: float) -> Tuple[float, float]:
        """
        Calculates telescope optical gain. Returns (linear_gain, dBi_gain).
        """
        gain_lin = ((math.pi * diameter_m) / self.wavelength_m) ** 2
        gain_dbi = 10.0 * math.log10(gain_lin)
        return gain_lin, gain_dbi

    def compute_beam_divergence_urad(self, diameter_m: float) -> float:
        """Calculates Airy disk divergence half-angle in microradians."""
        theta_rad = 1.22 * self.wavelength_m / diameter_m
        return theta_rad * 1e6

    def compute_reaction_wheel_jitter(
        self,
        wheel_rpm: float = 3600.0,
        static_imbalance_g_mm: float = 2.5,
        isolation_damping_ratio: float = 0.05,
    ) -> JitterSpectrumProfile:
        """
        Calculates micro-vibration angular jitter induced by reaction wheel imbalance.
        """
        f_wheel = wheel_rpm / 60.0  # Hz
        # Centrifugal disturbance force: F = m_imb * r_imb * omega^2
        omega = 2.0 * math.pi * f_wheel
        dist_force_n = (static_imbalance_g_mm * 1e-6) * (omega ** 2)

        # Structural amplification Q = 1 / (2 * zeta)
        q_factor = 1.0 / max(0.01, 2.0 * isolation_damping_ratio)

        # Baseline angular jitter standard deviation in microradians
        rms_jitter = (dist_force_n * q_factor * 0.18) + 1.2  # Base sensor floor ~ 1.2 urad

        return JitterSpectrumProfile(
            wheel_speed_rpm=wheel_rpm,
            static_imbalance_g_mm=static_imbalance_g_mm,
            structural_amplification_q=round(q_factor, 2),
            rms_jitter_urad=round(rms_jitter, 3),
        )

    def calculate_pointing_loss_db(self, jitter_urad: float, tx_dia_m: float) -> float:
        """
        Calculates pointing attenuation [dB] from beam divergence and angular jitter.
        """
        jitter_rad = jitter_urad * 1e-6
        g_tx_lin, _ = self.compute_aperture_gain(tx_dia_m)

        # Pointing exponent: 0.5 * G_tx * sigma^2
        arg = 0.5 * g_tx_lin * (jitter_rad ** 2)
        # Numerical protection
        loss_lin = math.exp(-min(25.0, arg))
        loss_db = 10.0 * math.log10(max(1e-12, loss_lin))
        return loss_db

    def calculate_optical_doppler_ghz(self, relative_velocity_km_s: float) -> float:
        """
        Calculates relativistic optical Doppler frequency shift [GHz].
        """
        v_rel_ms = relative_velocity_km_s * 1000.0
        delta_f_hz = self.carrier_freq_hz * (v_rel_ms / self.SPEED_OF_LIGHT)
        return delta_f_hz * 1e-9

    def evaluate_link_budget(
        self,
        distance_km: float = 5000.0,
        relative_velocity_km_s: float = 3.5,
        pointing_jitter_urad: float = 2.2,
    ) -> OpticalLinkReport:
        """
        Computes complete link budget for inter-satellite optical transmission.
        """
        dist_m = distance_km * 1000.0
        p_tx_w = self.config.tx_power_w
        p_tx_dbm = 10.0 * math.log10(p_tx_w * 1000.0)

        # Gains
        g_tx_lin, g_tx_dbi = self.compute_aperture_gain(self.config.tx_aperture_dia_m)
        g_rx_lin, g_rx_dbi = self.compute_aperture_gain(self.config.rx_aperture_dia_m)

        # Free space path loss: (lambda / (4*pi*R))^2
        fspl_lin = (self.wavelength_m / (4.0 * math.pi * dist_m)) ** 2
        fspl_db = 10.0 * math.log10(fspl_lin)

        # Pointing loss
        pointing_loss_db = self.calculate_pointing_loss_db(pointing_jitter_urad, self.config.tx_aperture_dia_m)
        optics_eff_db = 10.0 * math.log10(self.config.optics_efficiency)

        # Received optical power
        p_rx_dbm = p_tx_dbm + g_tx_dbi + g_rx_dbi + fspl_db + pointing_loss_db + optics_eff_db
        p_rx_w = (10.0 ** (p_rx_dbm / 10.0)) * 1e-3

        # Receiver sensitivity calculation
        # Photon energy: E_photon = h * nu
        e_photon = self.PLANCK_CONSTANT * self.carrier_freq_hz
        required_power_w = (
            self.config.receiver_sensitivity_photons_per_bit
            * (self.config.data_rate_gbps * 1e9)
            * e_photon
        )
        p_sens_dbm = 10.0 * math.log10(required_power_w * 1000.0)

        # Link margin
        link_margin_db = p_rx_dbm - p_sens_dbm

        # Doppler shift
        doppler_ghz = self.calculate_optical_doppler_ghz(relative_velocity_km_s)

        # Estimated bit error rate (approximate Q-function for OOK/BPSK coherent demodulation)
        if link_margin_db >= 6.0:
            est_ber = 1.0e-12
            status = "LINK_CLOSED"
        elif link_margin_db >= 2.0:
            est_ber = 1.0e-9
            status = "LINK_CLOSED"
        elif link_margin_db >= 0.0:
            est_ber = 1.0e-6
            status = "MARGIN_DEGRADED"
        else:
            est_ber = 0.5
            status = "ACQUISITION_LOSS"

        return OpticalLinkReport(
            link_distance_km=distance_km,
            relative_velocity_km_s=relative_velocity_km_s,
            carrier_frequency_thz=round(self.carrier_freq_hz * 1e-12, 3),
            transmitter_gain_dbi=round(g_tx_dbi, 2),
            free_space_path_loss_db=round(fspl_db, 2),
            pointing_jitter_urad=round(pointing_jitter_urad, 3),
            pointing_loss_db=round(pointing_loss_db, 2),
            received_optical_power_dbm=round(p_rx_dbm, 2),
            receiver_sensitivity_dbm=round(p_sens_dbm, 2),
            link_margin_db=round(link_margin_db, 2),
            doppler_frequency_shift_ghz=round(doppler_ghz, 3),
            estimated_ber=est_ber,
            link_status=status,
        )
