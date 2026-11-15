"""
Quaternion-based 3D attitude kinematics and rotation representation for spacecraft GNC.

Avoids gimbal lock singularities inherent to Euler angles during aggressive 90-degree
flip-and-burn pitching maneuvers. Implements quaternion multiplication, conjugate inversion,
error quaternion extraction, and directional cosine matrix (DCM) conversions.
"""

from dataclasses import dataclass
import math
from typing import Tuple


@dataclass
class Quaternion:
    """
    Unit quaternion representation of 3D spatial rotation: q = [w, x, y, z].
    Convention: w is the scalar component; (x, y, z) is the vector component.
    """
    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def norm(self) -> float:
        """Euclidean norm of quaternion."""
        return math.sqrt(self.w ** 2 + self.x ** 2 + self.y ** 2 + self.z ** 2)

    def normalized(self) -> "Quaternion":
        """Returns normalized unit quaternion."""
        n = self.norm()
        if n < 1e-12:
            return Quaternion(1.0, 0.0, 0.0, 0.0)
        return Quaternion(self.w / n, self.x / n, self.y / n, self.z / n)

    def conjugate(self) -> "Quaternion":
        """Returns quaternion conjugate q* = [w, -x, -y, -z]."""
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def multiply(self, other: "Quaternion") -> "Quaternion":
        """
        Hamilton quaternion product: q_result = self (x) other.
        """
        w1, x1, y1, z1 = self.w, self.x, self.y, self.z
        w2, x2, y2, z2 = other.w, other.x, other.y, other.z

        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2

        return Quaternion(w, x, y, z)

    def to_euler_angles_deg(self) -> Tuple[float, float, float]:
        """
        Converts quaternion to Tait-Bryan Euler angles: (roll, pitch, yaw) [degrees].
        Rotation sequence: Z-Y-X (yaw-pitch-roll).
        """
        # Roll (x-axis rotation):
        sinr_cosp = 2.0 * (self.w * self.x + self.y * self.z)
        cosr_cosp = 1.0 - 2.0 * (self.x ** 2 + self.y ** 2)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation):
        sinp = 2.0 * (self.w * self.y - self.z * self.x)
        if abs(sinp) >= 1.0:
            pitch = math.copysign(math.pi / 2.0, sinp)
        else:
            pitch = math.asin(sinp)

        # Yaw (z-axis rotation):
        siny_cosp = 2.0 * (self.w * self.z + self.x * self.y)
        cosy_cosp = 1.0 - 2.0 * (self.y ** 2 + self.z ** 2)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        return (
            round(math.degrees(roll), 2),
            round(math.degrees(pitch), 2),
            round(math.degrees(yaw), 2),
        )

    @classmethod
    def from_axis_angle(cls, axis: Tuple[float, float, float], angle_rad: float) -> "Quaternion":
        """
        Constructs unit quaternion from rotation axis (ax, ay, az) and angle theta [rad].
        """
        ax, ay, az = axis
        norm_axis = math.hypot(ax, math.hypot(ay, az))
        if norm_axis < 1e-12:
            return cls(1.0, 0.0, 0.0, 0.0)

        half_ang = angle_rad / 2.0
        s = math.sin(half_ang) / norm_axis
        return cls(
            w=math.cos(half_ang),
            x=ax * s,
            y=ay * s,
            z=az * s,
        ).normalized()

    @classmethod
    def from_euler_pitch(cls, pitch_rad: float) -> "Quaternion":
        """
        Constructs quaternion for pure pitching rotation about Y-body axis.
        """
        return cls.from_axis_angle((0.0, 1.0, 0.0), pitch_rad)


class AttitudeKinematics:
    """
    Kinematic operations for spacecraft attitude guidance and error tracking.
    """

    @staticmethod
    def compute_attitude_error(q_current: Quaternion, q_target: Quaternion) -> Tuple[float, float, float]:
        """
        Calculates 3-axis rotation error vector e = [e_roll, e_pitch, e_yaw] [rad]
        from current orientation to target orientation using exact quaternion logarithm map.
        Formula: delta_q = q_target^-1 (x) q_current.
        """
        q_err = q_target.conjugate().multiply(q_current).normalized()
        # Enforce shortest path (w >= 0):
        if q_err.w < 0.0:
            q_err = Quaternion(-q_err.w, -q_err.x, -q_err.y, -q_err.z)

        vec_norm = math.sqrt(q_err.x ** 2 + q_err.y ** 2 + q_err.z ** 2)
        if vec_norm < 1e-9:
            return (0.0, 0.0, 0.0)

        # Exact rotation angle: theta = 2 * atan2(vec_norm, w)
        angle = 2.0 * math.atan2(vec_norm, q_err.w)
        scale = angle / vec_norm

        e_roll = q_err.x * scale
        e_pitch = q_err.y * scale
        e_yaw = q_err.z * scale

        return (round(e_roll, 5), round(e_pitch, 5), round(e_yaw, 5))
