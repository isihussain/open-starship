"""
Geostationary equinox eclipse thermal transient and battery depth-of-discharge (DoD) model.

Simulates 44-day equinox eclipse seasons in GEO orbit, where spacecraft enter Earth's
shadow for up to 72 minutes daily. Models solar panel radiative cooldown, bus electrical
power discharge from lithium-ion battery banks, and temperature drops across the payload deck.
"""

from dataclasses import dataclass
import math
from typing import List, Tuple


@dataclass
class BatteryBankSpec:
    """
    Onboard energy storage system parameters (Space-grade Li-Ion battery).
    """
    capacity_watt_hours: float = 18_000.0     # 18 kWh battery
    nominal_bus_voltage_v: float = 100.0      # 100 V regulated bus
    max_allowable_dod_percent: float = 75.0   # 75% maximum Depth-of-Discharge ceiling
    battery_charge_efficiency: float = 0.94


@dataclass
class EclipseThermalReport:
    """
    Thermal-electrical status during and immediately following eclipse transit.
    """
    eclipse_duration_minutes: float
    final_solar_panel_temp_k: float
    final_payload_deck_temp_k: float
    energy_consumed_watt_hours: float
    depth_of_discharge_percent: float
    dod_within_safety_margin: bool
    recharge_duration_hours: float
    status_message: str


class EclipseThermalSimulator:
    """
    Propagates non-linear radiative cooldown and battery state-of-charge during shadow transit.
    """

    STEFAN_BOLTZMANN = 5.670374e-8
    DEEP_SPACE_TEMP_K = 3.0

    def __init__(
        self,
        battery: BatteryBankSpec = BatteryBankSpec(),
        solar_array_area_m2: float = 45.0,
        solar_array_mass_kg: float = 140.0,
        payload_deck_thermal_mass_j_k: float = 350_000.0,
        bus_power_consumption_watts: float = 4800.0,
    ):
        self.battery = battery
        self.array_area = solar_array_area_m2
        self.array_mass = solar_array_mass_kg
        self.deck_thermal_mass = payload_deck_thermal_mass_j_k
        self.bus_power_w = bus_power_consumption_watts

        # Specific heat capacity of carbon-composite solar array substrates:
        self.cp_substrate = 920.0  # J / (kg * K)

    def simulate_eclipse(
        self,
        eclipse_duration_minutes: float = 72.0,
        initial_array_temp_k: float = 330.0,
        initial_deck_temp_k: float = 293.15,
        heater_power_watts: float = 400.0,
        solar_array_emissivity: float = 0.85,
    ) -> EclipseThermalReport:
        """
        Simulates thermal radiation cooldown into deep space and battery drain during eclipse.
        """
        duration_s = eclipse_duration_minutes * 60.0
        dt = 5.0  # 5-second numerical integration step

        t_array = initial_array_temp_k
        t_deck = initial_deck_temp_k

        total_energy_wh = 0.0
        total_power_w = self.bus_power_w + heater_power_watts

        # Solar array thermal mass [J/K]:
        array_thermal_mass = self.array_mass * self.cp_substrate

        time_elapsed = 0.0
        while time_elapsed < duration_s:
            # Array radiation to space (front + rear surfaces = 2 * area):
            q_rad_array = 2.0 * self.array_area * solar_array_emissivity * self.STEFAN_BOLTZMANN * (t_array ** 4 - self.DEEP_SPACE_TEMP_K ** 4)
            dt_array = -(q_rad_array / array_thermal_mass) * dt
            t_array = max(40.0, t_array + dt_array)

            # Internal payload deck cooldown (insulated by MLI blanket, heat leak ~ 85 W):
            q_leak_deck = 85.0 - heater_power_watts
            dt_deck = -(q_leak_deck / self.deck_thermal_mass) * dt
            t_deck = max(260.0, t_deck + dt_deck)

            # Battery discharge:
            energy_step_wh = (total_power_w * dt) / 3600.0
            total_energy_wh += energy_step_wh

            time_elapsed += dt

        dod_percent = (total_energy_wh / self.battery.capacity_watt_hours) * 100.0
        dod_ok = dod_percent <= self.battery.max_allowable_dod_percent

        # Time to fully recharge battery upon solar re-illumination:
        solar_power_available_w = 12_000.0
        net_recharge_power = (solar_power_available_w - self.bus_power_w) * self.battery.battery_charge_efficiency
        recharge_hours = total_energy_wh / max(100.0, net_recharge_power)

        if dod_ok:
            msg = (
                f"Eclipse transit complete: {eclipse_duration_minutes:.0f} min shadow. "
                f"Array cooled to {t_array:.1f} K, DoD={dod_percent:.1f}% (within {self.battery.max_allowable_dod_percent:.0f}% limit). "
                f"Full recharge in {recharge_hours:.2f} hours."
            )
        else:
            msg = (
                f"BATTERY OVER-DISCHARGE WARNING: DoD={dod_percent:.1f}% exceeds limit "
                f"{self.battery.max_allowable_dod_percent:.0f}%. Non-essential payload shedding required."
            )

        return EclipseThermalReport(
            eclipse_duration_minutes=round(eclipse_duration_minutes, 1),
            final_solar_panel_temp_k=round(t_array, 2),
            final_payload_deck_temp_k=round(t_deck, 2),
            energy_consumed_watt_hours=round(total_energy_wh, 1),
            depth_of_discharge_percent=round(dod_percent, 2),
            dod_within_safety_margin=dod_ok,
            recharge_duration_hours=round(recharge_hours, 2),
            status_message=msg,
        )
