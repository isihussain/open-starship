"""
Foreign Function Interface (FFI) bridge connecting Python to the C99 flight dynamics kernel.

Loads or dynamically compiles the freestanding starship_core.c kernel to execute
4th-order Runge-Kutta numerical integration steps at native execution speeds.
"""

import ctypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from .models import FlightState, StarshipVehicle


class NativeFlightState(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_double),
        ("z", ctypes.c_double),
        ("vx", ctypes.c_double),
        ("vz", ctypes.c_double),
        ("theta", ctypes.c_double),
        ("omega", ctypes.c_double),
        ("propellant_mass", ctypes.c_double),
    ]


class NativeVehicleParams(ctypes.Structure):
    _fields_ = [
        ("dry_mass", ctypes.c_double),
        ("max_thrust_per_engine", ctypes.c_double),
        ("isp_sea_level", ctypes.c_double),
        ("length", ctypes.c_double),
        ("diameter", ctypes.c_double),
        ("gimbal_moment_arm", ctypes.c_double),
        ("moment_of_inertia_pitch", ctypes.c_double),
    ]


class NativeControlInput(ctypes.Structure):
    _fields_ = [
        ("throttle", ctypes.c_double),
        ("gimbal_rad", ctypes.c_double),
        ("active_engines", ctypes.c_int32),
    ]


class NativeFlightCoreBridge:
    """
    Manages loading, compiling, and dispatching to the native C99 flight dynamics library.
    """

    def __init__(self):
        self.lib = None
        self._load_or_compile_library()

    def _get_lib_path(self) -> Path:
        base_dir = Path(__file__).resolve().parent.parent / "native"
        ext = ".dylib" if sys.platform == "darwin" else ".so"
        return base_dir / f"libstarship_core{ext}"

    def _load_or_compile_library(self) -> None:
        lib_path = self._get_lib_path()
        c_src_path = lib_path.parent / "starship_core.c"

        if not lib_path.exists() and c_src_path.exists():
            # Attempt compilation via standard C toolchain:
            try:
                cmd = ["cc", "-O3", "-shared", "-fPIC", str(c_src_path), "-o", str(lib_path), "-lm"]
                subprocess.run(cmd, check=True, capture_output=True)
            except Exception:
                self.lib = None
                return

        if lib_path.exists():
            try:
                loaded = ctypes.CDLL(str(lib_path))
                loaded.native_step_rk4.argtypes = [
                    ctypes.POINTER(NativeFlightState),
                    ctypes.POINTER(NativeVehicleParams),
                    ctypes.POINTER(NativeControlInput),
                    ctypes.c_double,
                ]
                loaded.native_step_rk4.restype = None
                self.lib = loaded
            except Exception:
                self.lib = None

    @property
    def is_available(self) -> bool:
        return self.lib is not None

    def step_rk4(
        self,
        state: FlightState,
        vehicle: StarshipVehicle,
        throttle: float,
        gimbal_rad: float,
        active_engines: int,
        dt: float,
    ) -> FlightState:
        """
        Executes one RK4 step through the native C library.
        """
        if not self.is_available:
            raise RuntimeError("Native C flight core is not available.")

        s_c = NativeFlightState(
            x=state.x,
            z=state.z,
            vx=state.vx,
            vz=state.vz,
            theta=state.theta,
            omega=state.omega,
            propellant_mass=state.propellant_mass,
        )

        v_c = NativeVehicleParams(
            dry_mass=vehicle.dry_mass,
            max_thrust_per_engine=vehicle.engines.max_thrust_per_engine,
            isp_sea_level=vehicle.engines.isp_sea_level,
            length=vehicle.length,
            diameter=vehicle.diameter,
            gimbal_moment_arm=vehicle.gimbal_moment_arm,
            moment_of_inertia_pitch=vehicle.moment_of_inertia_pitch,
        )

        u_c = NativeControlInput(
            throttle=throttle,
            gimbal_rad=gimbal_rad,
            active_engines=active_engines,
        )

        self.lib.native_step_rk4(ctypes.byref(s_c), ctypes.byref(v_c), ctypes.byref(u_c), ctypes.c_double(dt))

        return FlightState(
            time=state.time + dt,
            x=s_c.x,
            z=s_c.z,
            vx=s_c.vx,
            vz=s_c.vz,
            theta=s_c.theta,
            omega=s_c.omega,
            propellant_mass=s_c.propellant_mass,
        )
