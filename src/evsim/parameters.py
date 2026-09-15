"""Parameter loading and the assumption register.

Requirement FR-1 (DOCS/PRD.md): every vehicle parameter is loaded from one
versioned YAML file and carries its provenance.  Values that are engineering
estimates rather than published data are flagged ``assumed: true`` and are
collected here into an *assumption register* which the report renders in red.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Iterator

import yaml


@dataclasses.dataclass(frozen=True)
class Parameter:
    """A single physical parameter together with its provenance."""

    path: str          # dotted location in the YAML file, e.g. "mass.curb_mass"
    value: float
    unit: str
    assumed: bool
    source: str

    @property
    def label(self) -> str:
        """Human-readable name derived from the dotted path."""
        return self.path.split(".")[-1].replace("_", " ")

    def __float__(self) -> float:
        return float(self.value)


class ParameterError(KeyError):
    """Raised when a required parameter is missing from the parameter file."""


class ParameterSet:
    """Dictionary-like access to a validated vehicle parameter file.

    Example
    -------
    >>> ps = ParameterSet.from_yaml("data/vehicles/tesla_model_3_rwd_2024.yaml")
    >>> ps["mass.curb_mass"]                      # doctest: +SKIP
    1765.0
    >>> ps.parameter("mass.curb_mass").assumed    # doctest: +SKIP
    False
    """

    def __init__(self, raw: dict[str, Any], origin: str | None = None) -> None:
        self.raw = raw
        self.origin = origin
        self._params: dict[str, Parameter] = {}
        self._collect(raw, prefix="")

    # ------------------------------------------------------------- construction
    @classmethod
    def from_yaml(cls, path: str | Path) -> "ParameterSet":
        path = Path(path)
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        if not isinstance(raw, dict):
            raise ValueError(f"{path} does not contain a YAML mapping")
        return cls(raw, origin=str(path))

    def _collect(self, node: Any, prefix: str) -> None:
        """Walk the YAML tree and register every {value, unit, assumed, source} leaf."""
        if not isinstance(node, dict):
            return
        if "value" in node and "unit" in node:
            self._params[prefix] = Parameter(
                path=prefix,
                value=float(node["value"]),
                unit=str(node["unit"]),
                assumed=bool(node.get("assumed", False)),
                source=str(node.get("source", "unspecified")),
            )
            return
        for key, child in node.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            self._collect(child, child_prefix)

    # -------------------------------------------------------------- access
    def __contains__(self, path: str) -> bool:
        return path in self._params

    def __getitem__(self, path: str) -> float:
        return self.parameter(path).value

    def __iter__(self) -> Iterator[Parameter]:
        return iter(self._params.values())

    def parameter(self, path: str) -> Parameter:
        try:
            return self._params[path]
        except KeyError as exc:
            raise ParameterError(
                f"parameter '{path}' not found in {self.origin or 'parameter set'}"
            ) from exc

    def get(self, path: str, default: float | None = None) -> float | None:
        param = self._params.get(path)
        return default if param is None else param.value

    def meta(self, key: str, default: Any = None) -> Any:
        return self.raw.get("meta", {}).get(key, default)

    def node(self, path: str) -> Any:
        """Return a raw (non-parameter) YAML node, e.g. a list of curve points."""
        node: Any = self.raw
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                raise ParameterError(f"node '{path}' not found in {self.origin}")
            node = node[part]
        return node

    # ------------------------------------------------------ assumption register
    def assumptions(self) -> list[Parameter]:
        """All parameters flagged ``assumed: true``, ordered by their path."""
        return sorted(
            (p for p in self._params.values() if p.assumed), key=lambda p: p.path
        )

    def published(self) -> list[Parameter]:
        """All parameters taken from an official or measured source."""
        return sorted(
            (p for p in self._params.values() if not p.assumed), key=lambda p: p.path
        )

    def override(self, **changes: float) -> "ParameterSet":
        """Return a copy with selected parameters replaced.

        Keys use ``__`` in place of ``.`` so they are valid Python identifiers,
        e.g. ``override(mass__curb_mass=1800.0)``.  Used by the sensitivity study.
        """
        import copy

        raw = copy.deepcopy(self.raw)
        for key, new_value in changes.items():
            path = key.replace("__", ".")
            node: Any = raw
            parts = path.split(".")
            for part in parts:
                if not isinstance(node, dict) or part not in node:
                    raise ParameterError(f"cannot override unknown parameter '{path}'")
                node = node[part]
            if not isinstance(node, dict) or "value" not in node:
                raise ParameterError(f"'{path}' is not an overridable parameter")
            node["value"] = float(new_value)
        return ParameterSet(raw, origin=f"{self.origin} (overridden)")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"ParameterSet({self.meta('name', 'unnamed')!r}, "
            f"{len(self._params)} parameters, {len(self.assumptions())} assumed)"
        )
