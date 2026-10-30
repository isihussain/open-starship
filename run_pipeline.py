"""
Open-Starship End-to-End Orchestration Pipeline.

Executes the unified data pipeline:
  1. starship-flip-gnc: Computes landing flip trajectory & writes flight telemetry.
  2. starship-cryo-slosh: Reads telemetry & simulates cryogenic propellant dynamics in header tanks.
  3. starship-tps-vision: Derives aerothermal risk map from flight loads & executes tile inspection.
"""

import sys
import os
from pathlib import Path

# Add child packages to Python path for seamless execution:
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "starship-flip-gnc"))
sys.path.insert(0, str(BASE_DIR / "starship-cryo-slosh"))
sys.path.insert(0, str(BASE_DIR / "starship-tps-vision"))

from starship_flip_gnc.models import StarshipVehicle, FlightState
from starship_flip_gnc.trajectory import TrajectoryOptimizer
from starship_flip_gnc.telemetry import TelemetryLogger

from starship_cryo_slosh.tank import HeaderTankAssembly
from starship_cryo_slosh.simulator import SloshSimulator

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
    print("\n[1/3] Calistiriliyor: starship-flip-gnc (Inis Manevrasi Cozumu)...")
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

    print(f"      -> Ucus Sonucu: {'BASARILI' if flight_result.success else 'BASARISIZ'}")
    print(f"      -> Inis Suresi: {flight_result.touchdown_time_s} s")
    print(f"      -> Son Dikey Hiz: {flight_result.final_velocity_z_mps} m/s | Yunuslama: {flight_result.final_pitch_deg} deg")
    print(f"      -> Harcanan Yakit: {flight_result.propellant_used_kg} kg (Kalan: {flight_result.propellant_remaining_kg} kg)")
    print(f"      -> Telemetri Kaydedildi: {telem_json_path} ({len(gnc_logger.records)} kayit)")

    # -------------------------------------------------------------------------
    # STEP 2: Cryogenic Slosh & Ullage Ingestion (starship-cryo-slosh)
    # -------------------------------------------------------------------------
    print("\n[2/3] Calistiriliyor: starship-cryo-slosh (Header Tank Yakit Calkantisi)...")
    assembly = HeaderTankAssembly.default_starship(with_baffles=True)
    slosh_sim = SloshSimulator(
        assembly=assembly,
        lox_mass_kg=flight_result.propellant_remaining_kg * 0.70,
        ch4_mass_kg=flight_result.propellant_remaining_kg * 0.30,
    )

    slosh_result, slosh_history = slosh_sim.simulate_telemetry(gnc_logger.records)
    slosh_json_path = out_path / "slosh_dynamics.json"
    with open(slosh_json_path, "w", encoding="utf-8") as f:
        import json
        json.dump([pt.to_dict() for pt in slosh_history], f, indent=2)

    print(f"      -> Calkanti Risk Seviyesi: {slosh_result.risk_level}")
    print(f"      -> LOX Gaz Alma: {'VAR' if slosh_result.lox_gas_ingestion_detected else 'YOK'} (Min Derinlik: {slosh_result.lox_min_submergence_m} m)")
    print(f"      -> CH4 Gaz Alma: {'VAR' if slosh_result.ch4_gas_ingestion_detected else 'YOK'} (Min Derinlik: {slosh_result.ch4_min_submergence_m} m)")
    print(f"      -> Tepe Bozulma Torku: {slosh_result.max_slosh_torque_nm} N*m")
    print(f"      -> Tepe Ağırlık Merkezi Kayması: {slosh_result.max_com_shift_x_mm} mm")
    print(f"      -> Calkanti Verisi Kaydedildi: {slosh_json_path}")

    # -------------------------------------------------------------------------
    # STEP 3: TPS Tile Damage Inspection (starship-tps-vision)
    # -------------------------------------------------------------------------
    print("\n[3/3] Calistiriliyor: starship-tps-vision (Isi Kalkani Karo Muayenesi)...")
    risk_map = AerothermalRiskMap.from_telemetry(gnc_logger.records)
    generator = SyntheticTileGridGenerator(random_seed=42)
    observations = generator.generate_sector(num_tiles_axial=30, num_tiles_azimuthal=20, defect_rate=0.06)

    detector = TileDefectDetector(risk_map=risk_map)
    batch_result = detector.inspect_batch(observations)

    tps_json_path = out_path / "tps_inspection_report.json"
    tps_md_path = out_path / "tps_maintenance_work_order.md"
    InspectionReporter.export_json(batch_result, str(tps_json_path))
    InspectionReporter.generate_markdown_report(batch_result, str(tps_md_path))

    print(f"      -> Toplam Denetlenen Karo: {batch_result.total_inspected}")
    print(f"      -> Saglam: {batch_result.intact_count} | Hasarli: {batch_result.defective_count}")
    print(f"         - Eksik: {batch_result.missing_count} | Catlak: {batch_result.cracked_count}")
    print(f"         - Kirik Kenar: {batch_result.chipped_count} | Genisleyen Bosluk: {batch_result.gap_expansion_count}")
    print(f"      -> Acil Degisim Emri (Kritik): {batch_result.critical_replacements_required}")
    print(f"      -> Is Emri Raporu Kaydedildi: {tps_md_path}")

    print("\n================================================================")
    print("       TUM FAZLAR BASARIYLA TAMAMLANDI VE BAGLANDI               ")
    print(f"       Uretilen Ciktilar: {out_path.resolve()}")
    print("================================================================\n")


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_artifacts"
    run_pipeline(out_dir)
