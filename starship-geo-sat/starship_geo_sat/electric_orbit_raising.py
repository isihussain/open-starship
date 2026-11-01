"""
Electric Orbit Raising (EOR) low-thrust spiral propagator and radiation degradation model.

Mitigates multi-month Van Allen radiation belt degradation incidents
(e.g., Türksat 5A and 5B on Airbus Eurostar E3000EOR platforms, 2021),
where Hall-effect electric thrusters took 140 to 160 days to spiral from GTO to GEO,
accumulating significant non-ionizing energy loss (NIEL) and solar array power degradation.

Integrates low-thrust orbital energy change, evaluates radiation fluence across belt crossings,
and calculates solar cell dark-current degradation and mission power margins.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict
import math


@dataclass
class EORThrusterConfig:
    """
    Electric propulsion subsystem parameters (Hall-effect xenon thrusters).
    """
    total_thrust_n: float = 0.35              # Two 175 mN Hall thrusters firing simultaneously
    specific_impulse_s: float = 1650.0        # Xenon Hall thruster Isp [s]
    duty_cycle_fraction: float = 0.90         # 90% active thrusting per orbit
    initial_wet_mass_kg: float = 3500.0       # Mass at GTO separation [kg]
    target_geo_semi_major_axis_km: float = 42_164.14


@dataclass
class SolarArraySpec:
    """
    Photovoltaic solar array electrical parameters at Beginning-of-Life (BOL).
    """
    bol_power_watts: float = 12_000.0         # 12 kW array at 1 AU
    cell_type: str = "Triple_Junction_GaAs"
    radiation_damage_coefficient: float = 0.048
    reference_fluence: float = 1.0e14         # 1-MeV equivalent electron fluence baseline [e-/cm^2]


@dataclass
class EORProgressReport:
    """
    Orbital parameters, transfer duration, cumulative radiation dose, and power degradation.
    """
    elapsed_days: float
    current_perigee_altitude_km: float
    current_apogee_altitude_km: float
    current_inclination_deg: float
    propellant_consumed_kg: float
    spacecraft_mass_kg: float
    cumulative_1mev_fluence: float            # Equivalent 1-MeV electrons / cm^2
    solar_array_power_watts: float
    power_degradation_percent: float
    target_geo_reached: bool
    status_message: str


class ElectricOrbitRaisingSimulator:
    """
    Propagates continuous low-thrust spiral transfer and integrates radiation damage.
    """

    EARTH_RADIUS_KM = 6378.137
    EARTH_MU = 398600.4418                    # Standard gravitational parameter [km^3 / s^2]
    STANDARD_GRAVITY = 9.80665

    # Van Allen belt altitude boundaries [km]:
    INNER_BELT_PROTON_PEAK_KM = 3000.0        # Intense trapped protons (E > 10 MeV)
    OUTER_BELT_ELECTRON_PEAK_KM = 20_000.0     # Relativistic electrons (E > 1 MeV)

    def __init__(
        self,
        thruster: EORThrusterConfig = EORThrusterConfig(),
        array: SolarArraySpec = SolarArraySpec(),
    ):
        self.thruster = thruster
        self.array = array

    def simulate_transfer(
        self,
        gto_perigee_km: float = 250.0,
        gto_apogee_km: float = 35_786.0,
        gto_inclination_deg: float = 27.0,      # Falcon 9 standard GTO from Cape Canaveral
        simulation_step_days: float = 1.0,
        max_duration_days: float = 180.0,
    ) -> List[EORProgressReport]:
        """
        Simulates spiral transfer from GTO to GEO, recording radiation and power degradation.
        """
        rp = self.EARTH_RADIUS_KM + gto_perigee_km
        ra = self.EARTH_RADIUS_KM + gto_apogee_km
        a = (rp + ra) / 2.0
        inc = gto_inclination_deg
        mass = self.thruster.initial_wet_mass_kg

        r_geo = self.thruster.target_geo_semi_major_axis_km

        ve = self.thruster.specific_impulse_s * self.STANDARD_GRAVITY
        thrust = self.thruster.total_thrust_n
        mdot = thrust / ve                     # kg/s

        cumulative_fluence = 0.0
        elapsed_days = 0.0
        reports = []

        # SECONDS per day active firing:
        active_seconds_per_day = 86_400.0 * self.thruster.duty_cycle_fraction

        while elapsed_days < max_duration_days:
            # Current altitude bounds
            hp = rp - self.EARTH_RADIUS_KM
            ha = ra - self.EARTH_RADIUS_KM

            # Low-thrust rate of change of semi-major axis:
            # da/dt = 2 * a^2 * v * (F/m) / mu = 2 * (F/m) * sqrt(a^3 / mu)
            accel = (thrust / mass) / 1000.0    # km/s^2
            orbital_period_s = 2.0 * math.pi * math.sqrt(a**3 / self.EARTH_MU)

            # Daily energy addition
            v_circ = math.sqrt(self.EARTH_MU / a) # km/s
            delta_v_day = accel * active_seconds_per_day

            # Semi-major axis growth:
            da_day = (2.0 * a * v_circ * delta_v_day) / (self.EARTH_MU / a)
            a = min(r_geo, a + da_day)

            # Circularization and inclination reduction:
            # Circularize by raising perigee faster than apogee:
            if rp < r_geo:
                rp = min(r_geo, rp + (da_day * 1.5))
            ra = (2.0 * a) - rp
            ra = min(r_geo, ra)

            # Plane change rate:
            if inc > 0.05:
                dinc_day = (0.015 * delta_v_day * 1000.0) / v_circ  # deg/day
                inc = max(0.0, inc - dinc_day)

            # Propellant consumed:
            fuel_used_day = mdot * active_seconds_per_day
            mass = max(self.thruster.initial_wet_mass_kg * 0.70, mass - fuel_used_day)

            # Calculate radiation fluence accumulated during this day:
            # Fluence rate is highest when perigee/apogee intersects belt peaks
            alt_mean = (hp + ha) / 2.0
            fluence_rate = self._estimate_belt_fluence_rate(alt_mean)
            cumulative_fluence += fluence_rate * active_seconds_per_day

            # Solar cell power degradation equation:
            # P(t) = P0 * [1 - C * ln(1 + Phi / Phi0)]
            ratio = cumulative_fluence / self.array.reference_fluence
            deg_factor = max(0.60, 1.0 - (self.array.radiation_damage_coefficient * math.log(1.0 + ratio)))
            current_power = self.array.bol_power_watts * deg_factor
            power_loss_pct = (1.0 - deg_factor) * 100.0

            elapsed_days += simulation_step_days

            reached_geo = (a >= (r_geo - 100.0)) and (inc <= 0.5)

            if reached_geo:
                msg = (
                    f"GEO INSERTION COMPLETE: Reached GEO in {elapsed_days:.1f} days. "
                    f"Final power={current_power:.0f} W (Degradation={power_loss_pct:.2f}%). "
                    f"Cumulative fluence={cumulative_fluence:.2e} e-/cm²."
                )
            else:
                msg = (
                    f"EOR Spiral: Day {elapsed_days:.0f}, Alt={hp:.0f}x{ha:.0f} km, inc={inc:.1f}°. "
                    f"Power={current_power:.0f} W."
                )

            report = EORProgressReport(
                elapsed_days=round(elapsed_days, 1),
                current_perigee_altitude_km=round(hp, 1),
                current_apogee_altitude_km=round(ha, 1),
                current_inclination_deg=round(inc, 2),
                propellant_consumed_kg=round(self.thruster.initial_wet_mass_kg - mass, 1),
                spacecraft_mass_kg=round(mass, 1),
                cumulative_1mev_fluence=cumulative_fluence,
                solar_array_power_watts=round(current_power, 1),
                power_degradation_percent=round(power_loss_pct, 2),
                target_geo_reached=reached_geo,
                status_message=msg,
            )
            reports.append(report)

            if reached_geo:
                break

        return reports

    def _estimate_belt_fluence_rate(self, altitude_km: float) -> float:
        """
        Calculates equivalent 1-MeV electron fluence rate [e- / (cm^2 * s)] based on altitude.
        """
        # Inner proton belt peak (~3000 km):
        inner_sigma = 1800.0
        inner_contrib = 6.0e7 * math.exp(-0.5 * ((altitude_km - self.INNER_BELT_PROTON_PEAK_KM) / inner_sigma) ** 2)

        # Outer electron belt peak (~20,000 km):
        outer_sigma = 6000.0
        outer_contrib = 2.5e7 * math.exp(-0.5 * ((altitude_km - self.OUTER_BELT_ELECTRON_PEAK_KM) / outer_sigma) ** 2)

        return inner_contrib + outer_contrib
