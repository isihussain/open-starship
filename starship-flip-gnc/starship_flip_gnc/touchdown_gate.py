"""
Multi-sensor touchdown validation gate and premature engine cutoff interlock.

Mitigates VTVL landing failures (e.g., Deep Blue Aerospace Nebula-1, September 2024),
where ground dust or rocket plume reflection tricked a single radar altimeter into reporting
zero altitude at 5 meters above pad, causing premature engine shutdown and a free-fall crash.

Enforces a dual-condition gate: engine shutdown requires BOTH multi-sensor altitude consensus
AND physical mechanical contact confirmation (Weight-on-Wheels / Chopstick pin load cells).
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple
import math


@dataclass
class AltimeterSensorSuite:
    """
    Multi-channel altitude measurements at landing terminal phase.
    """
    timestamp_s: float
    radar_altimeter_m: float
    lidar_altimeter_m: float
    ins_integrated_alt_m: float
    contact_force_n: float            # Measured compressive load on landing gear / catch pins [N]
    contact_switches_engaged: int     # Number of physical microswitches engaged (0 to 4)


@dataclass
class TouchdownGateResult:
    """
    Validation decision on commanded engine cutoff.
    """
    cutoff_permitted: bool
    override_commanded: bool          # True if flight software overrides premature shutdown
    override_throttle: float          # Safe hover throttle to maintain if cutoff rejected
    fused_altitude_m: float
    contact_verified: bool
    plume_reflection_detected: bool
    discrepancy_m: float
    message: str


class TouchdownValidationGate:
    """
    Dual-condition safety gate prohibiting engine cutoff without physical contact.
    """

    def __init__(
        self,
        cutoff_altitude_threshold_m: float = 0.40,
        min_contact_force_n: float = 40_000.0,      # 40 kN minimum compressive contact
        min_switches_required: int = 2,              # At least 2 of 4 contact switches
        max_sensor_divergence_m: float = 2.0,        # Threshold for sensor anomaly detection
        default_hover_throttle: float = 0.52,
    ):
        self.cutoff_alt_thresh = cutoff_altitude_threshold_m
        self.min_contact_force = min_contact_force_n
        self.min_switches = min_switches_required
        self.max_divergence = max_sensor_divergence_m
        self.hover_throttle = default_hover_throttle

    def evaluate(self, sensors: AltimeterSensorSuite, commanded_engine_cutoff: bool) -> TouchdownGateResult:
        """
        Validates engine cutoff request against multi-channel sensors and mechanical contact.
        """
        # 1. Detect plume/dust backscatter on radar altimeter:
        # If radar reads near-zero while LiDAR and INS still report several meters:
        divergence = abs(sensors.lidar_altimeter_m - sensors.radar_altimeter_m)
        plume_anomaly = (
            sensors.radar_altimeter_m < 0.8
            and sensors.lidar_altimeter_m > self.max_divergence
            and sensors.ins_integrated_alt_m > self.max_divergence
        )

        # 2. Compute fault-tolerant fused altitude:
        if plume_anomaly:
            # Reject corrupted radar altimeter, trust LiDAR and INS:
            fused_alt = 0.60 * sensors.lidar_altimeter_m + 0.40 * sensors.ins_integrated_alt_m
        else:
            # Standard weighted median consensus:
            alts = sorted([sensors.radar_altimeter_m, sensors.lidar_altimeter_m, sensors.ins_integrated_alt_m])
            fused_alt = alts[1]  # Median filter rejects single outlier

        # 3. Check physical mechanical contact:
        force_ok = sensors.contact_force_n >= self.min_contact_force
        switch_ok = sensors.contact_switches_engaged >= self.min_switches
        contact_verified = force_ok and switch_ok

        alt_ok = fused_alt <= self.cutoff_alt_thresh

        # Dual-condition rule: Both altitude AND physical contact must be confirmed
        cutoff_permitted = commanded_engine_cutoff and alt_ok and contact_verified

        if commanded_engine_cutoff and not cutoff_permitted:
            # Premature shutdown attempted without physical ground confirmation:
            reasons = []
            if not alt_ok:
                reasons.append(f"fused altitude {fused_alt:.2f}m > threshold {self.cutoff_alt_thresh:.2f}m")
            if not contact_verified:
                reasons.append(
                    f"contact unconfirmed (load={sensors.contact_force_n / 1e3:.1f}kN, switches={sensors.contact_switches_engaged})"
                )
            if plume_anomaly:
                reasons.append("radar altimeter plume backscatter anomaly detected")

            msg = "PREMATURE CUTOFF OVERRIDDEN: " + "; ".join(reasons)
            return TouchdownGateResult(
                cutoff_permitted=False,
                override_commanded=True,
                override_throttle=self.hover_throttle,
                fused_altitude_m=round(fused_alt, 3),
                contact_verified=contact_verified,
                plume_reflection_detected=plume_anomaly,
                discrepancy_m=round(divergence, 3),
                message=msg,
            )

        if cutoff_permitted:
            msg = (
                f"Touchdown confirmed: altitude={fused_alt:.2f}m, "
                f"contact_force={sensors.contact_force_n / 1e3:.1f}kN. Engine cutoff safe."
            )
        else:
            msg = f"Descent tracking nominal: altitude={fused_alt:.2f}m, contact={contact_verified}."

        return TouchdownGateResult(
            cutoff_permitted=cutoff_permitted,
            override_commanded=False,
            override_throttle=0.0,
            fused_altitude_m=round(fused_alt, 3),
            contact_verified=contact_verified,
            plume_reflection_detected=plume_anomaly,
            discrepancy_m=round(divergence, 3),
            message=msg,
        )
