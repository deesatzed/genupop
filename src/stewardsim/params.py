"""Provenance-tagged parameters (ARCHIVE/GOAL-v1-scaffold.md §4.1–4.3)."""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
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
# Max |ppf(p) - q_p| / |q_p|. Aligned with the relative-SSE objective (GOAL §4.3).
_MAX_REL_QUANTILE_ERROR = 0.25
_ELICITATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_FIT_FAMILIES = frozenset({"lognormal", "beta", "gamma", "normal", "triangular"})


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


def _coerce_quantiles(raw: dict[Any, Any]) -> dict[float, float]:
    coerced = {float(p): float(q) for p, q in raw.items()}
    bad = [p for p in coerced if not (0.0 < p < 1.0)]
    if bad:
        raise ValueError(
            f"quantile probability keys must lie in (0, 1); got {bad}"
        )
    _check_quantile_order(coerced)
    return coerced


def _check_quantile_order(quantiles: dict[float, float]) -> None:
    _probs, values = _sorted_pq(quantiles)
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


def _logit(x: float) -> float:
    x = min(max(float(x), 1e-12), 1.0 - 1e-12)
    return float(np.log(x / (1.0 - x)))


def _expit(z: float) -> float:
    z = float(z)
    if z >= 0.0:
        ez = float(np.exp(-z))
        return 1.0 / (1.0 + ez)
    ez = float(np.exp(z))
    return ez / (1.0 + ez)


def _median_of(quantiles: dict[float, float]) -> float:
    if 0.5 in quantiles:
        return float(quantiles[0.5])
    probs, values = _sorted_pq(quantiles)
    return float(np.interp(0.5, probs, values))


def _apply_overconfidence(
    quantiles: dict[float, float], factor: float, family: str
) -> dict[float, float]:
    if not np.isfinite(factor) or factor <= 0.0:
        raise ValueError("overconfidence_correction must be positive")
    if factor == 1.0:
        return dict(quantiles)
    median = _median_of(quantiles)
    if family in {"lognormal", "gamma"}:
        if median <= 0.0 or any(q <= 0.0 for q in quantiles.values()):
            raise ValueError(f"{family} quantiles must be strictly positive")
        log_m = float(np.log(median))
        return {
            p: float(np.exp(log_m + factor * (np.log(q) - log_m)))
            for p, q in quantiles.items()
        }
    if family == "beta":
        logit_m = _logit(median)
        return {
            p: _expit(logit_m + factor * (_logit(q) - logit_m))
            for p, q in quantiles.items()
        }
    return {p: median + factor * (q - median) for p, q in quantiles.items()}


def _pinball_loss(pred: np.ndarray, obs: np.ndarray, probs: np.ndarray) -> float:
    delta = obs - pred
    return float(np.sum(np.where(delta >= 0.0, probs * delta, (probs - 1.0) * delta)))


def _relative_sse(pred: np.ndarray, values: np.ndarray) -> float:
    rel = (pred - values) / np.maximum(np.abs(values), 1e-12)
    if not np.all(np.isfinite(rel)):
        return 1e12
    return float(np.dot(rel, rel))


def _max_rel_error(pred: np.ndarray, values: np.ndarray) -> float:
    rel = np.abs(pred - values) / np.maximum(np.abs(values), 1e-12)
    if not np.all(np.isfinite(rel)):
        return float("inf")
    return float(np.max(rel))


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


def _params_valid(family: str, params: dict[str, float]) -> bool:
    if not all(np.isfinite(v) for v in params.values()):
        return False
    if family == "lognormal":
        return params["sigma"] > 0.0
    if family == "normal":
        return params["sd"] > 0.0
    if family == "gamma":
        return params["shape"] > 0.0 and params["scale"] > 0.0
    if family == "beta":
        return params["a"] > 0.0 and params["b"] > 0.0
    if family == "triangular":
        return params["left"] <= params["mode"] <= params["right"] and (
            params["right"] > params["left"]
        )
    return False


def _pack(family: str, params: dict[str, float]) -> np.ndarray:
    if family == "lognormal":
        return np.array([params["mu"], np.log(params["sigma"])], dtype=float)
    if family == "normal":
        return np.array([params["mean"], np.log(params["sd"])], dtype=float)
    if family == "gamma":
        return np.array(
            [np.log(params["shape"]), np.log(params["scale"])], dtype=float
        )
    if family == "beta":
        return np.array([np.log(params["a"]), np.log(params["b"])], dtype=float)
    if family == "triangular":
        width = params["right"] - params["left"]
        c = (params["mode"] - params["left"]) / width
        return np.array(
            [params["left"], np.log(width), _logit(c)], dtype=float
        )
    raise ValueError(f"no pack for family={family!r}")


def _unpack(family: str, x: np.ndarray) -> dict[str, float]:
    x = np.asarray(x, dtype=float)
    if family == "lognormal":
        return {"mu": float(x[0]), "sigma": float(np.exp(x[1]))}
    if family == "normal":
        return {"mean": float(x[0]), "sd": float(np.exp(x[1]))}
    if family == "gamma":
        return {"shape": float(np.exp(x[0])), "scale": float(np.exp(x[1]))}
    if family == "beta":
        return {"a": float(np.exp(x[0])), "b": float(np.exp(x[1]))}
    if family == "triangular":
        left = float(x[0])
        width = float(np.exp(x[1]))
        c = _expit(float(x[2]))
        return {
            "left": left,
            "mode": left + c * width,
            "right": left + width,
        }
    raise ValueError(f"no unpack for family={family!r}")


def _initial_params(family: str, quantiles: dict[float, float]) -> dict[str, float]:
    probs, values = _sorted_pq(quantiles)
    q05 = float(quantiles[0.05]) if 0.05 in quantiles else float(np.interp(0.05, probs, values))
    q50 = float(quantiles[0.5]) if 0.5 in quantiles else float(np.interp(0.5, probs, values))
    q95 = float(quantiles[0.95]) if 0.95 in quantiles else float(np.interp(0.95, probs, values))
    span = max(q95 - q05, float(np.ptp(values)), 1e-12)

    if family == "lognormal":
        return {
            "mu": float(np.log(q50)),
            "sigma": max((np.log(q95) - np.log(q05)) / (2.0 * _Z95), 1e-8),
        }
    if family == "normal":
        return {
            "mean": q50,
            "sd": max((q95 - q05) / (2.0 * _Z95), 1e-8),
        }
    if family == "gamma":
        sd = max((q95 - q05) / (2.0 * _Z95), 1e-8)
        shape = max((q50 / sd) ** 2, 1e-6)
        scale = max(sd**2 / max(q50, 1e-12), 1e-12)
        return {"shape": float(shape), "scale": float(scale)}
    if family == "beta":
        sd = max((q95 - q05) / (2.0 * _Z95), 1e-4)
        mean = min(max(q50, 1e-6), 1.0 - 1e-6)
        var = min(sd**2, mean * (1.0 - mean) * 0.25)
        conc = max(mean * (1.0 - mean) / max(var, 1e-12) - 1.0, 2.0)
        return {
            "a": float(max(mean * conc, 1e-6)),
            "b": float(max((1.0 - mean) * conc, 1e-6)),
        }
    if family == "triangular":
        left = q05 - 0.05 * span / 0.9
        right = q95 + 0.05 * span / 0.9
        if right <= left:
            right = left + 1e-8
        mode = min(max(q50, left), right)
        return {"left": float(left), "mode": float(mode), "right": float(right)}
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
    x0 = _pack(family, _initial_params(family, quantiles))

    def objective(x: np.ndarray) -> float:
        params = _unpack(family, x)
        if not _params_valid(family, params):
            return 1e12
        pred = _ppf(family, params, probs)
        if not np.all(np.isfinite(pred)):
            return 1e12
        return _relative_sse(pred, values)

    method_options = {
        "L-BFGS-B": {"maxiter": 8000, "ftol": 1e-15, "gtol": 1e-15},
        "Nelder-Mead": {"maxiter": 8000, "xatol": 1e-14, "fatol": 1e-16},
    }
    candidates: list[tuple[float, np.ndarray]] = []
    for method, options in method_options.items():
        result = optimize.minimize(objective, x0, method=method, options=options)
        x = np.asarray(result.x, dtype=float)
        if not np.all(np.isfinite(x)):
            continue
        obj = float(objective(x))
        if not np.isfinite(obj):
            continue
        candidates.append((obj, x))

    if not candidates:
        raise ValueError(
            f"quantiles inconsistent with family={family!r}: fit failed"
        )

    _best_obj, best_x = min(candidates, key=lambda item: item[0])
    polished = optimize.minimize(
        objective,
        best_x,
        method="Nelder-Mead",
        options=method_options["Nelder-Mead"],
    )
    if np.all(np.isfinite(polished.x)):
        polished_obj = float(objective(polished.x))
        if np.isfinite(polished_obj) and polished_obj < _best_obj:
            best_x = np.asarray(polished.x, dtype=float)
    fitted = _unpack(family, best_x)
    pred = _ppf(family, fitted, probs)
    if not np.all(np.isfinite(pred)):
        raise ValueError(
            f"quantiles inconsistent with family={family!r}: "
            "fit produced non-finite quantiles"
        )

    residual = _pinball_loss(pred, values, probs)
    maxrel = _max_rel_error(pred, values)
    if maxrel > _MAX_REL_QUANTILE_ERROR:
        raise ValueError(
            f"quantiles inconsistent with family={family!r}: "
            f"max relative quantile error={maxrel:.6g} "
            f"(limit {_MAX_REL_QUANTILE_ERROR})"
        )
    return fitted, residual


def _prepare_distribution(data: dict[str, Any]) -> dict[str, Any]:
    family = data.get("family")
    if family == "point":
        fitted = data.get("fitted_params")
        if not isinstance(fitted, dict) or "value" not in fitted:
            raise ValueError('point family requires fitted_params={"value": ...}')
        data["residual"] = 0.0
        return data
    if family == "empirical":
        raw = data.get("quantiles")
        if raw:
            data["quantiles"] = _coerce_quantiles(raw)
        if data.get("residual") is None:
            data["residual"] = 0.0
        return data
    if family not in _FIT_FAMILIES:
        return data

    raw = data.get("quantiles")
    if not raw:
        raise ValueError(
            f"quantiles are required for family={family!r}; "
            "moments-only construction is rejected"
        )
    coerced = _coerce_quantiles(raw)
    data["quantiles"] = coerced
    factor = float(data.get("overconfidence_correction", 1.0))
    widened = _apply_overconfidence(coerced, factor, family)
    fitted, residual = _fit_by_quantile_loss(family, widened)
    data["fitted_params"] = fitted
    data["residual"] = residual
    return data


class DistributionSpec(BaseModel):
    family: Family
    quantiles: dict[float, float] | None = None
    fitted_params: dict[str, float] | None = None
    overconfidence_correction: float = 1.0
    residual: float | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _validate_and_fit(cls, data: Any) -> Any:
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            return data
        return _prepare_distribution(dict(data))


class Parameter(BaseModel):
    name: str
    provenance: Provenance
    distribution: DistributionSpec
    source: str
    elicitation_id: str | None = None
    notes: str = ""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("elicitation_id")
    @classmethod
    def _check_elicitation_id_format(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if _ELICITATION_ID_RE.fullmatch(value) is None:
            raise ValueError(
                "elicitation_id must match ^[A-Za-z0-9][A-Za-z0-9_.-]*$"
            )
        return value

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
