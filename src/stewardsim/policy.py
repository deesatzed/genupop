"""Policy representation and state-dependent adherence (GOAL §4.4–4.5, AT-14).

A policy is a function from host state to an ordered drug preference.
Adherence draws a Bernoulli against effective_fidelity; when deviation
occurs the substitute comes from DeviationTarget, never a global drug list.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from stewardsim.feasibility import ConstraintSet, evaluate
from stewardsim.host import Host
from stewardsim.params import Parameter


def point_value(param: Parameter) -> float:
    """Return the scalar from a point Parameter. Slice-0 does not sample."""
    if param.distribution.family != "point":
        raise ValueError(f"{param.name} must use family='point'")
    fitted = param.distribution.fitted_params
    if fitted is None or "value" not in fitted:
        raise ValueError(f"{param.name} point Parameter missing fitted_params['value']")
    return float(fitted["value"])


class PolicyRule(BaseModel):
    """Host state → ordered drug preference.

    Slice-0: a default ordered list, optionally keyed by a comorbidity flag
    in ``when``. A rule with ``when is None`` matches any host.
    """

    preferred: list[str]
    when: str | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class Policy(BaseModel):
    id: str
    rules: list[PolicyRule] = Field(min_length=1)
    reserve: list[str] = []
    duration: Parameter

    model_config = ConfigDict(extra="forbid", frozen=True)


class DeviationTarget(BaseModel):
    """Ordered substitutes when deviation occurs — not uniform over all drugs."""

    drugs: list[str]

    model_config = ConfigDict(extra="forbid", frozen=True)


class AdherenceModel(BaseModel):
    baseline_fidelity: Parameter
    deviation_drivers: dict[str, Parameter]
    deviation_target: DeviationTarget

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def _fidelity_in_unit_interval(self) -> AdherenceModel:
        value = point_value(self.baseline_fidelity)
        if not 0.0 <= value <= 1.0:
            raise ValueError("baseline_fidelity must be in [0, 1]")
        return self


def _flag_value(host: Host, name: str) -> Any:
    raw = host.comorbidity.get(name)
    if raw is None:
        raw = host.demographics.get(name)
    return raw


def _rule_matches(rule: PolicyRule, host: Host) -> bool:
    if rule.when is None:
        return True
    return bool(_flag_value(host, rule.when))


def policy_preference(policy: Policy, host: Host) -> list[str]:
    """Return ordered preferred drugs for this host.

    First matching rule, or ``rules[0].preferred`` if none match.
    """
    for rule in policy.rules:
        if _rule_matches(rule, host):
            return list(rule.preferred)
    return list(policy.rules[0].preferred)


def _driver_state(host: Host, name: str) -> float:
    raw = _flag_value(host, name)
    if raw is None:
        return 0.0
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 1.0 if raw else 0.0


def effective_fidelity(host: Host, adherence: AdherenceModel) -> float:
    """Deterministic fidelity in [0, 1] given host state and adherence.

    Starts from the baseline_fidelity point value. Each driver subtracts
    ``host_state * weight``. High severity lowers fidelity. No RNG.
    """
    fidelity = point_value(adherence.baseline_fidelity)
    for name, weight in adherence.deviation_drivers.items():
        fidelity -= _driver_state(host, name) * point_value(weight)
    if fidelity < 0.0:
        return 0.0
    if fidelity > 1.0:
        return 1.0
    return float(fidelity)


def execute_choice(
    host: Host,
    policy: Policy,
    constraints: ConstraintSet,
    adherence: AdherenceModel,
    rng: np.random.Generator,
) -> list[str]:
    """Empiric drugs: policy, then feasibility, then adherence.

    If no preferred drug is admissible, return []. If the draw stays
    with policy, return admissible preferred drugs in policy order.
    Otherwise pick feasible ``deviation_target`` drugs, or the first
    remaining admissible preferred drug. Never a uniform global draw.
    """
    preferred = policy_preference(policy, host)
    feasible = evaluate(host, preferred, constraints)
    if not feasible.admissible:
        return []
    if float(rng.random()) < effective_fidelity(host, adherence):
        return list(feasible.admissible)
    target = evaluate(host, list(adherence.deviation_target.drugs), constraints)
    if target.admissible:
        return list(target.admissible)
    return [feasible.admissible[0]]
