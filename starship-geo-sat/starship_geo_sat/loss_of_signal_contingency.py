"""
Loss-of-Signal (LOS) Autonomous Flight Control and Satellite Deployment Controller.

Models launch vehicle autonomous operations during total RF antenna failure
(primary and backup communication outage), validating:
1. RF watchdog timeout detection and ground-command lockout.
2. Autonomous Inertial Navigation System (INS) guidance continuation.
3. Autonomous Flight Termination System (AFTS) corridor tracking without ground contact.
4. Orbital insertion energy verification and engine cutoff (SECO).
5. Autonomous mechanical payload separation, satellite wake sequence, and independent RF activation.
"""

from dataclasses import dataclass
from typing import Optional
import math

# WGS-84 Earth gravitational parameter and equatorial radius
MU_EARTH_M3_S2 = 3.986004418e14
R_EARTH_EQUATORIAL_M = 6_378_137.0


@dataclass
class AntennaTelemetry:
    """
    Radio communication link telemetry for primary and backup antenna suites.
    """
    timestamp_s: float
    primary_rf_active: bool
    secondary_rf_active: bool
    primary_snr_db: float
    secondary_snr_db: float
    last_uplink_heartbeat_s: float
    carrier_frequency_mhz: float = 2250.0  # S-band telemetry


@dataclass
class AscentInertialState:
    """
    Onboard inertial measurement unit (IMU) fused state vector.
    """
    timestamp_s: float
    altitude_m: float
    downrange_km: float
    crossrange_km: float
    inertial_velocity_mps: float
    axial_acceleration_mps2: float
    attitude_pitch_deg: float
    attitude_yaw_rate_deg_s: float = 0.0


@dataclass
class AFTSCorridorLimits:
    """
    Autonomous Flight Safety System boundary definitions (FAA 14 CFR Part 450).
    """
    max_crossrange_km: float = 40.0
    max_yaw_rate_deg_s: float = 10.0
    min_axial_acceleration_mps2: float = 2.0
    comm_timeout_threshold_s: float = 3.0
    orbital_insertion_altitude_min_m: float = 160_000.0
    orbital_insertion_velocity_min_mps: float = 7750.0
    post_separation_coast_s: float = 900.0  # 15-minute clearance drift


@dataclass
class ContingencyAssessment:
    """
    Telemetry and flight controller decisions during RF communication loss.
    """
    timestamp_s: float
    loss_of_signal_confirmed: bool
    uplink_outage_duration_s: float
    flight_mode: str
    afts_corridor_cleared: bool
    afts_flight_termination_commanded: bool
    ground_command_lockout_active: bool
    orbital_insertion_verified: bool
    specific_orbital_energy_mj_kg: float
    payload_separation_commanded: bool
    satellite_microswitch_tripped: bool
    satellite_solar_arrays_deployed: bool
    satellite_rf_carrier_active: bool
    status_message: str


class LossOfSignalContingencyController:
    """
    Flight computer contingency executive governing uncrewed ascent through total antenna blackout.
    """

    def __init__(self, limits: Optional[AFTSCorridorLimits] = None):
        self.limits = limits or AFTSCorridorLimits()

    def evaluate(
        self,
        rf: AntennaTelemetry,
        state: AscentInertialState,
        post_sep_elapsed_s: float = 0.0,
    ) -> ContingencyAssessment:
        """
        Evaluate communication state, corridor limits, and payload release sequencing.
        """
        outage_duration = max(0.0, rf.timestamp_s - rf.last_uplink_heartbeat_s)
        rf_loss = (
            (not rf.primary_rf_active and not rf.secondary_rf_active)
            or (rf.primary_snr_db < -12.0 and rf.secondary_snr_db < -12.0)
            or (outage_duration >= self.limits.comm_timeout_threshold_s)
        )

        # Ground command lockout prevents executing degraded or corrupted RF bursts
        ground_lockout = rf_loss

        # AFTS Corridor evaluation: calculated entirely onboard via INS
        crossrange_exceeded = abs(state.crossrange_km) > self.limits.max_crossrange_km
        tumble_detected = abs(state.attitude_yaw_rate_deg_s) > self.limits.max_yaw_rate_deg_s
        under_acceleration = state.axial_acceleration_mps2 < self.limits.min_axial_acceleration_mps2

        afts_terminate = crossrange_exceeded or tumble_detected or (under_acceleration and state.altitude_m < 80_000.0)
        afts_cleared = not afts_terminate

        # Specific orbital energy: E = v^2/2 - mu/r
        r_orbit = R_EARTH_EQUATORIAL_M + state.altitude_m
        specific_energy_j_kg = (0.5 * (state.inertial_velocity_mps ** 2)) - (MU_EARTH_M3_S2 / r_orbit)
        specific_energy_mj_kg = specific_energy_j_kg / 1.0e6

        orbital_inserted = (
            state.altitude_m >= self.limits.orbital_insertion_altitude_min_m
            and state.inertial_velocity_mps >= self.limits.orbital_insertion_velocity_min_mps
            and specific_energy_mj_kg >= -32.0
        )

        # Payload release sequencing: only released after orbit insertion and clear corridor
        payload_released = orbital_inserted and afts_cleared and not afts_terminate
        satellite_switches_tripped = payload_released
        solar_deployed = payload_released and (post_sep_elapsed_s >= self.limits.post_separation_coast_s)
        satellite_rf_active = solar_deployed

        if afts_terminate:
            flight_mode = "AFTS_AUTONOMOUS_TERMINATION"
            msg = (
                f"AFTS triggered autonomous termination: crossrange={state.crossrange_km:.1f}km, "
                f"yaw_rate={state.attitude_yaw_rate_deg_s:.1f}deg/s, accel={state.axial_acceleration_mps2:.1f}m/s2."
            )
        elif rf_loss:
            flight_mode = "AUTONOMOUS_INS_MISSION_CONTINUATION"
            if orbital_inserted:
                msg = (
                    f"Total antenna blackout: autonomous INS achieved orbit (v={state.inertial_velocity_mps:.1f}m/s). "
                    f"Payload deployed successfully. Satellite autonomous sequence active."
                )
            else:
                msg = (
                    f"Total antenna blackout (outage={outage_duration:.1f}s): vehicle continuing nominal ascent "
                    f"via autonomous closed-loop INS. Corridor safe (crossrange={state.crossrange_km:.1f}km)."
                )
        else:
            flight_mode = "NOMINAL_RF_SUPERVISED"
            msg = f"Nominal RF communication link active (primary SNR={rf.primary_snr_db:.1f}dB)."

        return ContingencyAssessment(
            timestamp_s=state.timestamp_s,
            loss_of_signal_confirmed=rf_loss,
            uplink_outage_duration_s=outage_duration,
            flight_mode=flight_mode,
            afts_corridor_cleared=afts_cleared,
            afts_flight_termination_commanded=afts_terminate,
            ground_command_lockout_active=ground_lockout,
            orbital_insertion_verified=orbital_inserted,
            specific_orbital_energy_mj_kg=round(specific_energy_mj_kg, 2),
            payload_separation_commanded=payload_released,
            satellite_microswitch_tripped=satellite_switches_tripped,
            satellite_solar_arrays_deployed=solar_deployed,
            satellite_rf_carrier_active=satellite_rf_active,
            status_message=msg,
        )
