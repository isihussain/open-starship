"""
starship-flip-gnc: Starship landing flip trajectory, guidance, and aerospace safety interlock module.
"""

from .models import StarshipVehicle, EngineCluster, FlightState, TVCActuator
from .aerodynamics import (
    AerodynamicModel,
    Atmosphere,
    WindModel,
    StandardAtmosphere1976,
    RadiativeEquilibriumThermalModel,
    DrydenTurbulenceModel,
)
from .quaternion_attitude import Quaternion, AttitudeKinematics
from .trajectory import TrajectoryOptimizer, SimulationResult
from .telemetry import TelemetryRecord, TelemetryLogger, TelemetryIntegritySigner
from .catch_dynamics import CatchEnvelope, CatchResult, MechazillaCatchSolver
from .native_bridge import NativeFlightCoreBridge
from .test_stand_safety import (
    TestStandSafetyInterlock,
    TestStandMode,
    HoldDownSensorReading,
    InterlockStatus,
)
from .touchdown_gate import (
    TouchdownValidationGate,
    AltimeterSensorSuite,
    TouchdownGateResult,
)
from .actuator_fault_allocator import (
    ActuatorFaultAllocator,
    ActuatorTelemetry,
    TorqueDemand,
    AllocationResult,
)
from .engine_out_recovery import (
    EngineOutCompensator,
    EngineTelemetry,
    VehicleState,
    CompensationPlan,
)
from .debris_hazard_predictor import (
    DebrisHazardPredictor,
    GeofencePolygon,
    KinematicVector,
    DebrisFootprintReport,
)
from .atmospheric_entry import (
    AtmosphericEntrySolver,
    EntryState,
    EntryCorridorLimits,
    EntryTrajectoryProfile,
)
from .lunar_hls_landing import (
    LunarHLSPlumeSolver,
    LunarLandingState,
    PlumeErosionReport,
    EjectaRiskAssessment,
)

__all__ = [
    "StarshipVehicle",
    "EngineCluster",
    "FlightState",
    "TVCActuator",
    "AerodynamicModel",
    "Atmosphere",
    "WindModel",
    "StandardAtmosphere1976",
    "RadiativeEquilibriumThermalModel",
    "DrydenTurbulenceModel",
    "Quaternion",
    "AttitudeKinematics",
    "TrajectoryOptimizer",
    "SimulationResult",
    "TelemetryRecord",
    "TelemetryLogger",
    "TelemetryIntegritySigner",
    "CatchEnvelope",
    "CatchResult",
    "MechazillaCatchSolver",
    "NativeFlightCoreBridge",
    "TestStandSafetyInterlock",
    "TestStandMode",
    "HoldDownSensorReading",
    "InterlockStatus",
    "TouchdownValidationGate",
    "AltimeterSensorSuite",
    "TouchdownGateResult",
    "ActuatorFaultAllocator",
    "ActuatorTelemetry",
    "TorqueDemand",
    "AllocationResult",
    "EngineOutCompensator",
    "EngineTelemetry",
    "VehicleState",
    "CompensationPlan",
    "DebrisHazardPredictor",
    "GeofencePolygon",
    "KinematicVector",
    "DebrisFootprintReport",
    "AtmosphericEntrySolver",
    "EntryState",
    "EntryCorridorLimits",
    "EntryTrajectoryProfile",
    "LunarHLSPlumeSolver",
    "LunarLandingState",
    "PlumeErosionReport",
    "EjectaRiskAssessment",
]
