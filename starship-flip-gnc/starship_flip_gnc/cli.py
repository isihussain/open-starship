"""
Command line interface for starship-flip-gnc.
"""

import argparse
import sys
from .models import StarshipVehicle, FlightState
from .trajectory import TrajectoryOptimizer
from .telemetry import TelemetryLogger


def main():
    parser = argparse.ArgumentParser(
        description="Simulate Starship belly-flop to vertical landing flip maneuver."
    )
    parser.add_argument(
        "--altitude",
        type=float,
        default=500.0,
        help="Initial flip altitude [m] (default: 500.0)",
    )
    parser.add_argument(
        "--vz",
        type=float,
        default=-70.0,
        help="Initial vertical descent velocity [m/s] (default: -70.0)",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=0.02,
        help="Integration time step [s] (default: 0.02)",
    )
    parser.add_argument(
        "--export-json",
        type=str,
        default="",
        help="Path to export telemetry JSON file",
    )
    parser.add_argument(
        "--export-csv",
        type=str,
        default="",
        help="Path to export telemetry CSV file",
    )

    args = parser.parse_args()

    vehicle = StarshipVehicle()
    optimizer = TrajectoryOptimizer(vehicle=vehicle)
    logger = TelemetryLogger()

    init_state = FlightState(z=args.altitude, vz=args.vz)

    print(f"Running Starship flip simulation from z={args.altitude}m, vz={args.vz}m/s...")
    result = optimizer.simulate(initial_state=init_state, dt=args.dt, logger=logger)

    print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Touchdown Time: {result.touchdown_time_s} s")
    print(f"Final Altitude: {result.final_altitude_m} m")
    print(f"Final Vz: {result.final_velocity_z_mps} m/s")
    print(f"Final Pitch: {result.final_pitch_deg} deg")
    print(f"Propellant Burned: {result.propellant_used_kg} kg (Remaining: {result.propellant_remaining_kg} kg)")
    print(f"Max Lateral Accel: {result.max_lateral_accel_g} g")
    print(f"Max Axial Accel: {result.max_axial_accel_g} g")
    print(f"Message: {result.message}")

    if args.export_json:
        logger.export_json(args.export_json)
        print(f"Exported {len(logger.records)} records to {args.export_json}")

    if args.export_csv:
        logger.export_csv(args.export_csv)
        print(f"Exported {len(logger.records)} records to {args.export_csv}")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
