"""Longitudinal road-load model (FR-2).

The tractive force the vehicle must deliver at the wheels is

    F_trac = F_inertia + F_running + F_grade

with ``F_inertia = lambda * m * a`` (rotating masses included) and
``F_grade = m * g * sin(alpha)``.  Two formulations of the running resistance
are supported, selected by ``road_load.model`` in the parameter file.

``physical`` — the textbook decomposition
-----------------------------------------
    F_roll = f_r(v) * m * g * cos(alpha),   f_r(v) = f_r0 + k * v^2
    F_aero = 0.5 * rho * C_d * A * (v + v_wind)^2

This is the form the report derives, and it is what the traction diagram shows,
because it separates the two physical mechanisms.

``coastdown`` — the regulatory form (default)
---------------------------------------------
    F_run = F0 + F1 * v + F2 * v^2

This is what WLTP and EPA type approval actually measure, by letting the vehicle
coast down on a test track and fitting a quadratic.  It is the default for
energy and range work because it is physically complete in a way the textbook
decomposition is not:

* the linear term ``F1`` captures bearing, seal and driveline drag, for which
  the textbook decomposition has no counterpart at all;
* the quadratic term captures real on-road aerodynamic drag, including wheel
  rotation and cooling flow, which a wind-tunnel drag coefficient excludes.

For this vehicle the two differ by 15-19 % above 80 km/h, and using the
textbook form alone under-predicts the energy demand by about that much.  The
comparison is a result in its own right and is plotted in the report.

References: Ehsani et al., *Modern Electric, Hybrid Electric and Fuel Cell
Vehicles*, ch. 2; Mitschke & Wallentowitz, *Dynamik der Kraftfahrzeuge*, ch. 2;
UNECE GTR 15 Annex 4 (road-load determination).
"""

from __future__ import annotations

import dataclasses

import numpy as np

from .parameters import ParameterSet

ArrayLike = float | np.ndarray

PHYSICAL = "physical"
COASTDOWN = "coastdown"


@dataclasses.dataclass(frozen=True)
class RoadLoad:
    """Resistance forces acting on the vehicle."""

    mass: float               # kg, total mass incl. payload
    rotational_factor: float  # -, lambda
    gravity: float            # m/s^2
    # physical decomposition
    f_r0: float               # -, rolling resistance at low speed
    f_r_k: float              # s^2/m^2, speed-dependent rolling term
    air_density: float        # kg/m^3
    drag_coefficient: float   # -
    frontal_area: float       # m^2
    headwind: float           # m/s, positive = against the vehicle
    # regulatory coastdown polynomial
    f0: float                 # N, at the coastdown test mass
    f1: float                 # N/(m/s)
    f2: float                 # N/(m/s)^2
    coastdown_test_mass: float  # kg, mass the coastdown was measured at
    # selection and road
    model: str                # PHYSICAL or COASTDOWN
    grade: float              # rad

    # ------------------------------------------------------------ construction
    @classmethod
    def from_parameters(cls, ps: ParameterSet, model: str | None = None) -> "RoadLoad":
        if model is None:
            model = str(ps.raw.get("road_load", {}).get("model", COASTDOWN))
        if model not in (PHYSICAL, COASTDOWN):
            raise ValueError(
                f"unknown road-load model {model!r}; expected "
                f"{PHYSICAL!r} or {COASTDOWN!r}"
            )
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
            f0=ps["road_load.coastdown_f0"],
            f1=ps["road_load.coastdown_f1"],
            f2=ps["road_load.coastdown_f2"],
            coastdown_test_mass=ps["road_load.coastdown_test_mass"],
            model=model,
            grade=ps["environment.road_grade"],
        )

    def with_model(self, model: str) -> "RoadLoad":
        """Return a copy using the other road-load formulation."""
        return dataclasses.replace(self, model=model)

    # ------------------------------------- physical decomposition components
    def rolling_coefficient(self, v: ArrayLike) -> np.ndarray:
        """Speed-dependent rolling resistance coefficient f_r(v)."""
        return self.f_r0 + self.f_r_k * np.square(np.asarray(v, dtype=float))

    def rolling_resistance(self, v: ArrayLike) -> np.ndarray:
        """Tyre rolling resistance [N]. Vanishes at standstill."""
        v = np.asarray(v, dtype=float)
        force = (
            self.rolling_coefficient(v) * self.mass * self.gravity * np.cos(self.grade)
        )
        return np.where(np.abs(v) > 1e-3, np.sign(v) * force, 0.0)

    def aerodynamic_drag(self, v: ArrayLike) -> np.ndarray:
        """Aerodynamic drag from the wind-tunnel drag coefficient [N]."""
        v_rel = np.asarray(v, dtype=float) + self.headwind
        return (
            0.5
            * self.air_density
            * self.drag_coefficient
            * self.frontal_area
            * v_rel
            * np.abs(v_rel)
        )

    # -------------------------------------- coastdown polynomial components
    @property
    def mass_ratio(self) -> float:
        """Actual mass divided by the mass the coastdown was measured at."""
        return self.mass / self.coastdown_test_mass

    def coastdown_mechanical(self, v: ArrayLike) -> np.ndarray:
        """Speed-independent and linear terms of the coastdown fit [N].

        The constant term is tyre rolling resistance, which is proportional to
        the normal load, so it is scaled by the ratio of the actual mass to the
        mass the coastdown was measured at.  The linear term is bearing, seal
        and driveline drag, which does not scale with payload, so it is left
        alone.  Without this correction the model would report that payload is
        almost free, since the inertia it adds is largely recovered by
        regenerative braking.
        """
        v = np.asarray(v, dtype=float)
        rolling = self.f0 * self.mass_ratio
        # Resistance opposes motion, so it takes the sign of travel; the gate at
        # standstill avoids a static force on a stationary vehicle.
        magnitude = rolling + self.f1 * np.abs(v)
        return np.where(np.abs(v) > 1e-3, np.sign(v) * magnitude, 0.0)

    def coastdown_aerodynamic(self, v: ArrayLike) -> np.ndarray:
        """Quadratic term of the coastdown fit [N].

        A headwind is added to the vehicle speed here, as it would be for pure
        aerodynamic drag.  That is an approximation: ``F2`` is a fitted
        coefficient that also absorbs the speed-squared part of tyre and
        driveline loss, on which a headwind has no effect, so a large headwind
        overstates the resistance somewhat.  Use the physical model when the
        headwind matters.  Legislative cycles specify still air.
        """
        v_rel = np.asarray(v, dtype=float) + self.headwind
        return self.f2 * v_rel * np.abs(v_rel)

    # ------------------------------------------------------------------ grade
    def grade_resistance(self, v: ArrayLike = 0.0) -> np.ndarray:
        """Gradient force [N]. Independent of speed, broadcast to v's shape."""
        force = self.mass * self.gravity * np.sin(self.grade)
        return np.full(np.shape(np.asarray(v, dtype=float)), force, dtype=float)

    def inertia_force(self, a: ArrayLike) -> np.ndarray:
        """Force needed to accelerate translating + rotating masses [N]."""
        return self.rotational_factor * self.mass * np.asarray(a, dtype=float)

    # ------------------------------------------------------------------ totals
    def components(self, v: ArrayLike) -> dict[str, np.ndarray]:
        """Resistance split into named parts, using the active formulation."""
        if self.model == COASTDOWN:
            return {
                "mechanical": self.coastdown_mechanical(v),
                "aerodynamic": self.coastdown_aerodynamic(v),
                "grade": self.grade_resistance(v),
            }
        return {
            "mechanical": self.rolling_resistance(v),
            "aerodynamic": self.aerodynamic_drag(v),
            "grade": self.grade_resistance(v),
        }

    def running_resistance(self, v: ArrayLike) -> np.ndarray:
        """Resistance excluding the gradient [N], using the active formulation."""
        parts = self.components(v)
        return parts["mechanical"] + parts["aerodynamic"]

    def resistance(self, v: ArrayLike) -> np.ndarray:
        """Total speed-dependent resistance, gradient included [N]."""
        return self.running_resistance(v) + self.grade_resistance(v)

    def tractive_force(self, v: ArrayLike, a: ArrayLike) -> np.ndarray:
        """Total force required at the wheels [N] (negative = braking)."""
        return self.resistance(v) + self.inertia_force(a)

    def effective_mass(self) -> float:
        """Translational + rotational equivalent mass [kg]."""
        return self.rotational_factor * self.mass

    def coastdown_deceleration(self, v: ArrayLike) -> np.ndarray:
        """Deceleration in free coasting (no drive, no brakes) [m/s^2]."""
        return -self.resistance(v) / self.effective_mass()

    # -------------------------------------------------------- model comparison
    def effective_drag_area(self) -> float:
        """C_d * A implied by the coastdown quadratic term [m^2]."""
        return self.f2 / (0.5 * self.air_density)

    def drag_discrepancy(self) -> float:
        """Ratio of the coastdown-implied drag area to the wind-tunnel value."""
        return self.effective_drag_area() / (self.drag_coefficient * self.frontal_area)
