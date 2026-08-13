"""Provenance-tagged parameters (ARCHIVE/GOAL-v1-scaffold.md §4.1–4.3)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, model_validator
from scipy import optimize, stats

Family = Literal[
    "lognormal",
    "beta",
    "gamma",
    "normal",
    "triangular",
    "point",
    "empirical",
]

_Z95 = float(stats.norm.ppf(0.95))
_REL_RESIDUAL_LIMIT = 0.25
_QUANTILE_FAMILIES = frozenset(
    {"lognormal", "beta", "gamma", "normal", "triangular"}
)


class Provenance(str, Enum):
    TRIAL = "trial"
    REGISTRY = "registry"
    OBSERVATIONAL = "observational"
    MECHANISTIC = "mechanistic"
    ELICITED = "elicited"
    ASSUMED = "assumed"


def _sorted_pq(quantiles: dict[float, float]) -> tuple[np.ndarray, np.ndarray]:
    items = sorted(quantiles.items())
    probs = np.array([p for p, _ in items], dtype=float)
    values = np.array([v for _, v in items], dtype=float)
    return probs, values


def _check_quantile_order(quantiles: dict[float, float]) -> None:
    probs, values = _sorted_pq(quantiles)
    if np.any(np.diff(values) < 0):
        raise ValueError(
            "inconsistent quantiles: values must be non-decreasing in probability"
        )
    q05, q50, q95 = quantiles.get(0.05), quantiles.get(0.5), quantiles.get(0.95)
    if q05 is not None and q50 is not None and q05 > q50:
        raise ValueError("inconsistent quantiles: 5th > 50th")
    if q50 is not None and q95 is not None and q50 > q95:
        raise ValueError("inconsistent quantiles: 50th > 95th")


def _check_family_support(family: str, values: np.ndarray) -> None:
    if family in {"lognormal", "gamma"} and np.any(values <= 0):
        raise ValueError(f"{family} quantiles must be strictly positive")
    if family == "beta" and np.any((values <= 0) | (values >= 1)):
        raise ValueError("beta quantiles must lie in (0, 1)")


def _apply_overconfidence(
    quantiles: dict[float, float], factor: float
) -> dict[float, float]:
    if factor <= 0:
        raise ValueError("overconfidence_correction must be positive")
    if factor == 1.0:
        return dict(quantiles)
    probs, values = _sorted_pq(quantiles)
    median = (
        float(quantiles[0.5])
        if 0.5 in quantiles
        else float(np.interp(0.5, probs, values))
    )
    return {p: median + factor * (q - median) for p, q in quantiles.items()}


def _pinball_loss(pred: np.ndarray, obs: np.ndarray, probs: np.ndarray) -> float:
    delta = obs - pred
    return float(np.sum(np.where(delta >= 0.0, probs * delta, (probs - 1.0) * delta)))


def _ppf(family: str, params: dict[str, float], probs: np.ndarray) -> np.ndarray:
    p = np.asarray(probs, dtype=float)
    if family == "lognormal":
        return stats.lognorm.ppf(p, s=params["sigma"], scale=np.exp(params["mu"]))
    if family == "normal":
        return stats.norm.ppf(p, loc=params["mean"], scale=params["sd"])
    if family == "gamma":
        return stats.gamma.ppf(p, a=params["shape"], scale=params["scale"])
    if family == "beta":
        return stats.beta.ppf(p, a=params["a"], b=params["b"])
    if family == "triangular":
        left = params["left"]
        mode = params["mode"]
        right = params["right"]
        if not (left <= mode <= right) or right <= left:
            return np.full_like(p, np.nan, dtype=float)
        scale = right - left
        c = (mode - left) / scale
        return stats.triang.ppf(p, c=c, loc=left, scale=scale)
    raise ValueError(f"cannot evaluate ppf for family={family!r}")


def _initial_state(
    family: str, quantiles: dict[float, float]
) -> tuple[list[str], np.ndarray, list[tuple[float | None, float | None]]]:
    probs, values = _sorted_pq(quantiles)
    q05 = float(quantiles[0.05]) if 0.05 in quantiles else float(np.interp(0.05, probs, values))
    q50 = float(quantiles[0.5]) if 0.5 in quantiles else float(np.interp(0.5, probs, values))
    q95 = float(quantiles[0.95]) if 0.95 in quantiles else float(np.interp(0.95, probs, values))
    span = max(q95 - q05, np.ptp(values), 1e-12)

    if family == "lognormal":
        mu = float(np.log(q50))
        sigma = max((np.log(q95) - np.log(q05)) / (2.0 * _Z95), 1e-8)
        return ["mu", "sigma"], np.array([mu, sigma]), [(None, None), (1e-12, None)]
    if family == "normal":
        sd = max((q95 - q05) / (2.0 * _Z95), 1e-8)
        return ["mean", "sd"], np.array([q50, sd]), [(None, None), (1e-12, None)]
    if family == "gamma":
        sd = max((q95 - q05) / (2.0 * _Z95), 1e-8)
        shape = max((q50 / sd) ** 2, 1e-6)
        scale = max(sd**2 / max(q50, 1e-12), 1e-12)
        return (
            ["shape", "scale"],
            np.array([shape, scale]),
            [(1e-12, None), (1e-12, None)],
        )
    if family == "beta":
        sd = max((q95 - q05) / (2.0 * _Z95), 1e-4)
        mean = min(max(q50, 1e-6), 1.0 - 1e-6)
        var = min(sd**2, mean * (1.0 - mean) * 0.25)
        conc = max(mean * (1.0 - mean) / max(var, 1e-12) - 1.0, 2.0)
        return (
            ["a", "b"],
            np.array([max(mean * conc, 1e-6), max((1.0 - mean) * conc, 1e-6)]),
            [(1e-12, None), (1e-12, None)],
        )
    if family == "triangular":
        left = q05 - 0.05 * span / 0.9
        right = q95 + 0.05 * span / 0.9
        if right <= left:
            right = left + 1e-8
        mode = min(max(q50, left), right)
        return (
            ["left", "mode", "right"],
            np.array([left, mode, right]),
            [(None, None), (None, None), (None, None)],
        )
    raise ValueError(f"no initializer for family={family!r}")


def _fit_by_quantile_loss(
    family: str, quantiles: dict[float, float]
) -> tuple[dict[str, float], float]:
    _check_family_support(family, np.array(list(quantiles.values()), dtype=float))
    min_points = 3 if family == "triangular" else 2
    if len(quantiles) < min_points:
        raise ValueError(
            f"{family} fit requires at least {min_points} quantiles; got {len(quantiles)}"
        )

    probs, values = _sorted_pq(quantiles)
    names, x0, bounds = _initial_state(family, quantiles)

    def objective(x: np.ndarray) -> float:
        params = {name: float(val) for name, val in zip(names, x, strict=True)}
        pred = _ppf(family, params, probs)
        if not np.all(np.isfinite(pred)):
            return 1e12
        return _pinball_loss(pred, values, probs)

    result = optimize.minimize(objective, x0, method="L-BFGS-B", bounds=bounds)
    if not result.success:
        result = optimize.minimize(objective, x0, method="Nelder-Mead")

    fitted = {name: float(val) for name, val in zip(names, result.x, strict=True)}
    pred = _ppf(family, fitted, probs)
    if not np.all(np.isfinite(pred)):
        raise ValueError(
            f"quantiles inconsistent with family={family!r}: fit produced non-finite quantiles"
        )

    residual = _pinball_loss(pred, values, probs)
    rmse = float(np.sqrt(np.mean((pred - values) ** 2)))
    span = max(float(np.ptp(values)), float(np.max(np.abs(values))), 1e-12)
    if rmse / span > _REL_RESIDUAL_LIMIT:
        raise ValueError(
            f"quantiles inconsistent with family={family!r}: residual={residual:.6g}"
        )
    return fitted, residual


class DistributionSpec(BaseModel):
    family: Family
    quantiles: dict[float, float] | None = None
    fitted_params: dict[str, float] | None = None
    overconfidence_correction: float = 1.0
    residual: float | None = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_and_fit(self) -> DistributionSpec:
        if self.family == "point":
            if self.fitted_params is None or "value" not in self.fitted_params:
                raise ValueError(
                    'point family requires fitted_params={"value": ...}'
                )
            self.residual = 0.0
            return self

        if self.family == "empirical":
            if self.quantiles:
                coerced = {float(p): float(q) for p, q in self.quantiles.items()}
                _check_quantile_order(coerced)
                self.quantiles = coerced
            self.residual = 0.0 if self.residual is None else self.residual
            return self

        if not self.quantiles:
            raise ValueError(
                f"quantiles are required for family={self.family!r}; "
                "moments-only construction is rejected"
            )

        coerced = {float(p): float(q) for p, q in self.quantiles.items()}
        _check_quantile_order(coerced)
        self.quantiles = coerced
        widened = _apply_overconfidence(coerced, self.overconfidence_correction)
        fitted, residual = _fit_by_quantile_loss(self.family, widened)
        self.fitted_params = fitted
        self.residual = residual
        return self


class Parameter(BaseModel):
    name: str
    provenance: Provenance
    distribution: DistributionSpec
    source: str
    elicitation_id: str | None = None
    notes: str = ""

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _require_elicitation_record(self) -> Parameter:
        if self.provenance is not Provenance.ELICITED:
            return self
        if not self.elicitation_id:
            raise ValueError(
                "elicitation_id is required when provenance is ELICITED"
            )
        record = Path("configs/elicitation") / f"{self.elicitation_id}.yaml"
        if not record.is_file():
            raise ValueError(f"elicitation record not found: {record}")
        return self
