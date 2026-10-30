"""
starship-tps-vision: Starship Thermal Protection System (TPS) tile inspection pipeline.
"""

from .thermal_map import HullThermalZone, AerothermalRiskMap
from .synthetic import TileObservation, SyntheticTileGridGenerator, DefectType
from .detector import TileDefectDetector, TileInspectionResult, InspectionBatchResult
from .reporter import InspectionReporter

__all__ = [
    "HullThermalZone",
    "AerothermalRiskMap",
    "TileObservation",
    "SyntheticTileGridGenerator",
    "DefectType",
    "TileDefectDetector",
    "TileInspectionResult",
    "InspectionBatchResult",
    "InspectionReporter",
]
