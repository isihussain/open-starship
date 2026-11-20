"""
Command line interface for starship-geo-sat.

Executes orbital mechanics, fleet coordination, payload safety, and loss-of-signal
evaluations from the terminal with optional JSON reporting.
"""

import argparse
import json
import sys
from pathlib import Path

from .station_keeping_prognostics import (
    StationKeepingPrognosticator,
    StationKeepingConfig,
)
from .launch_abort_detector import (
    LaunchAbortDetector,
    PropulsionTelemetry,
)
from .loss_of_signal_contingency import (
    LossOfSignalContingencyController,
    AntennaTelemetry,
    AscentInertialState,
)
from .hotbird_fleet_operations import (
    HotbirdFleetCoordinator,
    OrbitalVectorState,
)
from .optical_isl_crosslink import (
    OpticalISLTransceiver,
)
from .azercosmos_orbital_coordination import (
    AzercosmosOrbitalCoordinator,
    GroundStationSite,
)


def run_station_keeping(args) -> dict:
    config = StationKeepingConfig(
        slot_longitude_deg=args.slot,
        dry_mass_kg=args.dry_mass,
        current_propellant_kg=args.propellant,
        thruster_isp_s=args.isp,
    )
    prog = StationKeepingPrognosticator(config)
    report = prog.forecast_mission_lifetime()
    budget = prog.compute_annual_budget()

    print(f"\n--- Geostationary Station-Keeping Prognosis ({args.slot:.1f}°E) ---")
    print(f"Current Propellant: {report.current_propellant_kg:.1f} kg")
    print(f"Usable Propellant: {report.usable_propellant_kg:.1f} kg")
    print(f"Graveyard Reserve: {report.graveyard_reserve_kg:.1f} kg (Δv = {report.graveyard_delta_v_ms:.2f} m/s)")
    print(f"Annual Delta-V Budget: {report.annual_burn_budget_ms:.2f} m/s/yr")
    print(f"Annual Fuel Consumption: {budget.annual_propellant_consumption_kg:.2f} kg/yr")
    print(f"Remaining Lifetime: {report.remaining_lifetime_years:.2f} years")
    print(f"End-of-Life Status: {report.eol_status}")

    return {
        "mode": "station-keeping",
        "slot_longitude_deg": report.slot_longitude_deg,
        "remaining_lifetime_years": report.remaining_lifetime_years,
        "usable_propellant_kg": report.usable_propellant_kg,
        "graveyard_reserve_kg": report.graveyard_reserve_kg,
        "annual_burn_budget_ms": report.annual_burn_budget_ms,
        "annual_propellant_consumption_kg": budget.annual_propellant_consumption_kg,
        "eol_status": report.eol_status,
    }


def run_launch_abort(args) -> dict:
    detector = LaunchAbortDetector()
    telemetry = PropulsionTelemetry(
        timestamp_s=args.timestamp,
        chamber_pressure_bar=args.chamber_pressure,
        turbopump_speed_rpm=args.turbopump_rpm,
        lox_valve_position_percent=args.lox_valve,
        axial_acceleration_mps2=args.axial_accel,
        altitude_km=args.altitude,
        inertial_velocity_mps=args.velocity,
    )
    assessment = detector.evaluate(telemetry)

    print(f"\n--- Upper-Stage Launch Abort Assessment ---")
    print(f"Nominal Thrust: {assessment.nominal_thrust}")
    print(f"Abort Triggered: {assessment.abort_triggered}")
    print(f"Injection Shortfall: {assessment.injection_shortfall_mps:.1f} m/s")
    print(f"Spacecraft Safing Commanded: {assessment.spacecraft_safing_commanded}")
    print(f"Status Message: {assessment.status_message}")

    return {
        "mode": "launch-abort",
        "nominal_thrust": assessment.nominal_thrust,
        "abort_triggered": assessment.abort_triggered,
        "injection_shortfall_mps": assessment.injection_shortfall_mps,
        "spacecraft_safing_commanded": assessment.spacecraft_safing_commanded,
        "status_message": assessment.status_message,
    }


def run_los_blackout(args) -> dict:
    controller = LossOfSignalContingencyController()
    rf = AntennaTelemetry(
        timestamp_s=args.timestamp,
        primary_rf_active=not args.rf_loss,
        secondary_rf_active=not args.rf_loss,
        primary_snr_db=-99.0 if args.rf_loss else 18.0,
        secondary_snr_db=-99.0 if args.rf_loss else 16.0,
        last_uplink_heartbeat_s=args.timestamp - (45.0 if args.rf_loss else 0.5),
    )
    state = AscentInertialState(
        timestamp_s=args.timestamp,
        altitude_m=args.altitude,
        downrange_km=args.downrange,
        crossrange_km=args.crossrange,
        inertial_velocity_mps=args.velocity,
        axial_acceleration_mps2=args.axial_accel,
        attitude_pitch_deg=args.pitch,
    )
    assessment = controller.evaluate(rf, state, post_sep_elapsed_s=args.post_sep_time)

    print(f"\n--- Loss-of-Signal (LOS) Blackout Assessment ---")
    print(f"LOS Confirmed: {assessment.loss_of_signal_confirmed}")
    print(f"Flight Mode: {assessment.flight_mode}")
    print(f"Ground Command Lockout: {assessment.ground_command_lockout_active}")
    print(f"AFTS Corridor Safe: {assessment.afts_corridor_cleared}")
    print(f"AFTS Termination Commanded: {assessment.afts_flight_termination_commanded}")
    print(f"Orbital Insertion Verified: {assessment.orbital_insertion_verified}")
    print(f"Payload Separation Commanded: {assessment.payload_separation_commanded}")
    print(f"Satellite RF Link Active: {assessment.satellite_rf_carrier_active}")
    print(f"Status Message: {assessment.status_message}")

    return {
        "mode": "los-blackout",
        "loss_of_signal_confirmed": assessment.loss_of_signal_confirmed,
        "flight_mode": assessment.flight_mode,
        "ground_command_lockout_active": assessment.ground_command_lockout_active,
        "afts_corridor_cleared": assessment.afts_corridor_cleared,
        "afts_flight_termination_commanded": assessment.afts_flight_termination_commanded,
        "orbital_insertion_verified": assessment.orbital_insertion_verified,
        "payload_separation_commanded": assessment.payload_separation_commanded,
        "satellite_solar_arrays_deployed": assessment.satellite_solar_arrays_deployed,
        "satellite_rf_carrier_active": assessment.satellite_rf_carrier_active,
        "status_message": assessment.status_message,
    }


def run_optical_isl(args) -> dict:
    transceiver = OpticalISLTransceiver()
    report = transceiver.evaluate_link_budget(
        distance_km=args.distance,
        relative_velocity_km_s=args.relative_velocity,
        pointing_jitter_urad=args.jitter,
    )

    print(f"\n--- Optical Inter-Satellite Link (1550nm Laser Crosslink) ---")
    print(f"Range: {report.link_distance_km:.1f} km")
    print(f"Received Optical Power: {report.received_optical_power_dbm:.2f} dBm")
    print(f"Link Margin: {report.link_margin_db:.2f} dB")
    print(f"Doppler Shift: {report.doppler_frequency_shift_ghz:.3f} GHz")
    print(f"Estimated Bit Error Rate: {report.estimated_ber:.2e}")
    print(f"Link Status: {report.link_status}")

    return {
        "mode": "optical-isl",
        "link_distance_km": report.link_distance_km,
        "received_optical_power_dbm": report.received_optical_power_dbm,
        "link_margin_db": report.link_margin_db,
        "doppler_frequency_shift_ghz": report.doppler_frequency_shift_ghz,
        "estimated_ber": report.estimated_ber,
        "link_status": report.link_status,
    }


def main(cli_args=None):
    parser = argparse.ArgumentParser(
        description="Geostationary satellite fleet dynamics, propulsion safety, and link budget CLI."
    )
    parser.add_argument(
        "--mode",
        choices=["station-keeping", "launch-abort", "los-blackout", "optical-isl"],
        default="station-keeping",
        help="Evaluation mode (default: station-keeping)",
    )
    # Station-keeping arguments:
    parser.add_argument("--slot", type=float, default=42.0, help="Orbital slot longitude in degrees East (default: 42.0)")
    parser.add_argument("--dry-mass", type=float, default=2200.0, help="Spacecraft dry mass in kg (default: 2200.0)")
    parser.add_argument("--propellant", type=float, default=280.0, help="Current usable propellant mass in kg (default: 280.0)")
    parser.add_argument("--isp", type=float, default=310.0, help="Thruster specific impulse in seconds (default: 310.0)")

    # Launch-abort and propulsion arguments:
    parser.add_argument("--timestamp", type=float, default=700.0, help="Flight timestamp in seconds (default: 700.0)")
    parser.add_argument("--chamber-pressure", type=float, default=34.5, help="Chamber pressure in bar (default: 34.5)")
    parser.add_argument("--turbopump-rpm", type=float, default=61800.0, help="Turbopump rotational speed in RPM (default: 61800.0)")
    parser.add_argument("--lox-valve", type=float, default=99.0, help="LOX valve position percent (default: 99.0)")
    parser.add_argument("--axial-accel", type=float, default=19.2, help="Axial acceleration in m/s^2 (default: 19.2)")
    parser.add_argument("--altitude", type=float, default=185000.0, help="Altitude in meters (default: 185000.0)")
    parser.add_argument("--velocity", type=float, default=7825.0, help="Inertial velocity in m/s (default: 7825.0)")

    # LOS Blackout arguments:
    parser.add_argument("--rf-loss", action="store_true", default=True, help="Simulate complete RF loss of signal (default: True)")
    parser.add_argument("--downrange", type=float, default=1420.0, help="Downrange distance in km (default: 1420.0)")
    parser.add_argument("--crossrange", type=float, default=2.1, help="Crossrange deviation in km (default: 2.1)")
    parser.add_argument("--pitch", type=float, default=0.0, help="Attitude pitch angle in degrees (default: 0.0)")
    parser.add_argument("--post-sep-time", type=float, default=920.0, help="Seconds elapsed after separation (default: 920.0)")

    # Optical ISL arguments:
    parser.add_argument("--distance", type=float, default=4500.0, help="Optical link distance in km (default: 4500.0)")
    parser.add_argument("--relative-velocity", type=float, default=2.8, help="Relative line-of-sight velocity in km/s (default: 2.8)")
    parser.add_argument("--jitter", type=float, default=1.8, help="Pointing jitter in microradians (default: 1.8)")

    # Output argument:
    parser.add_argument("--export-json", type=str, default="", help="Path to export evaluation output JSON file")

    args = parser.parse_args(cli_args)

    if args.mode == "station-keeping":
        output_data = run_station_keeping(args)
    elif args.mode == "launch-abort":
        output_data = run_launch_abort(args)
    elif args.mode == "los-blackout":
        output_data = run_los_blackout(args)
    elif args.mode == "optical-isl":
        output_data = run_optical_isl(args)
    else:
        output_data = {}

    if args.export_json:
        out_p = Path(args.export_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nExported {args.mode} results to {args.export_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
