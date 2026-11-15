"""
starship-tps-vision: Starship Thermal Protection System (TPS) tile inspection pipeline.
"""

from .thermal_map import HullThermalZone, AerothermalRiskMap
from .synthetic import (
    TileObservation,
    SyntheticTileGridGenerator,
    DefectType,
    HexAxialCoord,
    TileSpatialClusterAnalyzer,
)
from .detector import (
    TileDefectDetector,
    TileInspectionResult,
    InspectionBatchResult,
    MultiSpectralObservation,
    MultiSpectralInspectionResult,
    InspectionMetricsEngine,
)
from .reporter import InspectionReporter

__all__ = [
    "HullThermalZone",
    "AerothermalRiskMap",
    "TileObservation",
    "SyntheticTileGridGenerator",
    "DefectType",
    "HexAxialCoord",
    "TileSpatialClusterAnalyzer",
    "TileDefectDetector",
    "TileInspectionResult",
    "InspectionBatchResult",
    "MultiSpectralObservation",
    "MultiSpectralInspectionResult",
    "InspectionMetricsEngine",
    "InspectionReporter",
]
