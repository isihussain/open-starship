"""
Tile defect classification and risk-weighted prioritization engine.

Fuses computer-vision geometric observations with aerothermal flight risk maps
to generate ranked maintenance work orders.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from .thermal_map import AerothermalRiskMap
from .synthetic import TileObservation, DefectType


@dataclass
class TileInspectionResult:
    """
    Inspection classification and maintenance urgency for a single tile.
    """
    tile_id: str
    z_hull_m: float
    azimuth_deg: float
    zone_id: str
    detected_defect: DefectType
    severity_level: str           # "CRITICAL", "HIGH", "MEDIUM", "LOW", "PASS"
    risk_multiplier: float
    priority_score: float         # base_severity * risk_multiplier
    action_required: str          # "REPLACE_IMMEDIATELY", "FILL_GAP", "MONITOR", "NONE"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["detected_defect"] = self.detected_defect.value
        return d


@dataclass
class InspectionBatchResult:
    """
    Summary metrics for a batch inspection of hull tiles.
    """
    total_inspected: int
    intact_count: int
    defective_count: int
    missing_count: int
    cracked_count: int
    chipped_count: int
    gap_expansion_count: int
    critical_replacements_required: int
    results: List[TileInspectionResult]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_inspected": self.total_inspected,
            "intact_count": self.intact_count,
            "defective_count": self.defective_count,
            "missing_count": self.missing_count,
            "cracked_count": self.cracked_count,
            "chipped_count": self.chipped_count,
            "gap_expansion_count": self.gap_expansion_count,
            "critical_replacements_required": self.critical_replacements_required,
            "results": [r.to_dict() for r in self.results],
        }


class TileDefectDetector:
    """
    Classifies tile defects from geometric sensor readings and ranks severity
    using flight aerothermal environment maps.
    """

    def __init__(self, risk_map: Optional[AerothermalRiskMap] = None):
        self.risk_map = risk_map or AerothermalRiskMap()

        # Detection thresholds:
        self.missing_area_threshold = 0.20     # Below 20% area = missing
        self.chipped_area_threshold = 0.94     # Below 94% area = chipped edge
        self.crack_length_threshold_mm = 20.0  # Above 20mm = structural crack
        self.gap_hazard_threshold_mm = 4.5     # Above 4.5mm = plasma risk gap

    def inspect_tile(self, obs: TileObservation) -> TileInspectionResult:
        """
        Classifies defect and calculates environment-weighted priority score.
        """
        # 1. Defect classification
        if obs.surface_area_ratio < self.missing_area_threshold:
            defect = DefectType.MISSING_TILE
            base_severity = 10.0
            action = "REPLACE_IMMEDIATELY"
        elif obs.crack_length_mm >= self.crack_length_threshold_mm:
            defect = DefectType.CRACKED_TILE
            base_severity = 7.5
            action = "REPLACE_IMMEDIATELY"
        elif obs.max_inter_tile_gap_mm >= self.gap_hazard_threshold_mm:
            defect = DefectType.EXPANDED_GAP
            base_severity = 5.0
            action = "SHIM_OR_REINSTALL"
        elif obs.surface_area_ratio < self.chipped_area_threshold:
            defect = DefectType.CHIPPED_EDGE
            base_severity = 3.5
            action = "APPLY_RTV_PATCH_OR_MONITOR"
        else:
            defect = DefectType.NONE
            base_severity = 0.0
            action = "NONE"

        # 2. Correlate with aerothermal flight risk
        zone_id, risk_mult = self.risk_map.evaluate_tile_risk(obs.z_hull_m, obs.azimuth_deg)
        priority = round(base_severity * risk_mult, 1)

        # 3. Severity grade assignment:
        if priority >= 12.0:
            severity = "CRITICAL"
        elif priority >= 6.5:
            severity = "HIGH"
        elif priority >= 3.0:
            severity = "MEDIUM"
        elif priority > 0.0:
            severity = "LOW"
        else:
            severity = "PASS"

        return TileInspectionResult(
            tile_id=obs.tile_id,
            z_hull_m=obs.z_hull_m,
            azimuth_deg=obs.azimuth_deg,
            zone_id=zone_id,
            detected_defect=defect,
            severity_level=severity,
            risk_multiplier=risk_mult,
            priority_score=priority,
            action_required=action,
        )

    def inspect_batch(self, observations: List[TileObservation]) -> InspectionBatchResult:
        """
        Executes inspection across a collection of tile observations.
        """
        results: List[TileInspectionResult] = []

        missing_c = 0
        cracked_c = 0
        chipped_c = 0
        gap_c = 0
        intact_c = 0
        critical_c = 0

        for obs in observations:
            res = self.inspect_tile(obs)
            results.append(res)

            if res.detected_defect == DefectType.NONE:
                intact_c += 1
            else:
                if res.detected_defect == DefectType.MISSING_TILE:
                    missing_c += 1
                elif res.detected_defect == DefectType.CRACKED_TILE:
                    cracked_c += 1
                elif res.detected_defect == DefectType.CHIPPED_EDGE:
                    chipped_c += 1
                elif res.detected_defect == DefectType.EXPANDED_GAP:
                    gap_c += 1

                if res.severity_level == "CRITICAL":
                    critical_c += 1

        # Sort results descending by priority score:
        results.sort(key=lambda r: r.priority_score, reverse=True)

        return InspectionBatchResult(
            total_inspected=len(observations),
            intact_count=intact_c,
            defective_count=len(observations) - intact_c,
            missing_count=missing_c,
            cracked_count=cracked_c,
            chipped_count=chipped_c,
            gap_expansion_count=gap_c,
            critical_replacements_required=critical_c,
            results=results,
        )
