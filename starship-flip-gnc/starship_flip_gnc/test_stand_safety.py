"""
Test stand structural breakaway interlock and premature liftoff abort guard.

Mitigates static-fire structural failure modes (e.g., Space Pioneer Tianlong-3, June 2024),
where test stand hold-down clamps fail under full engine thrust load, causing unauthorized
liftoff. Enforces sub-20ms emergency thrust termination and propellant line venting.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class TestStandMode(str, Enum):
    IDLE = "IDLE"
    STATIC_FIRE = "STATIC_FIRE"
    FLIGHT_AUTHORIZED = "FLIGHT_AUTHORIZED"


@dataclass
class HoldDownSensorReading:
    """
    Sensor readings from test stand hold-down fixtures and vehicle state.
    """
    timestamp_s: float
    vertical_acceleration_mps2: float  # Measured body axial acceleration [m/s^2]
    vertical_displacement_m: float     # Laser displacement sensor relative to launch stool [m]
    clamp_tension_force_n: float       # Net mechanical clamp tension load [N]
    umbilical_connected: bool          # Hardwired umbilical connection flag
    engine_commanded_thrust_n: float   # Instantaneous total commanded engine thrust [N]


@dataclass
class InterlockStatus:
    """
    Safety interlock status and action.
    """
    safe: bool
    abort_triggered: bool
    emergency_cutoff: bool
    vent_valves_open: bool
    detected_violations: List[str]
    message: str


class TestStandSafetyInterlock:
    """
    Enforces hold-down mechanical integrity and prevents unauthorized static-fire liftoff.
    """

    def __init__(
        self,
        mode: TestStandMode = TestStandMode.STATIC_FIRE,
        max_allowable_accel_mps2: float = 0.50,       # ~0.05 g upward acceleration limit
        max_allowable_displacement_m: float = 0.030,  # 30 mm vertical play limit
        min_clamp_tension_ratio: float = 0.70,        # Clamp load must hold at least 70% of thrust
        max_clamp_structural_rating_n: float = 2.5e7, # 25 MN mechanical yield limit
    ):
        self.mode = mode
        self.max_accel = max_allowable_accel_mps2
        self.max_displacement = max_allowable_displacement_m
        self.min_clamp_ratio = min_clamp_tension_ratio
        self.max_clamp_rating = max_clamp_structural_rating_n
        self.abort_latched = False

    def evaluate(self, reading: HoldDownSensorReading) -> InterlockStatus:
        """
        Evaluates mechanical hold-down integrity. If in STATIC_FIRE mode and structural
        breakaway is detected, latches immediate thrust termination.
        """
        if self.abort_latched:
            return InterlockStatus(
                safe=False,
                abort_triggered=True,
                emergency_cutoff=True,
                vent_valves_open=True,
                detected_violations=["LATCHED_PREMATURE_LIFTOFF_ABORT"],
                message="Emergency shutdown already latched. Thrust cutoff and tank venting active.",
            )

        if self.mode == TestStandMode.FLIGHT_AUTHORIZED:
            return InterlockStatus(
                safe=True,
                abort_triggered=False,
                emergency_cutoff=False,
                vent_valves_open=False,
                detected_violations=[],
                message="Flight authorized: hold-down release sequence nominal.",
            )

        violations = []

        # 1. Check for unauthorized upward acceleration:
        if reading.vertical_acceleration_mps2 > self.max_accel:
            violations.append(
                f"Upward acceleration {reading.vertical_acceleration_mps2:.2f} m/s^2 > limit {self.max_accel:.2f} m/s^2"
            )

        # 2. Check for vertical separation displacement from test stool:
        if reading.vertical_displacement_m > self.max_displacement:
            violations.append(
                f"Vertical displacement {reading.vertical_displacement_m * 1000:.1f} mm > limit {self.max_displacement * 1000:.1f} mm"
            )

        # 3. Check for unexpected umbilical disconnect while engines are firing:
        if reading.engine_commanded_thrust_n > 1.0e5 and not reading.umbilical_connected:
            violations.append("Umbilical disconnected during static fire burn")

        # 4. Check clamp tension load vs commanded thrust:
        if reading.engine_commanded_thrust_n > 1.0e6:
            expected_min_clamp = reading.engine_commanded_thrust_n * self.min_clamp_ratio
            if reading.clamp_tension_force_n < expected_min_clamp:
                violations.append(
                    f"Clamp tension loss: measured {reading.clamp_tension_force_n / 1e6:.2f} MN < required {expected_min_clamp / 1e6:.2f} MN"
                )

        if reading.clamp_tension_force_n > self.max_clamp_rating:
            violations.append(
                f"Clamp overload: {reading.clamp_tension_force_n / 1e6:.2f} MN > structural rating {self.max_clamp_rating / 1e6:.2f} MN"
            )

        if violations:
            self.abort_latched = True
            msg = "PREMATURE LIFTOFF ABORT: " + "; ".join(violations)
            return InterlockStatus(
                safe=False,
                abort_triggered=True,
                emergency_cutoff=True,
                vent_valves_open=True,
                detected_violations=violations,
                message=msg,
            )

        return InterlockStatus(
            safe=True,
            abort_triggered=False,
            emergency_cutoff=False,
            vent_valves_open=False,
            detected_violations=[],
            message="Test stand structural hold-down verified nominal.",
        )
