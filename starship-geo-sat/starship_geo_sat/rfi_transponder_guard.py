"""
Transponder radio-frequency interference (RFI) guard and Ka-band rain fade compensator.

Mitigates commercial GEO communications payload anomalies
(e.g., Türksat 3A, 4A, and 4B cross-polarization and Ka-band atmospheric fade events),
where terrestrial uplink cross-polarization leakage (XPI < 25 dB), TWTA non-linear saturation,
or severe rain attenuation (up to 20 dB at 30 GHz) degraded transponder throughput.

Implements Saleh non-linear TWTA gain compression modeling, cross-polarization isolation detection,
and automated uplink power control (AUPC) feedback commands.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
import math


@dataclass
class CarrierTelemetry:
    """
    Measured RF characteristics of an uplink carrier on a satellite transponder.
    """
    carrier_id: str
    frequency_ghz: float
    polarization: str                         # "V" (Vertical) or "H" (Horizontal)
    measured_input_power_dbw: float           # Measured at transponder input
    nominal_operating_point_dbw: float = -75.0
    cross_polar_leakage_power_dbw: float = -105.0 # Leakage measured on orthogonal polarization
    rain_rate_mm_per_hr: float = 0.0          # Ground station meteorological rainfall rate


@dataclass
class TransponderState:
    """
    On-board Traveling Wave Tube Amplifier (TWTA) operational state.
    """
    transponder_name: str
    twta_saturated_output_power_watts: float = 120.0 # 120 W Ku/Ka TWTA
    input_backoff_db: float = 3.0             # Desired backoff from saturation (IBO)
    nominal_operating_point_dbw: float = -75.0
    saleh_alpha_a: float = 2.0                # Saleh amplitude compression model parameters
    saleh_beta_a: float = 1.0


@dataclass
class PayloadGuardAction:
    """
    Diagnostic assessment, backoff recommendation, and AUPC power control command.
    """
    carrier_id: str
    cross_polar_isolation_db: float
    xpi_violation: bool
    twta_saturated: bool
    saleh_output_power_watts: float
    rain_attenuation_db: float
    aupc_recommended_boost_db: float
    intermodulation_risk: str                 # "LOW", "MODERATE", "CRITICAL"
    status_message: str


class RFITransponderGuard:
    """
    Detects cross-polarization contamination, TWTA saturation, and commands rain fade power compensation.
    """

    MIN_ACCEPTABLE_XPI_DB = 25.0              # Industry standard: XPI must exceed 25 dB
    MAX_AUPC_BOOST_DB = 15.0                  # Hardware power amplifier ceiling

    def __init__(self, transponder: TransponderState = TransponderState(transponder_name="Ku_TP_12A")):
        self.tp = transponder

    def evaluate_carrier(self, carrier: CarrierTelemetry) -> PayloadGuardAction:
        """
        Evaluates uplink power against TWTA non-linear curve, XPI isolation, and rain fade.
        """
        # 1. Cross-Polarization Isolation (XPI):
        # XPI = P_co - P_cross (in dB)
        xpi_db = carrier.measured_input_power_dbw - carrier.cross_polar_leakage_power_dbw
        xpi_fault = xpi_db < self.MIN_ACCEPTABLE_XPI_DB

        # 2. Saleh non-linear TWTA model:
        # Normalized input voltage r = 10^((P_in - P_sat_in) / 20)
        p_sat_in = self.tp.nominal_operating_point_dbw + self.tp.input_backoff_db
        actual_ibo = p_sat_in - carrier.measured_input_power_dbw

        twta_sat = actual_ibo < 0.5  # Input power is driving TWTA into saturation

        # Normalized input voltage
        voltage_ratio = 10.0 ** ((carrier.measured_input_power_dbw - p_sat_in) / 20.0)
        # Saleh amplitude compression: A(r) = (alpha * r) / (1 + beta * r^2)
        gain_comp = (self.tp.saleh_alpha_a * voltage_ratio) / (1.0 + self.tp.saleh_beta_a * (voltage_ratio ** 2))
        normalized_output_power = (gain_comp ** 2) / (self.tp.saleh_alpha_a ** 2 / (4.0 * self.tp.saleh_beta_a))
        out_power_watts = min(
            self.tp.twta_saturated_output_power_watts,
            self.tp.twta_saturated_output_power_watts * normalized_output_power,
        )

        # 3. Rain Attenuation Estimation (ITU-R P.618 simplified power-law: A_rain = a * R^b * L_eff):
        # For Ku/Ka-band: higher frequencies suffer exponentially worse rain fade
        if carrier.frequency_ghz >= 25.0:
            # Ka-band (28-30 GHz uplink)
            k_rain = 0.22
            alpha_rain = 0.95
        else:
            # Ku-band (14 GHz uplink)
            k_rain = 0.04
            alpha_rain = 1.15

        path_length_km = 4.2  # Effective slant path through troposphere rain cell
        if carrier.rain_rate_mm_per_hr > 0.1:
            specific_attenuation_db_per_km = k_rain * (carrier.rain_rate_mm_per_hr ** alpha_rain)
            rain_fade_db = specific_attenuation_db_per_km * path_length_km
        else:
            rain_fade_db = 0.0

        # Calculate Automated Uplink Power Control (AUPC) recommendation:
        aupc_boost = min(self.MAX_AUPC_BOOST_DB, rain_fade_db)

        # Intermodulation distortion (IMD3) assessment:
        if twta_sat:
            imd_level = "CRITICAL"
        elif actual_ibo < 2.0:
            imd_level = "MODERATE"
        else:
            imd_level = "LOW"

        # Diagnostic message
        issues = []
        if xpi_fault:
            issues.append(f"XPI violation ({xpi_db:.1f} dB < {self.MIN_ACCEPTABLE_XPI_DB} dB)")
        if twta_sat:
            issues.append(f"TWTA saturated (IBO={actual_ibo:.1f} dB)")
        if rain_fade_db > 3.0:
            issues.append(f"Heavy rain fade ({rain_fade_db:.1f} dB)")

        if issues:
            msg = f"PAYLOAD INTERFERENCE/FADE DETECTED: {'; '.join(issues)}. AUPC command: +{aupc_boost:.1f} dB."
        else:
            msg = f"Carrier nominal: XPI={xpi_db:.1f} dB, IBO={actual_ibo:.1f} dB, Out={out_power_watts:.1f}W."

        return PayloadGuardAction(
            carrier_id=carrier.carrier_id,
            cross_polar_isolation_db=round(xpi_db, 2),
            xpi_violation=xpi_fault,
            twta_saturated=twta_sat,
            saleh_output_power_watts=round(out_power_watts, 2),
            rain_attenuation_db=round(rain_fade_db, 2),
            aupc_recommended_boost_db=round(aupc_boost, 2),
            intermodulation_risk=imd_level,
            status_message=msg,
        )
