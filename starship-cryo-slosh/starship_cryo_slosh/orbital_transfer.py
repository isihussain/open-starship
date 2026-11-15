"""
Orbital cryogenic propellant transfer and microgravity fluid settling simulator.

Models Artemis III and Mars architecture ship-to-ship propellant transfers:
  1. Microgravity RCS ullage settling (Bond number fluid stabilization)
  2. Pressure-differential cryogenic mass transfer (Tanker to Depot)
  3. Radiative boil-off and transfer efficiency management
"""

from dataclasses import dataclass
import math
from typing import Optional, Tuple

from .tank import CryogenicFluid


@dataclass
class TransferConfiguration:
    """
    Orbital propellant transfer interface specifications.
    """
    pipe_diameter_m: float = 0.20           # 8-inch cryogenic transfer line
    flow_discharge_coeff: float = 0.65       # Discharge coefficient Cd
    tanker_ullage_pressure_kpa: float = 280.0# Tanker autogenous pressure [kPa]
    depot_ullage_pressure_kpa: float = 230.0 # Depot back-pressure [kPa]
    ullage_settling_accel_mps2: float = 0.15 # Micro-RCS forward settling acceleration (~0.015 g)
    heat_leak_rate_w_m2: float = 12.0        # Multi-layer insulation (MLI) orbital heat leak


@dataclass
class TransferResult:
    """
    Outcome and performance metrics of an orbital propellant transfer operation.
    """
    success: bool
    mass_transferred_kg: float
    duration_s: float
    average_flow_rate_kg_s: float
    boil_off_loss_kg: float
    transfer_efficiency_percent: float
    bond_number: float
    is_fluid_settled: bool
    message: str


@dataclass
class LineChilldownReport:
    """
    Thermal chill-down and vapor lock assessment for transfer plumbing.
    """
    pipe_mass_kg: float
    chilldown_energy_joules: float
    cryogen_boiloff_for_chill_kg: float
    chilldown_duration_s: float
    vapor_lock_cleared: bool
    status_message: str


class OrbitalTransferSimulator:
    """
    Simulates in-space cryogenic transfer dynamics between docked Starship vehicles.
    """

    def __init__(self, config: Optional[TransferConfiguration] = None):
        self.config = config or TransferConfiguration()

        # Latent heat of vaporization [J/kg]:
        self.h_vap_lox = 213.0e3   # 213 kJ/kg
        self.h_vap_lch4 = 510.0e3  # 510 kJ/kg

    def evaluate_bond_number(self, tank_radius_m: float, fluid: CryogenicFluid) -> Tuple[float, bool]:
        """
        Calculates Bond number to verify whether micro-RCS acceleration overcomes surface tension.
        Bo = (rho * a * R^2) / sigma. Fluid settles stably when Bo > 50.
        """
        bo = (fluid.density_kg_m3 * self.config.ullage_settling_accel_mps2 * (tank_radius_m ** 2)) / fluid.surface_tension_n_m
        is_settled = bo >= 50.0
        return bo, is_settled

    def simulate_transfer(
        self,
        fluid: CryogenicFluid,
        target_mass_kg: float = 100_000.0,
        tank_radius_m: float = 4.5,
    ) -> TransferResult:
        """
        Simulates pressure-driven transfer from Tanker to Depot until target mass is delivered.
        """
        bo, is_settled = self.evaluate_bond_number(tank_radius_m, fluid)
        if not is_settled:
            return TransferResult(
                success=False,
                mass_transferred_kg=0.0,
                duration_s=0.0,
                average_flow_rate_kg_s=0.0,
                boil_off_loss_kg=0.0,
                transfer_efficiency_percent=0.0,
                bond_number=round(bo, 1),
                is_fluid_settled=False,
                message=f"Transfer aborted: Bond number {bo:.1f} < 50.0. Propellant not settled at sump.",
            )

        # Cross-sectional pipe area:
        area_pipe = math.pi * ((self.config.pipe_diameter_m / 2.0) ** 2)

        # Pressure differential driving flow:
        delta_p_pa = (self.config.tanker_ullage_pressure_kpa - self.config.depot_ullage_pressure_kpa) * 1000.0
        if delta_p_pa <= 0.0:
            return TransferResult(
                success=False,
                mass_transferred_kg=0.0,
                duration_s=0.0,
                average_flow_rate_kg_s=0.0,
                boil_off_loss_kg=0.0,
                transfer_efficiency_percent=0.0,
                bond_number=round(bo, 1),
                is_fluid_settled=True,
                message="Transfer failed: Tanker pressure must exceed Depot pressure (Delta P <= 0).",
            )

        # Orifice flow mass rate: m_dot = Cd * A * sqrt(2 * rho * delta_P)
        m_dot = self.config.flow_discharge_coeff * area_pipe * math.sqrt(2.0 * fluid.density_kg_m3 * delta_p_pa)

        # Total transfer duration [s]:
        duration_s = target_mass_kg / m_dot

        # Radiative heat leak and boil-off:
        tank_surface_area = 4.0 * math.pi * (tank_radius_m ** 2)
        total_heat_rate_w = tank_surface_area * self.config.heat_leak_rate_w_m2
        h_vap = self.h_vap_lch4 if fluid.name == "LCH4" else self.h_vap_lox
        boil_off_rate_kg_s = total_heat_rate_w / h_vap
        boil_off_loss_kg = boil_off_rate_kg_s * duration_s

        efficiency = (target_mass_kg / (target_mass_kg + boil_off_loss_kg)) * 100.0

        msg = (
            f"Transferred {target_mass_kg:.0f} kg of {fluid.name} in {duration_s / 60.0:.1f} min "
            f"at {m_dot:.1f} kg/s (Efficiency: {efficiency:.2f}%)."
        )

        return TransferResult(
            success=True,
            mass_transferred_kg=round(target_mass_kg, 1),
            duration_s=round(duration_s, 2),
            average_flow_rate_kg_s=round(m_dot, 2),
            boil_off_loss_kg=round(boil_off_loss_kg, 2),
            transfer_efficiency_percent=round(efficiency, 2),
            bond_number=round(bo, 1),
            is_fluid_settled=True,
            message=msg,
        )

    def evaluate_line_chilldown(
        self,
        fluid: CryogenicFluid,
        line_length_m: float = 12.0,
        pipe_wall_thickness_m: float = 0.003,
        pipe_initial_temp_k: float = 290.0,
        chill_bleed_flow_kg_s: float = 0.85,
    ) -> LineChilldownReport:
        """
        Simulates line pre-cooling transient from ambient temperature down to cryogenic
        saturation temperature, preventing geysering and vapor-lock in transfer pumps.
        """
        # Stainless steel 304L density ~7900 kg/m^3, specific heat ~480 J/(kg*K):
        rho_steel = 7900.0
        cp_steel = 480.0
        r_outer = self.config.pipe_diameter_m / 2.0
        r_inner = r_outer - pipe_wall_thickness_m

        pipe_volume = math.pi * (r_outer ** 2 - r_inner ** 2) * line_length_m
        pipe_mass = pipe_volume * rho_steel

        # Target saturation temperatures: LOX = 90K, LCH4 = 111K
        t_target = 90.0 if fluid.name == "LOX" else 111.0
        delta_t = max(0.0, pipe_initial_temp_k - t_target)

        # Thermal energy required to extract: Q = m * Cp * Delta_T
        q_chill_j = pipe_mass * cp_steel * delta_t

        h_vap = self.h_vap_lox if fluid.name == "LOX" else self.h_vap_lch4
        cryo_boiled_kg = q_chill_j / h_vap

        chill_time_s = cryo_boiled_kg / max(0.01, chill_bleed_flow_kg_s)
        cleared = chill_time_s < 300.0  # Must chill within 5-minute operational timeline

        msg = (
            f"Line chill-down completed in {chill_time_s:.1f}s consuming {cryo_boiled_kg:.1f} kg {fluid.name}. "
            f"Single-phase liquid established across {line_length_m:.1f}m transfer line."
        )

        return LineChilldownReport(
            pipe_mass_kg=round(pipe_mass, 2),
            chilldown_energy_joules=round(q_chill_j, 1),
            cryogen_boiloff_for_chill_kg=round(cryo_boiled_kg, 2),
            chilldown_duration_s=round(chill_time_s, 1),
            vapor_lock_cleared=cleared,
            status_message=msg,
        )
