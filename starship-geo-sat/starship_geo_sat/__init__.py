"""
starship-geo-sat: Geostationary and Earth observation satellite operations suite.

Implements failure mitigations, dynamics models, and payload protection derived from:
  1. Türksat Satellite Fleet (Türksat 1A through 6A):
     - Upper-stage turbopump abort detection (Türksat 1A)
     - Inclined orbit secular drift & antenna pointing (Türksat 1B/1C)
     - Electric orbit raising & Van Allen radiation fluence (Türksat 5A/5B)
     - Zero-magnetic-field reaction wheel desaturation (Türksat 6A)
     - Transponder cross-polarization guard & rain fade AUPC (Türksat 3A/4A/4B)
  2. Azercosmos Satellite Fleet (Azerspace-1, Azerspace-2, AzerSky):
     - 0.9° orbital proximity Adjacent Satellite Interference (ASI) and DVB-S2X ACM
       adaptation between Azerspace-1 (46.0°E) and Azerspace-2 (45.1°E)
     - Ground control redundancy: Absheron Main Teleport and Nakhchivan Reserve Teleport
     - AzerSky (SPOT 7) Sun-Synchronous LEO hypervelocity micro-debris collision
       penetration, tumbling dynamics, and SPOT-6 twin service continuity
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
    CathodeErosionReport,
)
from .eclipse_thermal_model import (
    EclipseThermalSimulator,
    BatteryBankSpec,
    EclipseThermalReport,
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
from .azercosmos_orbital_coordination import (
    AzercosmosOrbitalCoordinator,
    GroundStationSite,
    SatelliteSlot,
    AdjacentInterferenceAssessment,
)
from .azersky_debris_conjunction import (
    AzerSkyDebrisAnalyzer,
    AzerSkyOrbitSpec,
    DebrisImpactTelemetry,
    DebrisAnomalyReport,
)
from .hotbird_fleet_operations import (
    HotbirdFleetCoordinator,
    HotbirdSatelliteSpec,
    OrbitalVectorState,
    ColocationSeparationReport,
    EclipseThermalShockReport,
    FleetMigrationReport,
)
from .optical_isl_crosslink import (
    OpticalISLTransceiver,
    OpticalISLConfig,
    JitterSpectrumProfile,
    OpticalLinkReport,
)
from .station_keeping_prognostics import (
    StationKeepingPrognosticator,
    StationKeepingConfig,
    TankPVTReading,
    StationKeepingBudget,
    LifetimePrognosisReport,
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
    "CathodeErosionReport",
    "EclipseThermalSimulator",
    "BatteryBankSpec",
    "EclipseThermalReport",
    "ReactionWheelDesaturator",
    "WheelAssemblyState",
    "SolarPressureProperties",
    "DesaturationPlan",
    "RFITransponderGuard",
    "CarrierTelemetry",
    "TransponderState",
    "PayloadGuardAction",
    "AzercosmosOrbitalCoordinator",
    "GroundStationSite",
    "SatelliteSlot",
    "AdjacentInterferenceAssessment",
    "AzerSkyDebrisAnalyzer",
    "AzerSkyOrbitSpec",
    "DebrisImpactTelemetry",
    "DebrisAnomalyReport",
    "HotbirdFleetCoordinator",
    "HotbirdSatelliteSpec",
    "OrbitalVectorState",
    "ColocationSeparationReport",
    "EclipseThermalShockReport",
    "FleetMigrationReport",
    "OpticalISLTransceiver",
    "OpticalISLConfig",
    "JitterSpectrumProfile",
    "OpticalLinkReport",
    "StationKeepingPrognosticator",
    "StationKeepingConfig",
    "TankPVTReading",
    "StationKeepingBudget",
    "LifetimePrognosisReport",
]
