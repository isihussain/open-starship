"""
Flight telemetry definitions and serialization for cross-module integration.

Provides strict schemas and export utilities (JSON, CSV) connecting the GNC solver
to downstream cryo-slosh and TPS inspection pipelines.
"""

from dataclasses import dataclass, asdict
import json
import csv
from typing import List, Dict, Any
from pathlib import Path


@dataclass
class TelemetryRecord:
    """
    Instantaneous flight dynamics and environmental record.
    """
    time_s: float
    altitude_m: float
    downrange_m: float
    velocity_x_mps: float
    velocity_z_mps: float
    speed_mps: float
    pitch_deg: float
    pitch_rate_deg_s: float
    throttle: float
    gimbal_deg: float
    thrust_n: float
    drag_n: float
    lift_n: float
    dynamic_pressure_pa: float
    heat_flux_w_m2: float
    total_mass_kg: float
    accel_lateral_mps2: float
    accel_axial_mps2: float
    gimbal_cmd_deg: float = 0.0
    propellant_mass_kg: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return asdict(self)


class TelemetryLogger:
    """
    Collects, validates, and serializes flight trajectory telemetry.
    """

    def __init__(self):
        self.records: List[TelemetryRecord] = []

    def log(self, record: TelemetryRecord) -> None:
        """Append record to time-series."""
        self.records.append(record)

    def clear(self) -> None:
        """Reset records."""
        self.records.clear()

    def export_json(self, file_path: str, indent: int = 2) -> None:
        """
        Export telemetry time-series to standard JSON format.
        """
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = [r.to_dict() for r in self.records]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent)

    def export_csv(self, file_path: str) -> None:
        """
        Export telemetry time-series to CSV format.
        """
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not self.records:
            return

        keys = list(self.records[0].to_dict().keys())
        with open(p, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for r in self.records:
                writer.writerow(r.to_dict())

    @staticmethod
    def load_json(file_path: str) -> List[TelemetryRecord]:
        """
        Load telemetry from JSON file and validate into TelemetryRecord objects.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            raw_list = json.load(f)
        return [TelemetryRecord(**item) for item in raw_list]
