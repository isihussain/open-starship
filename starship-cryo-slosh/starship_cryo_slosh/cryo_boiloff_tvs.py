"""
Cryogenic propellant depot boiloff and Thermodynamic Vent System (TVS) simulator.

Models long-duration orbital storage of cryogenic propellants (LOX and LCH4):
  - Multi-Layer Insulation (MLI) thermal radiation heat leak (Lockheed-Martin model)
  - Structural strut and feedline heat conduction bridges
  - Two-phase saturated tank thermodynamic self-pressurization
  - Active Thermodynamic Vent System (TVS) Joule-Thomson expansion cooling
  - Automated pressure deadband regulation and boiloff mass preservation
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import math


@dataclass
class CryoFluidProperties:
    """Thermodynamic saturation properties of cryogenic liquids."""
    name: str
    saturation_temp_k: float              # Boiling point at 1 atm (K)
    latent_heat_j_kg: float               # Latent heat of vaporization (J/kg)
    liquid_density_kg_m3: float           # Saturated liquid density (kg/m^3)
    vapor_density_kg_m3: float            # Saturated vapor density at 1 atm (kg/m^3)
    specific_heat_liquid_j_kg_k: float    # Specific heat capacity c_p (J/(kg*K))
    gas_constant_j_kg_k: float            # Individual gas constant R (J/(kg*K))

    @classmethod
    def liquid_oxygen(cls) -> "CryoFluidProperties":
        return cls(
            name="LOX",
            saturation_temp_k=90.18,
            latent_heat_j_kg=213000.0,
            liquid_density_kg_m3=1141.0,
            vapor_density_kg_m3=4.42,
            specific_heat_liquid_j_kg_k=1699.0,
            gas_constant_j_kg_k=259.8,
        )

    @classmethod
    def liquid_methane(cls) -> "CryoFluidProperties":
        return cls(
            name="LCH4",
            saturation_temp_k=111.66,
            latent_heat_j_kg=510000.0,
            liquid_density_kg_m3=422.8,
            vapor_density_kg_m3=1.82,
            specific_heat_liquid_j_kg_k=3480.0,
            gas_constant_j_kg_k=518.3,
        )


@dataclass
class MLISpec:
    """Multi-Layer Insulation blanket parameters."""
    layer_count: int = 50                 # Number of double-aluminized Mylar (DAM) layers
    hot_boundary_temp_k: float = 260.0    # Mean orbital surface temperature (K)
    residual_gas_pressure_pa: float = 1e-3  # Space vacuum residual pressure (Pa)
    tank_surface_area_m2: float = 180.0   # Tank outer shell surface area (m^2)
    strut_conduction_area_m2: float = 0.015  # Solid cross-section of support struts
    strut_length_m: float = 1.2           # Strut length (m)
    strut_conductivity_w_m_k: float = 8.5 # Low-conductivity titanium alloy Ti-6Al-4V


@dataclass
class DepotThermalState:
    """Instantaneous thermal and pressure state of an orbital storage tank."""
    time_days: float
    tank_pressure_bar: float
    bulk_temperature_k: float
    propellant_mass_kg: float
    vented_vapor_mass_kg: float
    net_heat_leak_watts: float
    tvs_active: bool


@dataclass
class DepotStorageReport:
    """Summary of long-duration depot storage simulation."""
    fluid_name: str
    duration_days: float
    initial_propellant_kg: float
    final_propellant_kg: float
    total_boiloff_vented_kg: float
    boiloff_loss_percent: float
    max_tank_pressure_bar: float
    relief_valve_tripped: bool
    tvs_duty_cycle_percent: float
    storage_outcome: str                 # "NOMINAL_TVS_REGULATED", "PRESSURE_OVERLIMIT_VENTING"
    states: List[DepotThermalState] = field(default_factory=list)


class CryoBoiloffTVSSimulator:
    """
    Simulates thermal heat leaks, tank pressurization, and TVS cooling in orbital depots.

    Physics formulations:
      Lockheed-Martin MLI heat flux correlation:
        q_mli = (C_rad * (T_hot^4.67 - T_cold^4.67) / N)
              + (C_cond * T_mean * (T_hot - T_cold) / N)
              + (C_gas * P_res * (T_hot^0.52 - T_cold^0.52))

      Structural conduction:
        Q_strut = (k_strut * A_strut / L_strut) * (T_hot - T_cold)

      Clausius-Clapeyron saturation pressure:
        P_sat(T) = P_ref * exp(-(h_fg / R) * (1/T - 1/T_ref))

      Thermodynamic Vent System (TVS) cooling duty:
        Q_tvs = m_dot_bleed * h_fg
        Vents dry expanded vapor at low saturation pressure.
    """

    C_RAD = 7.07e-10    # W / (m^2 * K^4.67)
    C_COND = 7.30e-7   # W / (m * K^2)
    C_GAS = 1.46e-2    # W / (m^2 * Pa * K^0.52)
    BAR_TO_PA = 100000.0
    ATM_PRESSURE_PA = 101325.0

    def __init__(
        self,
        fluid: Optional[CryoFluidProperties] = None,
        mli_spec: Optional[MLISpec] = None,
        tank_volume_m3: float = 85.0,
        initial_fill_fraction: float = 0.90,
        tvs_bleed_rate_kg_s: float = 0.0035,
        target_pressure_bar: float = 2.0,
        pressure_deadband_bar: float = 0.15,
        relief_pressure_bar: float = 2.80,
    ):
        self.fluid = fluid or CryoFluidProperties.liquid_oxygen()
        self.mli = mli_spec or MLISpec()
        self.tank_volume_m3 = tank_volume_m3
        self.fill_fraction = initial_fill_fraction
        self.tvs_bleed_rate = tvs_bleed_rate_kg_s
        self.p_target = target_pressure_bar
        self.p_deadband = pressure_deadband_bar
        self.p_relief = relief_pressure_bar

    def calculate_mli_heat_flux_w_m2(self, t_cold_k: float) -> float:
        """
        Calculates heat flux across the MLI blanket [W/m^2] via Lockheed-Martin equation.
        """
        t_hot = self.mli.hot_boundary_temp_k
        n = max(1, self.mli.layer_count)
        t_mean = 0.5 * (t_hot + t_cold_k)

        # Radiative term
        q_rad = (self.C_RAD * (t_hot ** 4.67 - t_cold_k ** 4.67)) / n

        # Solid conduction across spacer netting
        q_cond = (self.C_COND * t_mean * (t_hot - t_cold_k)) / n

        # Residual gas conduction in space vacuum
        q_gas = self.C_GAS * self.mli.residual_gas_pressure_pa * (t_hot ** 0.52 - t_cold_k ** 0.52)

        return max(0.01, q_rad + q_cond + q_gas)

    def calculate_strut_conduction_watts(self, t_cold_k: float) -> float:
        """Calculates solid heat conduction through structural mounting struts [W]."""
        delta_t = self.mli.hot_boundary_temp_k - t_cold_k
        q_strut = (
            self.mli.strut_conductivity_w_m_k
            * self.mli.strut_conduction_area_m2
            * delta_t
        ) / self.mli.strut_length_m
        return max(0.0, q_strut)

    def compute_saturation_pressure_bar(self, temperature_k: float) -> float:
        """Calculates saturation vapor pressure [bar] from bulk liquid temperature."""
        t_ref = self.fluid.saturation_temp_k
        h_fg = self.fluid.latent_heat_j_kg
        r_gas = self.fluid.gas_constant_j_kg_k

        # Clausius-Clapeyron integration
        exponent = -(h_fg / r_gas) * ((1.0 / temperature_k) - (1.0 / t_ref))
        # Clamp exponent to prevent numerical overflow
        exponent = max(-10.0, min(10.0, exponent))
        p_pa = self.ATM_PRESSURE_PA * math.exp(exponent)
        return p_pa / self.BAR_TO_PA

    def compute_temperature_from_pressure_k(self, pressure_bar: float) -> float:
        """Calculates saturation temperature [K] from tank pressure."""
        p_pa = max(0.1, pressure_bar) * self.BAR_TO_PA
        t_ref = self.fluid.saturation_temp_k
        h_fg = self.fluid.latent_heat_j_kg
        r_gas = self.fluid.gas_constant_j_kg_k

        denom = (1.0 / t_ref) - (r_gas / h_fg) * math.log(p_pa / self.ATM_PRESSURE_PA)
        if denom <= 0.0:
            return t_ref
        return 1.0 / denom

    def simulate_storage(
        self,
        duration_days: float = 30.0,
        enable_tvs: bool = True,
        initial_pressure_bar: float = 1.6,
        dt_seconds: float = 600.0,
    ) -> DepotStorageReport:
        """
        Simulates multi-day depot cryogenic storage with thermal leaks and TVS subcooling.
        """
        # Initial mass calculation
        liquid_vol = self.tank_volume_m3 * self.fill_fraction
        propellant_mass = liquid_vol * self.fluid.liquid_density_kg_m3
        initial_mass = propellant_mass

        tank_pressure = initial_pressure_bar
        bulk_temp = self.compute_temperature_from_pressure_k(tank_pressure)

        total_time_seconds = duration_days * 86400.0
        time_elapsed = 0.0
        vented_mass_total = 0.0
        tvs_active_time = 0.0
        max_pressure = tank_pressure
        relief_tripped = False

        states: List[DepotThermalState] = []
        tvs_is_on = False

        record_interval_s = 86400.0  # Daily snapshot
        next_record_time = 0.0

        while time_elapsed <= total_time_seconds:
            # 1. Total heat leak into tank
            q_mli_flux = self.calculate_mli_heat_flux_w_m2(bulk_temp)
            q_mli_total = q_mli_flux * self.mli.tank_surface_area_m2
            q_struts = self.calculate_strut_conduction_watts(bulk_temp)
            q_net_in = q_mli_total + q_struts

            # 2. TVS controller logic
            q_cooling = 0.0
            if enable_tvs:
                if tank_pressure >= (self.p_target + self.p_deadband):
                    tvs_is_on = True
                elif tank_pressure <= (self.p_target - self.p_deadband):
                    tvs_is_on = False

                if tvs_is_on:
                    # Bleed flow evaporation extracts latent heat
                    q_cooling = self.tvs_bleed_rate * self.fluid.latent_heat_j_kg
                    m_vent = self.tvs_bleed_rate * dt_seconds
                    propellant_mass -= m_vent
                    vented_mass_total += m_vent
                    tvs_active_time += dt_seconds

            # 3. Relief valve emergency passive venting
            if tank_pressure >= self.p_relief:
                relief_tripped = True
                # Vent vapor to arrest pressure rise
                boiloff_rate = q_net_in / self.fluid.latent_heat_j_kg
                m_relief = boiloff_rate * dt_seconds
                propellant_mass -= m_relief
                vented_mass_total += m_relief
                q_cooling += q_net_in  # Latent heat carried away by boiloff

            # 4. Net thermal energy and temperature change
            delta_q_net = (q_net_in - q_cooling) * dt_seconds
            heat_capacity = propellant_mass * self.fluid.specific_heat_liquid_j_kg_k
            delta_t = delta_q_net / heat_capacity
            bulk_temp += delta_t

            # 5. Pressure update from new liquid saturation temperature
            tank_pressure = self.compute_saturation_pressure_bar(bulk_temp)
            if tank_pressure > max_pressure:
                max_pressure = tank_pressure

            # Record daily state
            if time_elapsed >= next_record_time:
                states.append(
                    DepotThermalState(
                        time_days=round(time_elapsed / 86400.0, 2),
                        tank_pressure_bar=round(tank_pressure, 3),
                        bulk_temperature_k=round(bulk_temp, 2),
                        propellant_mass_kg=round(propellant_mass, 1),
                        vented_vapor_mass_kg=round(vented_mass_total, 2),
                        net_heat_leak_watts=round(q_net_in, 1),
                        tvs_active=tvs_is_on,
                    )
                )
                next_record_time += record_interval_s

            time_elapsed += dt_seconds

        boiloff_percent = (vented_mass_total / initial_mass) * 100.0
        tvs_duty = (tvs_active_time / total_time_seconds) * 100.0 if total_time_seconds > 0 else 0.0

        outcome = "NOMINAL_TVS_REGULATED" if (enable_tvs and not relief_tripped) else (
            "PRESSURE_OVERLIMIT_VENTING" if relief_tripped else "PASSIVE_STORAGE_UNCOOLED"
        )

        return DepotStorageReport(
            fluid_name=self.fluid.name,
            duration_days=duration_days,
            initial_propellant_kg=round(initial_mass, 1),
            final_propellant_kg=round(propellant_mass, 1),
            total_boiloff_vented_kg=round(vented_mass_total, 2),
            boiloff_loss_percent=round(boiloff_percent, 3),
            max_tank_pressure_bar=round(max_pressure, 3),
            relief_valve_tripped=relief_tripped,
            tvs_duty_cycle_percent=round(tvs_duty, 1),
            storage_outcome=outcome,
            states=states,
        )
