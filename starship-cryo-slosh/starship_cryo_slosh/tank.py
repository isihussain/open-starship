"""
Cryogenic fluid properties and header tank geometric specifications.
"""

from dataclasses import dataclass
import math


@dataclass
class CryogenicFluid:
    """
    Physical properties of cryogenic rocket propellants at boiling point.
    """
    name: str
    density_kg_m3: float       # Density [kg/m^3]
    kinematic_viscosity_m2_s: float  # Kinematic viscosity [m^2/s]
    surface_tension_n_m: float # Surface tension [N/m]

    @classmethod
    def liquid_oxygen(cls) -> "CryogenicFluid":
        """Liquid Oxygen (LOX) at 90 K."""
        return cls(
            name="LOX",
            density_kg_m3=1141.0,
            kinematic_viscosity_m2_s=1.7e-7,
            surface_tension_n_m=0.0132,
        )

    @classmethod
    def liquid_methane(cls) -> "CryogenicFluid":
        """Liquid Methane (LCH4) at 111 K."""
        return cls(
            name="LCH4",
            density_kg_m3=422.0,
            kinematic_viscosity_m2_s=3.5e-7,
            surface_tension_n_m=0.0150,
        )


@dataclass
class HeaderTankGeometry:
    """
    Spherical header tank geometry with engine suction intake location.

    Attributes:
        radius_m: Tank internal radius [m].
        z_position_vehicle_m: Position of tank center along vehicle body axis [m].
        suction_inlet_z_local_m: Suction intake z-coordinate in local tank frame [m]
                                 (-radius_m represents bottom pole).
        suction_inlet_x_local_m: Suction intake x-coordinate in local tank frame [m].
        intake_submergence_threshold_m: Minimum liquid depth above inlet before gas ingestion.
        has_slosh_baffles: Boolean indicating internal damping baffle rings.
    """
    radius_m: float
    z_position_vehicle_m: float
    suction_inlet_z_local_m: float
    suction_inlet_x_local_m: float = 0.0
    intake_submergence_threshold_m: float = 0.12  # 12 cm minimum liquid coverage
    has_slosh_baffles: bool = False

    @property
    def total_volume_m3(self) -> float:
        """Total spherical tank volume [m^3]."""
        return (4.0 / 3.0) * math.pi * (self.radius_m ** 3)

    @property
    def damping_ratio(self) -> float:
        """
        Hydrodynamic damping ratio zeta.
        Unbaffled clean walls have very low damping (~0.015); annular ring baffles increase to ~0.08.
        """
        return 0.085 if self.has_slosh_baffles else 0.018


@dataclass
class HeaderTankAssembly:
    """
    Starship landing propellant header tank pair:
    1. Nose Cone LOX Header Tank (forward tip of vehicle).
    2. Common Dome Methane Header Tank (mid-aft tank section).
    """
    lox_tank: HeaderTankGeometry
    ch4_tank: HeaderTankGeometry

    @classmethod
    def default_starship(cls, with_baffles: bool = False) -> "HeaderTankAssembly":
        """
        Default geometry matching Starship Block 2/3 dimensions.
        """
        # Nose LOX tank sits in vehicle tip (~ +21m from geometric center):
        # Radius ~1.55m -> Volume ~15.6 m^3 -> LOX mass ~17,800 kg
        lox = HeaderTankGeometry(
            radius_m=1.55,
            z_position_vehicle_m=21.0,
            suction_inlet_z_local_m=-1.45,
            suction_inlet_x_local_m=0.0,
            intake_submergence_threshold_m=0.15,
            has_slosh_baffles=with_baffles,
        )
        # Methane header tank sits in the inter-tank common dome (~ -2m):
        # Radius ~1.60m -> Volume ~17.1 m^3 -> LCH4 mass ~7,200 kg
        ch4 = HeaderTankGeometry(
            radius_m=1.60,
            z_position_vehicle_m=-2.0,
            suction_inlet_z_local_m=-1.50,
            suction_inlet_x_local_m=0.0,
            intake_submergence_threshold_m=0.15,
            has_slosh_baffles=with_baffles,
        )
        return cls(lox_tank=lox, ch4_tank=ch4)
