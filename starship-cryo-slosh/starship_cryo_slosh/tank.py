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

    def compute_baffle_damping(
        self,
        fill_fraction: float,
        baffle_width_ratio: float = 0.12,
        baffle_z_locations_norm: tuple[float, ...] = (-0.4, 0.0, 0.4),
    ) -> float:
        """
        Calculates local liquid free-surface hydrodynamic damping ratio using
        Miles & Abramson formulation for annular ring baffles.
        """
        zeta_wall = 0.018
        if not self.has_slosh_baffles:
            return zeta_wall

        # Fluid free surface position along tank z-axis in [-1, +1]:
        z_surface_norm = 2.0 * min(1.0, max(0.0, fill_fraction)) - 1.0

        damping_baffles = 0.0
        # Miles damping parameter: C_b * (w_b / R)^1.5 * exp(-2 * k * |z_surf - z_baffle|)
        for z_b in baffle_z_locations_norm:
            dist = abs(z_surface_norm - z_b)
            contrib = 2.83 * (baffle_width_ratio ** 1.5) * math.exp(-3.68 * dist)
            damping_baffles += contrib

        return round(min(0.25, zeta_wall + damping_baffles), 4)


@dataclass
class UllagePressurizationReport:
    """
    Thermodynamic state and pressure rise rate of unvented cryogenic tank ullage.
    """
    ullage_volume_m3: float
    initial_pressure_kpa: float
    pressure_rise_rate_kpa_per_s: float
    time_to_vent_relief_s: float
    boil_off_rate_kg_s: float


class UllageThermodynamicsModel:
    """
    Thermodynamic self-pressurization model for unvented cryogenic tank coast periods.
    """

    def __init__(
        self,
        tank: HeaderTankGeometry,
        fluid: CryogenicFluid,
        ambient_heat_leak_w: float = 350.0,
        relief_valve_limit_kpa: float = 450.0,
    ):
        self.tank = tank
        self.fluid = fluid
        self.heat_leak_w = ambient_heat_leak_w
        self.relief_pressure_kpa = relief_valve_limit_kpa

    def evaluate_pressurization(
        self,
        fluid_mass_kg: float,
        current_pressure_kpa: float = 280.0,
    ) -> UllagePressurizationReport:
        """
        Solves energy balance for closed cryogenic tank ullage: dP/dt = (Q_dot / V_ullage) * (R / Cv).
        """
        fluid_vol = fluid_mass_kg / self.fluid.density_kg_m3
        ullage_vol = max(0.05, self.tank.total_volume_m3 - fluid_vol)

        # Cryogenic latent heat [J/kg]:
        h_vap = 213.0e3 if self.fluid.name == "LOX" else 510.0e3
        boil_off_kg_s = self.heat_leak_w / h_vap

        # Ideal gas constant and specific heat for methane or oxygen:
        r_gas = 259.8 if self.fluid.name == "LOX" else 518.3  # J / (kg * K)
        cv = 650.0 if self.fluid.name == "LOX" else 1700.0   # J / (kg * K)

        # Pressure rise rate [Pa/s -> kPa/s]:
        dp_dt_pa = (self.heat_leak_w / ullage_vol) * (r_gas / cv)
        dp_dt_kpa = dp_dt_pa / 1000.0

        headroom_kpa = max(0.0, self.relief_pressure_kpa - current_pressure_kpa)
        time_to_vent = headroom_kpa / max(1e-5, dp_dt_kpa)

        return UllagePressurizationReport(
            ullage_volume_m3=round(ullage_vol, 3),
            initial_pressure_kpa=round(current_pressure_kpa, 1),
            pressure_rise_rate_kpa_per_s=round(dp_dt_kpa, 4),
            time_to_vent_relief_s=round(time_to_vent, 1),
            boil_off_rate_kg_s=round(boil_off_kg_s, 6),
        )


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
