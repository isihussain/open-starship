"""
Open-Starship End-to-End Orchestration Pipeline.

Executes the unified data pipeline:
  1. starship-flip-gnc: Computes landing flip trajectory & writes flight telemetry.
  2. starship-cryo-slosh: Reads telemetry & simulates cryogenic propellant dynamics in header tanks.
  3. starship-tps-vision: Derives aerothermal risk map from flight loads & executes tile inspection.
  4. Mechazilla Catch Solver: Evaluates chopstick arm capture kinematics at launch tower.
  5. In-Space Cryogenic Transfer: Simulates orbital propellant delivery from Tanker to Depot.
"""

import sys
import os
import json
from pathlib import Path

# Add child packages to Python path for seamless execution:
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "starship-flip-gnc"))
sys.path.insert(0, str(BASE_DIR / "starship-cryo-slosh"))
sys.path.insert(0, str(BASE_DIR / "starship-tps-vision"))

from starship_flip_gnc.models import StarshipVehicle, FlightState
from starship_flip_gnc.trajectory import TrajectoryOptimizer
from starship_flip_gnc.telemetry import TelemetryLogger
from starship_flip_gnc.catch_dynamics import MechazillaCatchSolver, CatchEnvelope

from starship_cryo_slosh.tank import HeaderTankAssembly, CryogenicFluid
from starship_cryo_slosh.simulator import SloshSimulator
from starship_cryo_slosh.orbital_transfer import OrbitalTransferSimulator

from starship_tps_vision.thermal_map import AerothermalRiskMap
from starship_tps_vision.synthetic import SyntheticTileGridGenerator
from starship_tps_vision.detector import TileDefectDetector
from starship_tps_vision.reporter import InspectionReporter


def run_pipeline(output_dir: str = "pipeline_artifacts") -> None:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print("================================================================")
    print("           OPEN-STARSHIP ENGINEERING PIPELINE                   ")
    print("================================================================")

    # -------------------------------------------------------------------------
    # STEP 1: Flight Dynamics & Trajectory Optimization (starship-flip-gnc)
    # -------------------------------------------------------------------------
    print("\n[1/5] Running: starship-flip-gnc (Landing Flip Trajectory Solver)...")
    vehicle = StarshipVehicle(dry_mass=100_000.0, landing_propellant_mass=25_000.0)
    optimizer = TrajectoryOptimizer(vehicle=vehicle)
    gnc_logger = TelemetryLogger()

    # Initiate flip burn from 500m at -70 m/s:
    initial_state = FlightState(z=500.0, vz=-70.0)
    flight_result = optimizer.simulate(initial_state=initial_state, dt=0.02, logger=gnc_logger)

    telem_json_path = out_path / "flight_telemetry.json"
    telem_csv_path = out_path / "flight_telemetry.csv"
    gnc_logger.export_json(str(telem_json_path))
    gnc_logger.export_csv(str(telem_csv_path))

    print(f"      -> Flight Outcome: {'SUCCESS' if flight_result.success else 'FAILED'}")
    print(f"      -> Touchdown Time: {flight_result.touchdown_time_s} s")
    print(f"      -> Terminal Vertical Velocity: {flight_result.final_velocity_z_mps} m/s | Pitch: {flight_result.final_pitch_deg} deg")
    print(f"      -> Propellant Burned: {flight_result.propellant_used_kg} kg (Remaining: {flight_result.propellant_remaining_kg} kg)")
    print(f"      -> Telemetry Saved: {telem_json_path} ({len(gnc_logger.records)} records)")

    # -------------------------------------------------------------------------
    # STEP 2: Cryogenic Slosh & Ullage Ingestion (starship-cryo-slosh)
    # -------------------------------------------------------------------------
    print("\n[2/5] Running: starship-cryo-slosh (Header Tank Fluid Slosh)...")
    assembly = HeaderTankAssembly.default_starship(with_baffles=True)
    slosh_sim = SloshSimulator(
        assembly=assembly,
        lox_mass_kg=flight_result.propellant_remaining_kg * 0.70,
        ch4_mass_kg=flight_result.propellant_remaining_kg * 0.30,
    )

    slosh_result, slosh_history = slosh_sim.simulate_telemetry(gnc_logger.records)
    slosh_json_path = out_path / "slosh_dynamics.json"
    with open(slosh_json_path, "w", encoding="utf-8") as f:
        json.dump([pt.to_dict() for pt in slosh_history], f, indent=2)

    print(f"      -> Slosh Risk Level: {slosh_result.risk_level}")
    print(f"      -> LOX Gas Ingestion: {'YES' if slosh_result.lox_gas_ingestion_detected else 'NO'} (Min Submergence: {slosh_result.lox_min_submergence_m} m)")
    print(f"      -> CH4 Gas Ingestion: {'YES' if slosh_result.ch4_gas_ingestion_detected else 'NO'} (Min Submergence: {slosh_result.ch4_min_submergence_m} m)")
    print(f"      -> Peak Disturbance Torque: {slosh_result.max_slosh_torque_nm} N*m")
    print(f"      -> Peak Center-of-Mass Shift: {slosh_result.max_com_shift_x_mm} mm")
    print(f"      -> Slosh Telemetry Saved: {slosh_json_path}")

    # -------------------------------------------------------------------------
    # STEP 3: TPS Tile Damage Inspection (starship-tps-vision)
    # -------------------------------------------------------------------------
    print("\n[3/5] Running: starship-tps-vision (Heat Shield Tile Inspection)...")
    risk_map = AerothermalRiskMap.from_telemetry(gnc_logger.records)
    generator = SyntheticTileGridGenerator(random_seed=42)
    observations = generator.generate_sector(num_tiles_axial=30, num_tiles_azimuthal=20, defect_rate=0.06)

    detector = TileDefectDetector(risk_map=risk_map)
    batch_result = detector.inspect_batch(observations)

    tps_json_path = out_path / "tps_inspection_report.json"
    tps_md_path = out_path / "tps_maintenance_work_order.md"
    InspectionReporter.export_json(batch_result, str(tps_json_path))
    InspectionReporter.generate_markdown_report(batch_result, str(tps_md_path))

    print(f"      -> Total Inspected Tiles: {batch_result.total_inspected}")
    print(f"      -> Intact: {batch_result.intact_count} | Defective: {batch_result.defective_count}")
    print(f"         - Missing: {batch_result.missing_count} | Cracked: {batch_result.cracked_count}")
    print(f"         - Chipped Edges: {batch_result.chipped_count} | Gap Expansions: {batch_result.gap_expansion_count}")
    print(f"      -> Critical Replacements Required: {batch_result.critical_replacements_required}")
    print(f"      -> Maintenance Work Order Saved: {tps_md_path}")

    # -------------------------------------------------------------------------
    # STEP 4: Mechazilla Tower Catch Verification
    # -------------------------------------------------------------------------
    print("\n[4/5] Running: Mechazilla Chopstick Catch Solver...")
    catch_solver = MechazillaCatchSolver()
    catch_res = catch_solver.evaluate_capture(
        x_m=0.12,
        z_m=45.05,
        vx_mps=0.04,
        vz_mps=-0.28,
        pitch_deg=0.5,
        vehicle_mass_kg=vehicle.dry_mass + flight_result.propellant_remaining_kg,
    )
    print(f"      -> Chopstick Catch Status: {'SUCCESS' if catch_res.caught else 'ABORT'}")
    print(f"      -> Lateral Error: {catch_res.lateral_error_m} m | Vertical Error: {catch_res.vertical_error_m} m")
    print(f"      -> Contact Load: {catch_res.contact_impulse_n / 1e3:.1f} kN")
    print(f"      -> Message: {catch_res.message}")

    # -------------------------------------------------------------------------
    # STEP 5: In-Space Cryogenic Propellant Transfer
    # -------------------------------------------------------------------------
    print("\n[5/5] Running: In-Space Cryogenic Propellant Transfer Simulator...")
    transfer_sim = OrbitalTransferSimulator()
    lox_fluid = CryogenicFluid.liquid_oxygen()
    transfer_res = transfer_sim.simulate_transfer(fluid=lox_fluid, target_mass_kg=80_000.0)
    print(f"      -> Transfer Status: {'SUCCESS' if transfer_res.success else 'FAILED'}")
    print(f"      -> Delivered Mass: {transfer_res.mass_transferred_kg:.0f} kg in {transfer_res.duration_s / 60.0:.1f} min")
    print(f"      -> Flow Rate: {transfer_res.average_flow_rate_kg_s:.1f} kg/s | Transfer Efficiency: {transfer_res.transfer_efficiency_percent:.2f}%")
    print(f"      -> Settling Bond Number: {transfer_res.bond_number:.1f} (Settled: {transfer_res.is_fluid_settled})")

    print("\n================================================================")
    print("      ALL PHASES COMPLETED AND INTEGRATED SUCCESSFULLY          ")
    print(f"      Output Artifacts: {out_path.resolve()}")
    print("      3D Visualizer: visualizer/index.html")
    print("================================================================\n")


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_artifacts"
    run_pipeline(out_dir)
