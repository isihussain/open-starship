"""
Synthetic hexagonal tile inspection data and defect generator.

Generates ground-truth tile coordinates, geometric edge gaps, and surface
damage patterns for testing inspection algorithms.
"""

from dataclasses import dataclass, asdict
from enum import Enum
import random
from typing import List, Dict, Any


class DefectType(str, Enum):
    NONE = "NONE"
    MISSING_TILE = "MISSING_TILE"       # Entire ceramic tile detached
    CRACKED_TILE = "CRACKED_TILE"       # Transverse fracture across ceramic body
    CHIPPED_EDGE = "CHIPPED_EDGE"       # Corner or border spallation
    EXPANDED_GAP = "EXPANDED_GAP"       # Inter-tile expansion beyond plasma seal limit


@dataclass
class TileObservation:
    """
    Sensor observation parameters for a single hexagonal tile.
    """
    tile_id: str
    z_hull_m: float
    azimuth_deg: float
    surface_area_ratio: float       # 1.0 = intact, <0.15 = missing, 0.7-0.95 = chipped
    crack_length_mm: float          # 0.0 = no crack, >10.0 = structural crack
    max_inter_tile_gap_mm: float    # Nominal is 2.0 mm; >4.5 mm indicates plasma hazard
    ground_truth_defect: DefectType

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ground_truth_defect"] = self.ground_truth_defect.value
        return d


class SyntheticTileGridGenerator:
    """
    Generates realistic geometric grids of hexagonal TPS tiles with injected defects.
    """

    def __init__(self, random_seed: int = 42):
        self.rng = random.Random(random_seed)
        self.nominal_gap_mm = 2.0

    def generate_sector(
        self,
        num_tiles_axial: int = 20,
        num_tiles_azimuthal: int = 15,
        defect_rate: float = 0.08,
    ) -> List[TileObservation]:
        """
        Creates a cylindrical tile array sector with controlled defect distributions.
        """
        observations: List[TileObservation] = []

        # Tile spacing: ~0.35m hexagonal side-to-side pitch
        dz = 0.35
        d_azimuth = 360.0 / 64.0  # ~64 tiles per circumference

        for row in range(num_tiles_axial):
            z = -20.0 + row * dz
            for col in range(num_tiles_azimuthal):
                # Stagger alternate rows for hexagonal close-packing:
                az_offset = 0.5 * d_azimuth if (row % 2 == 1) else 0.0
                az = -60.0 + col * d_azimuth + az_offset
                tile_id = f"T-R{row:02d}-C{col:02d}"

                # Determine if defect is injected:
                if self.rng.random() < defect_rate:
                    defect = self.rng.choice([
                        DefectType.MISSING_TILE,
                        DefectType.CRACKED_TILE,
                        DefectType.CHIPPED_EDGE,
                        DefectType.EXPANDED_GAP,
                    ])
                else:
                    defect = DefectType.NONE

                # Simulate measurement signals based on defect mode:
                if defect == DefectType.MISSING_TILE:
                    area_ratio = self.rng.uniform(0.0, 0.08)
                    crack_len = 0.0
                    gap_mm = self.nominal_gap_mm + self.rng.uniform(15.0, 30.0)
                elif defect == DefectType.CRACKED_TILE:
                    area_ratio = self.rng.uniform(0.96, 1.0)
                    crack_len = self.rng.uniform(25.0, 120.0)
                    gap_mm = self.nominal_gap_mm + self.rng.uniform(0.2, 1.0)
                elif defect == DefectType.CHIPPED_EDGE:
                    area_ratio = self.rng.uniform(0.75, 0.92)
                    crack_len = self.rng.uniform(0.0, 15.0)
                    gap_mm = self.nominal_gap_mm + self.rng.uniform(1.0, 3.5)
                elif defect == DefectType.EXPANDED_GAP:
                    area_ratio = self.rng.uniform(0.97, 1.0)
                    crack_len = 0.0
                    gap_mm = self.rng.uniform(5.0, 9.5)
                else:
                    # Intact nominal tile with measurement noise:
                    area_ratio = self.rng.uniform(0.98, 1.0)
                    crack_len = 0.0
                    gap_mm = self.rng.uniform(1.8, 2.3)

                obs = TileObservation(
                    tile_id=tile_id,
                    z_hull_m=round(z, 3),
                    azimuth_deg=round(az, 2),
                    surface_area_ratio=round(area_ratio, 3),
                    crack_length_mm=round(crack_len, 1),
                    max_inter_tile_gap_mm=round(gap_mm, 2),
                    ground_truth_defect=defect,
                )
                observations.append(obs)

        return observations
