"""
Vehicle physical models and state representations for Starship landing dynamics.

Defines mass distribution, geometry, engine limits, and instantaneous 3-DoF states.
"""

from dataclasses import dataclass, field
import math


@dataclass
class EngineCluster:
    """
    Center landing engine cluster configuration (e.g. 3 center Raptor 3 engines).
    
    Attributes:
        num_engines: Number of active landing engines.
        max_thrust_per_engine: Maximum sea-level thrust per engine [N].
        min_throttle: Minimum throttle ratio (e.g. 0.40 = 40%).
        max_throttle: Maximum throttle ratio (1.0 = 100%).
        max_gimbal_deg: Maximum thrust vectoring angle from vehicle centerline [degrees].
        max_gimbal_rate_deg_s: Maximum gimbal slew rate [deg/s].
        isp_sea_level: Specific impulse at sea level [s].
    """
    num_engines: int = 3
    max_thrust_per_engine: float = 2.25e6  # 2.25 MN (~230 tf per engine)
    min_throttle: float = 0.40
    max_throttle: float = 1.00
    max_gimbal_deg: float = 15.0
    max_gimbal_rate_deg_s: float = 20.0
    isp_sea_level: float = 330.0  # seconds

    @property
    def max_thrust_total(self) -> float:
        """Total maximum thrust available across all active landing engines [N]."""
        return self.num_engines * self.max_thrust_per_engine

    @property
    def min_thrust_total(self) -> float:
        """Total minimum throttleable thrust across all active landing engines [N]."""
        return self.max_thrust_total * self.min_throttle

    @property
    def max_gimbal_rad(self) -> float:
        """Maximum gimbal angle converted to radians."""
        return math.radians(self.max_gimbal_deg)


@dataclass
class StarshipVehicle:
    """
    Starship structural and inertial parameters.

    Coordinate system conventions:
      - X: Downrange position [m], pointing in the landing direction.
      - Z: Vertical altitude [m], pointing upward away from ground.
      - Theta (pitch): 0 rad is vertical (nose up, engines pointing to ground).
                       pi/2 rad (90 deg) is horizontal belly-flop posture.
      - Coordinate origin is the ground touchdown target at (0, 0).
    """
    dry_mass: float = 100_000.0  # kg
    landing_propellant_mass: float = 25_000.0  # kg (LOX + LCH4 in nose/header tanks)
    length: float = 50.0  # meters
    diameter: float = 9.0  # meters
    # Engine gimbal pivot distance from vehicle geometric center along body axis [m]
    # Negative value indicates aft position towards engine skirt.
    gimbal_pivot_z_body: float = -24.0
    # Center of mass position along body axis relative to geometric center [m]
    # Header tanks in nose offset aft engine weight; typically sits aft of midpoint.
    com_z_body: float = -5.0
    engines: EngineCluster = field(default_factory=EngineCluster)

    @property
    def total_mass(self) -> float:
        """Instantaneous total vehicle mass [kg]."""
        return self.dry_mass + self.landing_propellant_mass

    @property
    def moment_of_inertia_pitch(self) -> float:
        """
        Approximate pitch moment of inertia (I_yy) about center of mass [kg*m^2].
        Calculated as a thin-walled cylindrical shell plus distributed payload/tanks.
        Formula: I = m * (3*R^2 + L^2) / 12
        """
        r = self.diameter / 2.0
        return self.total_mass * (3.0 * (r ** 2) + (self.length ** 2)) / 12.0

    @property
    def gimbal_moment_arm(self) -> float:
        """
        Distance from vehicle center of mass to engine gimbal pivot [m].
        Moment produced by gimbal angle delta: M = F_thrust * sin(delta) * moment_arm.
        """
        return abs(self.com_z_body - self.gimbal_pivot_z_body)

    @property
    def nose_radius(self) -> float:
        """Equivalent nose curvature radius for aerothermal stagnation calculation [m]."""
        return 4.5


@dataclass
class FlightState:
    """
    Instantaneous 3-DoF state in the vertical flight plane.
    """
    time: float = 0.0          # Time since maneuver initiation [s]
    x: float = 0.0             # Horizontal downrange position [m]
    z: float = 500.0           # Altitude above ground level [m]
    vx: float = 0.0            # Horizontal velocity [m/s]
    vz: float = -70.0          # Vertical velocity [m/s] (negative indicates descent)
    theta: float = math.pi / 2 # Pitch angle [rad] (pi/2 = 90 deg horizontal belly-flop)
    omega: float = 0.0         # Pitch angular velocity [rad/s]
    propellant_mass: float = 25_000.0  # Remaining landing propellant [kg]

    @property
    def speed(self) -> float:
        """Scalar flight speed magnitude [m/s]."""
        return math.hypot(self.vx, self.vz)

    @property
    def pitch_deg(self) -> float:
        """Pitch angle in degrees."""
        return math.degrees(self.theta)

    @property
    def omega_deg_s(self) -> float:
        """Pitch rate in degrees per second."""
        return math.degrees(self.omega)
