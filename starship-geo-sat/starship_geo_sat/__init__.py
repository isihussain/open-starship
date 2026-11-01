"""
starship-geo-sat: Geostationary satellite operations, electric orbit raising, and payload protection module.

Implements failure mitigations and dynamics models derived from the Türksat satellite program:
  1. launch_abort_detector: Cryogenic upper-stage turbopump failure and suborbital fallback (Türksat 1A).
  2. inclined_orbit_dynamics: Station-keeping fuel depletion and lunisolar drift tracking (Türksat 1B/1C).
  3. electric_orbit_raising: Hall-effect low-thrust spiral transfer and Van Allen radiation degradation (Türksat 5A/5B).
  4. reaction_wheel_desat: Zero-magnetic-field reaction wheel momentum desaturation via thrusters (Türksat 6A).
  5. rfi_transponder_guard: Transponder cross-polarization interference and Ka-band rain fade AUPC (Türksat 3A/4A/4B).
"""

from .launch_abort_detector import (
    LaunchAbortDetector,
    PropulsionTelemetry,
    AbortAssessment,
)
from .inclined_orbit_dynamics import (
    InclinedOrbitDynamics,
    OrbitalElements,
    GroundStation,
    InclinedOrbitReport,
)
from .electric_orbit_raising import (
    ElectricOrbitRaisingSimulator,
    EORThrusterConfig,
    SolarArraySpec,
    EORProgressReport,
)
from .reaction_wheel_desat import (
    ReactionWheelDesaturator,
    WheelAssemblyState,
    SolarPressureProperties,
    DesaturationPlan,
)
from .rfi_transponder_guard import (
    RFITransponderGuard,
    CarrierTelemetry,
    TransponderState,
    PayloadGuardAction,
)

__all__ = [
    "LaunchAbortDetector",
    "PropulsionTelemetry",
    "AbortAssessment",
    "InclinedOrbitDynamics",
    "OrbitalElements",
    "GroundStation",
    "InclinedOrbitReport",
    "ElectricOrbitRaisingSimulator",
    "EORThrusterConfig",
    "SolarArraySpec",
    "EORProgressReport",
    "ReactionWheelDesaturator",
    "WheelAssemblyState",
    "SolarPressureProperties",
    "DesaturationPlan",
    "RFITransponderGuard",
    "CarrierTelemetry",
    "TransponderState",
    "PayloadGuardAction",
]
