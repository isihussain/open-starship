"""
Open-Starship End-to-End Orchestration Pipeline.

Executes the unified data pipeline:
  1. starship-flip-gnc: Computes landing flip trajectory & writes flight telemetry.
  2. starship-cryo-slosh: Reads telemetry & simulates cryogenic propellant dynamics in header tanks.
  3. starship-tps-vision: Derives aerothermal risk map from flight loads & executes tile inspection.
  4. Mechazilla Catch Solver: Evaluates chopstick arm capture kinematics at launch tower.
  5. In-Space Cryogenic Transfer: Simulates orbital propellant delivery from Tanker to Depot.
  6. Flight Safety Interlocks: Validates failure mitigations from historical launch vehicle incidents.
  7. Geostationary Satellite Operations: Evaluates orbital dynamics and payload mitigations (Türksat fleet).
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
sys.path.insert(0, str(BASE_DIR / "starship-geo-sat"))

from starship_flip_gnc.models import StarshipVehicle, FlightState
from starship_flip_gnc.trajectory import TrajectoryOptimizer
from starship_flip_gnc.telemetry import TelemetryLogger
from starship_flip_gnc.catch_dynamics import MechazillaCatchSolver, CatchEnvelope
from starship_flip_gnc.test_stand_safety import (
    TestStandSafetyInterlock,
    TestStandMode,
    HoldDownSensorReading,
)
from starship_flip_gnc.touchdown_gate import (
    TouchdownValidationGate,
    AltimeterSensorSuite,
)
from starship_flip_gnc.actuator_fault_allocator import (
    ActuatorFaultAllocator,
    ActuatorTelemetry,
    TorqueDemand,
)
from starship_flip_gnc.engine_out_recovery import (
    EngineOutCompensator,
    EngineTelemetry,
    VehicleState,
)
from starship_flip_gnc.debris_hazard_predictor import (
    DebrisHazardPredictor,
    GeofencePolygon,
    KinematicVector,
)

from starship_cryo_slosh.tank import HeaderTankAssembly, CryogenicFluid
from starship_cryo_slosh.simulator import SloshSimulator
from starship_cryo_slosh.orbital_transfer import OrbitalTransferSimulator

from starship_tps_vision.thermal_map import AerothermalRiskMap
from starship_tps_vision.synthetic import SyntheticTileGridGenerator
from starship_tps_vision.detector import TileDefectDetector
from starship_tps_vision.reporter import InspectionReporter

from starship_geo_sat.launch_abort_detector import (
    LaunchAbortDetector,
    PropulsionTelemetry,
)
from starship_geo_sat.inclined_orbit_dynamics import (
    InclinedOrbitDynamics,
    OrbitalElements,
    GroundStation,
)
from starship_geo_sat.electric_orbit_raising import (
    ElectricOrbitRaisingSimulator,
    EORThrusterConfig,
    SolarArraySpec,
)
from starship_geo_sat.reaction_wheel_desat import (
    ReactionWheelDesaturator,
    WheelAssemblyState,
    SolarPressureProperties,
)
from starship_geo_sat.rfi_transponder_guard import (
    RFITransponderGuard,
    CarrierTelemetry,
    TransponderState,
)


def run_pipeline(output_dir: str = "pipeline_artifacts") -> None:
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    print("================================================================")
    print("           OPEN-STARSHIP ENGINEERING PIPELINE                   ")
    print("================================================================")

    # -------------------------------------------------------------------------
    # STEP 1: Flight Dynamics & Trajectory Optimization (starship-flip-gnc)
    # -------------------------------------------------------------------------
    print("\n[1/7] Running: starship-flip-gnc (Landing Flip Trajectory Solver)...")
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
    print("\n[2/7] Running: starship-cryo-slosh (Header Tank Fluid Slosh)...")
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
    print("\n[3/7] Running: starship-tps-vision (Heat Shield Tile Inspection)...")
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
    print("\n[4/7] Running: Mechazilla Chopstick Catch Solver...")
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
    print("\n[5/7] Running: In-Space Cryogenic Propellant Transfer Simulator...")
    transfer_sim = OrbitalTransferSimulator()
    lox_fluid = CryogenicFluid.liquid_oxygen()
    transfer_res = transfer_sim.simulate_transfer(fluid=lox_fluid, target_mass_kg=80_000.0)
    print(f"      -> Transfer Status: {'SUCCESS' if transfer_res.success else 'FAILED'}")
    print(f"      -> Delivered Mass: {transfer_res.mass_transferred_kg:.0f} kg in {transfer_res.duration_s / 60.0:.1f} min")
    print(f"      -> Flow Rate: {transfer_res.average_flow_rate_kg_s:.1f} kg/s | Transfer Efficiency: {transfer_res.transfer_efficiency_percent:.2f}%")
    print(f"      -> Settling Bond Number: {transfer_res.bond_number:.1f} (Settled: {transfer_res.is_fluid_settled})")

    # -------------------------------------------------------------------------
    # STEP 6: Flight Safety Interlocks & Incident Mitigations
    # -------------------------------------------------------------------------
    print("\n[6/7] Running: Aerospace Incident Safety Interlocks & Mitigations...")

    stand_guard = TestStandSafetyInterlock(mode=TestStandMode.STATIC_FIRE)
    stand_check = stand_guard.evaluate(
        HoldDownSensorReading(
            timestamp_s=2.5,
            vertical_acceleration_mps2=0.01,
            vertical_displacement_m=0.003,
            clamp_tension_force_n=5.8e6,
            umbilical_connected=True,
            engine_commanded_thrust_n=6.0e6,
        )
    )

    touchdown_gate = TouchdownValidationGate()
    touchdown_check = touchdown_gate.evaluate(
        AltimeterSensorSuite(
            timestamp_s=flight_result.touchdown_time_s,
            radar_altimeter_m=0.22,
            lidar_altimeter_m=0.25,
            ins_integrated_alt_m=0.24,
            contact_force_n=72_000.0,
            contact_switches_engaged=4,
        ),
        commanded_engine_cutoff=True,
    )

    actuator_alloc = ActuatorFaultAllocator()
    actuators = [
        ActuatorTelemetry("aft_port", 0.02, 0.02, 14.0),
        ActuatorTelemetry("aft_starboard", 0.02, 0.02, 13.5),
        ActuatorTelemetry("fwd_port", -0.01, -0.01, 8.0),
        ActuatorTelemetry("fwd_starboard", -0.01, -0.01, 8.2),
    ]
    actuator_check = actuator_alloc.allocate(
        TorqueDemand(pitch_nm=5000.0, yaw_nm=0.0, roll_nm=0.0),
        q_dyn_pa=12_000.0,
        actuators=actuators,
    )

    engine_comp = EngineOutCompensator()
    v_state = VehicleState(
        mass_kg=vehicle.dry_mass + flight_result.propellant_remaining_kg,
        gimbal_to_com_distance_m=18.0,
    )
    engines = [
        EngineTelemetry("center", 0.0, 0.0, 225.0, 1.2e6, 1.2e6),
        EngineTelemetry("outer_port", -1.8, 0.0, 225.0, 1.2e6, 1.2e6),
        EngineTelemetry("outer_starboard", 1.8, 0.0, 225.0, 1.2e6, 1.2e6),
    ]
    engine_check = engine_comp.evaluate(
        engines=engines,
        vehicle=v_state,
        target_delta_v_mps=abs(flight_result.final_velocity_z_mps),
        nominal_burn_duration_s=12.0,
    )

    debris_pred = DebrisHazardPredictor(
        zones=[
            GeofencePolygon("Inhabited_Settlement_A", True, 180.0, 240.0, -30.0, 30.0),
            GeofencePolygon("Offshore_Safety_Corridor", False, 0.0, 600.0, -100.0, 100.0),
        ]
    )
    debris_check = debris_pred.evaluate_trajectory(
        KinematicVector(
            altitude_m=500.0,
            downrange_km=0.05,
            crossrange_km=0.01,
            vx_mps=0.05,
            vy_mps=0.0,
            vz_mps=flight_result.final_velocity_z_mps,
        )
    )

    safety_summary = {
        "test_stand_breakaway_interlock": {
            "safe": stand_check.safe,
            "abort_triggered": stand_check.abort_triggered,
            "message": stand_check.message,
        },
        "touchdown_validation_gate": {
            "cutoff_permitted": touchdown_check.cutoff_permitted,
            "override_commanded": touchdown_check.override_commanded,
            "fused_altitude_m": touchdown_check.fused_altitude_m,
            "contact_verified": touchdown_check.contact_verified,
            "message": touchdown_check.message,
        },
        "actuator_fault_allocator": {
            "jammed_surfaces": actuator_check.jammed_surfaces,
            "reallocation_converged": actuator_check.reallocation_converged,
            "status_message": actuator_check.status_message,
        },
        "engine_out_recovery": {
            "failed_engines": engine_check.failed_engines,
            "twr": engine_check.thrust_to_weight_ratio,
            "attitude_controllable": engine_check.attitude_controllable,
            "gravity_arrest_possible": engine_check.gravity_arrest_possible,
            "message": engine_check.message,
        },
        "debris_hazard_predictor": {
            "safe": debris_check.safe,
            "iip_downrange_km": debris_check.iip_downrange_km,
            "afts_destruct_required": debris_check.afts_destruct_required,
            "status_message": debris_check.status_message,
        },
    }

    safety_json_path = out_path / "incident_safety_validation.json"
    with open(safety_json_path, "w", encoding="utf-8") as f:
        json.dump(safety_summary, f, indent=2)

    print(f"      -> Test Stand Clamp Interlock: {'SAFE' if stand_check.safe else 'ABORT'}")
    print(f"      -> Touchdown Validation Gate: {'CUTOFF_PERMITTED' if touchdown_check.cutoff_permitted else 'OVERRIDE_HOVER'}")
    print(f"      -> Actuator Torque Allocation: {'CONVERGED' if actuator_check.reallocation_converged else 'DEGRADED'}")
    print(f"      -> Engine-Out Controllability: {'CONTROLLABLE' if engine_check.attitude_controllable else 'UNCONTROLLABLE'} (TWR={engine_check.thrust_to_weight_ratio:.2f})")
    print(f"      -> Instantaneous Impact Point: {'SAFE_CORRIDOR' if debris_check.safe else 'BREACH_EXCLUSION'}")
    print(f"      -> Safety Validation Report Saved: {safety_json_path}")

    # -------------------------------------------------------------------------
    # STEP 7: Geostationary Satellite Operations (starship-geo-sat / Türksat Fleet)
    # -------------------------------------------------------------------------
    print("\n[7/7] Running: starship-geo-sat (Geostationary Operations & Payload Guard)...")

    # A. Upper-stage abort detector (Türksat 1A)
    abort_detector = LaunchAbortDetector()
    abort_eval = abort_detector.evaluate(
        PropulsionTelemetry(
            timestamp_s=700.0,
            chamber_pressure_bar=34.5,
            turbopump_speed_rpm=61_800.0,
            lox_valve_position_percent=99.0,
            axial_acceleration_mps2=19.2,
            altitude_km=210.0,
            inertial_velocity_mps=9800.0,
        )
    )

    # B. Inclined orbit dynamics & tracking (Türksat 1B/1C)
    inclined_dyn = InclinedOrbitDynamics()
    inclined_eval = inclined_dyn.propagate_drift(
        initial=OrbitalElements(nominal_longitude_deg=42.0),
        elapsed_years=3.5,
        station=GroundStation(),
        current_time_hours=6.0,
        remaining_fuel_kg=15.0,
    )

    # C. Electric Orbit Raising & Radiation Degradation (Türksat 5A/5B)
    eor_sim = ElectricOrbitRaisingSimulator()
    eor_history = eor_sim.simulate_transfer(
        simulation_step_days=10.0,
        max_duration_days=30.0,
    )
    eor_latest = eor_history[-1]

    # D. Zero-magnetic-field reaction wheel desaturation (Türksat 6A)
    desaturator = ReactionWheelDesaturator()
    srp_torque = desaturator.calculate_srp_torque_nm(SolarPressureProperties())
    wheels_accum = desaturator.accumulate_momentum(
        WheelAssemblyState(hx_nms=18.0, hy_nms=16.0, hz_nms=8.0),
        srp_torque,
        duration_hours=48.0,
    )
    desat_plan = desaturator.plan_desaturation(wheels_accum)

    # E. RFI Transponder Guard & Rain Fade AUPC (Türksat 3A/4A/4B)
    rfi_guard = RFITransponderGuard()
    rfi_action = rfi_guard.evaluate_carrier(
        CarrierTelemetry(
            carrier_id="TURKSAT_42E_BEACON",
            frequency_ghz=12.5,
            polarization="V",
            measured_input_power_dbw=-74.5,
            cross_polar_leakage_power_dbw=-108.0,
            rain_rate_mm_per_hr=12.0,
        )
    )

    geo_summary = {
        "launch_abort_detector": {
            "nominal_thrust": abort_eval.nominal_thrust,
            "abort_triggered": abort_eval.abort_triggered,
            "injection_shortfall_mps": abort_eval.injection_shortfall_mps,
            "status_message": abort_eval.status_message,
        },
        "inclined_orbit_dynamics": {
            "current_inclination_deg": inclined_eval.current_inclination_deg,
            "tracking_required": inclined_eval.tracking_required,
            "graveyard_delta_v_mps": inclined_eval.graveyard_delta_v_mps,
            "disposal_safe": inclined_eval.disposal_safe,
            "status_message": inclined_eval.status_message,
        },
        "electric_orbit_raising": {
            "elapsed_days": eor_latest.elapsed_days,
            "perigee_altitude_km": eor_latest.current_perigee_altitude_km,
            "apogee_altitude_km": eor_latest.current_apogee_altitude_km,
            "solar_array_power_watts": eor_latest.solar_array_power_watts,
            "power_degradation_percent": eor_latest.power_degradation_percent,
        },
        "reaction_wheel_desaturation": {
            "desaturation_required": desat_plan.desaturation_required,
            "pulse_duration_s": desat_plan.pulse_duration_s,
            "propellant_consumed_grams": desat_plan.propellant_consumed_grams,
            "station_keeping_deadband_safe": desat_plan.station_keeping_deadband_safe,
            "status_message": desat_plan.status_message,
        },
        "rfi_transponder_guard": {
            "carrier_id": rfi_action.carrier_id,
            "cross_polar_isolation_db": rfi_action.cross_polar_isolation_db,
            "xpi_violation": rfi_action.xpi_violation,
            "twta_saturated": rfi_action.twta_saturated,
            "aupc_recommended_boost_db": rfi_action.aupc_recommended_boost_db,
            "status_message": rfi_action.status_message,
        },
    }

    geo_json_path = out_path / "geo_satellite_validation.json"
    with open(geo_json_path, "w", encoding="utf-8") as f:
        json.dump(geo_summary, f, indent=2)

    print(f"      -> Upper-Stage Injection Status: {'NOMINAL' if abort_eval.nominal_thrust else 'ABORT'}")
    print(f"      -> Inclined Orbit Drift: Inc={inclined_eval.current_inclination_deg:.2f}° (Tracking: {'REQUIRED' if inclined_eval.tracking_required else 'FIXED'})")
    print(f"      -> Electric Orbit Raising: Day {eor_latest.elapsed_days:.0f} (Array Power: {eor_latest.solar_array_power_watts:.0f}W, Loss: -{eor_latest.power_degradation_percent:.1f}%)")
    print(f"      -> Wheel Desaturation: {'PULSED' if desat_plan.desaturation_required else 'HOLD'} (Deadband Safe: {desat_plan.station_keeping_deadband_safe})")
    print(f"      -> Transponder Link Guard: XPI={rfi_action.cross_polar_isolation_db:.1f} dB (AUPC: +{rfi_action.aupc_recommended_boost_db:.1f} dB)")
    print(f"      -> Geostationary Validation Saved: {geo_json_path}")

    print("\n================================================================")
    print("      ALL PHASES COMPLETED AND INTEGRATED SUCCESSFULLY          ")
    print(f"      Output Artifacts: {out_path.resolve()}")
    print("      3D Visualizer: visualizer/index.html")
    print("================================================================\n")


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_artifacts"
    run_pipeline(out_dir)
