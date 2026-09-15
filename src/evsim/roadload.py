"""Longitudinal road-load model (FR-2).

The tractive force the vehicle must deliver at the wheels to follow a given
speed/acceleration state is

    F_trac = F_inertia + F_roll + F_aero + F_grade

with

    F_inertia = lambda * m * a                       rotating masses included
    F_roll    = f_r(v) * m * g * cos(alpha)          tyre deformation
    F_aero    = 0.5 * rho * C_d * A * (v + v_wind)^2 aerodynamic drag
    F_grade   = m * g * sin(alpha)                   road gradient

References: Ehsani et al., *Modern Electric, Hybrid Electric and Fuel Cell
Vehicles*, ch. 2; Mitschke & Wallentowitz, *Dynamik der Kraftfahrzeuge*, ch. 2.
"""

from __future__ import annotations

import dataclasses

import numpy as np

from .parameters import ParameterSet

ArrayLike = float | np.ndarray


@dataclasses.dataclass(frozen=True)
class RoadLoad:
    """Resistance forces acting on the vehicle."""

    mass: float               # kg, total mass incl. payload
    rotational_factor: float  # -, lambda
    gravity: float            # m/s^2
    f_r0: float               # -, rolling resistance at low speed
    f_r_k: float              # s^2/m^2, speed-dependent rolling term
    air_density: float        # kg/m^3
    drag_coefficient: float   # -
    frontal_area: float       # m^2
    headwind: float           # m/s, positive = against the vehicle
    grade: float              # rad

    # ------------------------------------------------------------ construction
    @classmethod
    def from_parameters(cls, ps: ParameterSet) -> "RoadLoad":
        return cls(
            mass=ps["mass.curb_mass"] + ps["mass.test_payload"],
            rotational_factor=ps["mass.rotational_mass_factor"],
            gravity=ps["environment.gravity"],
            f_r0=ps["tyres.rolling_resistance_coefficient"],
            f_r_k=ps["tyres.rolling_resistance_speed_coefficient"],
            air_density=ps["aerodynamics.air_density"],
            drag_coefficient=ps["aerodynamics.drag_coefficient"],
            frontal_area=ps["aerodynamics.frontal_area"],
            headwind=ps["environment.headwind"],
            grade=ps["environment.road_grade"],
        )

    # -------------------------------------------------------- component forces
    def rolling_coefficient(self, v: ArrayLike) -> ArrayLike:
        """Speed-dependent rolling resistance coefficient f_r(v)."""
        return self.f_r0 + self.f_r_k * np.square(v)

    def rolling_resistance(self, v: ArrayLike) -> ArrayLike:
        """Rolling resistance force [N]. Vanishes at standstill."""
        force = (
            self.rolling_coefficient(v)
            * self.mass
            * self.gravity
            * np.cos(self.grade)
        )
        return np.where(np.asarray(v) > 1e-3, force, 0.0)

    def aerodynamic_drag(self, v: ArrayLike) -> ArrayLike:
        """Aerodynamic drag force [N]."""
        v_rel = np.asarray(v) + self.headwind
        return (
            0.5
            * self.air_density
            * self.drag_coefficient
            * self.frontal_area
            * v_rel
            * np.abs(v_rel)
        )

    def grade_resistance(self, v: ArrayLike = 0.0) -> ArrayLike:
        """Gradient force [N]. Independent of speed, broadcast to v's shape."""
        force = self.mass * self.gravity * np.sin(self.grade)
        return np.broadcast_to(np.asarray(force, dtype=float), np.shape(np.asarray(v)))

    def inertia_force(self, a: ArrayLike) -> ArrayLike:
        """Force needed to accelerate translating + rotating masses [N]."""
        return self.rotational_factor * self.mass * np.asarray(a)

    # ------------------------------------------------------------------ totals
    def resistance(self, v: ArrayLike) -> ArrayLike:
        """Total speed-dependent resistance (no inertia) [N]."""
        return (
            self.rolling_resistance(v)
            + self.aerodynamic_drag(v)
            + self.grade_resistance(v)
        )

    def tractive_force(self, v: ArrayLike, a: ArrayLike) -> ArrayLike:
        """Total force required at the wheels [N] (negative = braking)."""
        return self.resistance(v) + self.inertia_force(a)

    def effective_mass(self) -> float:
        """Translational + rotational equivalent mass [kg]."""
        return self.rotational_factor * self.mass

    def coastdown_deceleration(self, v: ArrayLike) -> ArrayLike:
        """Deceleration in free coasting (no drive, no brakes) [m/s^2]."""
        return -np.asarray(self.resistance(v)) / self.effective_mass()
