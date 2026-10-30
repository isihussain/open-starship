"""
Command line interface for starship-tps-vision.
"""

import argparse
import json
import sys
from pathlib import Path

from .thermal_map import AerothermalRiskMap
from .synthetic import SyntheticTileGridGenerator
from .detector import TileDefectDetector
from .reporter import InspectionReporter


def main():
    parser = argparse.ArgumentParser(
        description="Inspect TPS heat shield tiles and generate risk-weighted repair work orders."
    )
    parser.add_argument(
        "--telemetry",
        type=str,
        default="",
        help="Optional path to flight telemetry JSON from starship-flip-gnc to weigh aerothermal risk.",
    )
    parser.add_argument(
        "--tiles-axial",
        type=int,
        default=25,
        help="Number of axial tile rows to generate in test sector (default: 25)",
    )
    parser.add_argument(
        "--tiles-azimuthal",
        type=int,
        default=20,
        help="Number of azimuthal tile columns to generate in test sector (default: 20)",
    )
    parser.add_argument(
        "--defect-rate",
        type=float,
        default=0.06,
        help="Simulated anomaly rate (default: 0.06 = 6%%)",
    )
    parser.add_argument(
        "--export-json",
        type=str,
        default="",
        help="Path to export inspection report JSON",
    )
    parser.add_argument(
        "--export-markdown",
        type=str,
        default="",
        help="Path to export maintenance work order Markdown",
    )

    args = parser.parse_args()

    # 1. Initialize risk map:
    if args.telemetry and Path(args.telemetry).exists():
        with open(args.telemetry, "r", encoding="utf-8") as f:
            telem_data = json.load(f)
        risk_map = AerothermalRiskMap.from_telemetry(telem_data)
        print(f"Loaded flight telemetry: Peak Heat Flux = {risk_map.peak_heat_flux:.1f} W/m^2, Peak Q = {risk_map.peak_q_dyn:.1f} Pa")
    else:
        risk_map = AerothermalRiskMap()
        print("Using standard aerothermal risk baseline.")

    # 2. Generate inspection dataset:
    generator = SyntheticTileGridGenerator()
    observations = generator.generate_sector(
        num_tiles_axial=args.tiles_axial,
        num_tiles_azimuthal=args.tiles_azimuthal,
        defect_rate=args.defect_rate,
    )
    print(f"Generated {len(observations)} synthetic tile observations.")

    # 3. Detect and prioritize:
    detector = TileDefectDetector(risk_map=risk_map)
    batch_result = detector.inspect_batch(observations)

    print("\n--- TPS Inspection Summary ---")
    print(f"Total Tiles Inspected: {batch_result.total_inspected}")
    print(f"Intact: {batch_result.intact_count} ({batch_result.intact_count / batch_result.total_inspected * 100:.1f}%)")
    print(f"Defective: {batch_result.defective_count} ({batch_result.defective_count / batch_result.total_inspected * 100:.1f}%)")
    print(f"  - Missing Tiles: {batch_result.missing_count}")
    print(f"  - Cracked Tiles: {batch_result.cracked_count}")
    print(f"  - Chipped Edges: {batch_result.chipped_count}")
    print(f"  - Gap Expansions: {batch_result.gap_expansion_count}")
    print(f"Critical Replacements Required: {batch_result.critical_replacements_required}")

    # 4. Export reports:
    if args.export_json:
        InspectionReporter.export_json(batch_result, args.export_json)
        print(f"Exported JSON report to {args.export_json}")

    if args.export_markdown:
        InspectionReporter.generate_markdown_report(batch_result, args.export_markdown)
        print(f"Exported Markdown work order to {args.export_markdown}")

    sys.exit(0)


if __name__ == "__main__":
    main()
