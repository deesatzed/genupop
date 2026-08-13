"""State-dependent adherence (GOAL §4.5, AT-14).

Deviation is a function of host state. A model that substitutes uniformly
at random over a global drug list, or that ignores drivers, fails these tests.
"""

from __future__ import annotations

import inspect
import math
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from stewardsim.feasibility import ConstraintSet, Rule, evaluate
from stewardsim.host import Host
from stewardsim.params import DistributionSpec, Parameter, Provenance
from stewardsim.policy import (
    AdherenceModel,
    DeviationTarget,
    Policy,
    PolicyRule,
    effective_fidelity,
    execute_choice,
    policy_preference,
)

_SEED = 20260812
_N = 2000


def _point(name: str, value: float) -> Parameter:
    return Parameter(
        name=name,
        provenance=Provenance.ASSUMED,
        distribution=DistributionSpec(family="point", fitted_params={"value": value}),
        source="test://slice0",
    )


def _host(*, host_id: int = 1, comorbidity: dict | None = None) -> Host:
    return Host(id=host_id, exposure_history=[], comorbidity=comorbidity or {})


def _policy(preferred: list[str] | None = None) -> Policy:
    return Policy(
        id="slice0_empiric",
        rules=[PolicyRule(preferred=list(preferred or ["drug_a"]))],
        duration=_point("duration", 5.0),
    )


def _adherence(
    *,
    fidelity: float,
    drivers: dict[str, float] | None = None,
    target: list[str] | None = None,
) -> AdherenceModel:
    return AdherenceModel(
        baseline_fidelity=_point("baseline_fidelity", fidelity),
        deviation_drivers={
            name: _point(name, weight) for name, weight in (drivers or {}).items()
        },
        deviation_target=DeviationTarget(drugs=list(target or ["drug_x"])),
    )


def _mc_envelope(p: float, n: int, se_mult: float = 4.0) -> float:
    return se_mult * math.sqrt(p * (1.0 - p) / n)


def test_adherence_models_are_frozen_and_forbid_extra() -> None:
    target = DeviationTarget(drugs=["drug_x"])
    model = _adherence(fidelity=0.7)
    with pytest.raises(ValidationError):
        DeviationTarget(drugs=["drug_x"], invented=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        AdherenceModel(
            baseline_fidelity=_point("baseline_fidelity", 0.7),
            deviation_drivers={},
            deviation_target=target,
            noise=0.1,  # type: ignore[call-arg]
        )
    with pytest.raises((ValidationError, TypeError)):
        target.drugs = ["drug_z"]  # type: ignore[misc]
    with pytest.raises((ValidationError, TypeError)):
        model.baseline_fidelity = _point("baseline_fidelity", 1.0)  # type: ignore[misc]


def test_baseline_fidelity_must_be_parameter_not_raw_float() -> None:
    with pytest.raises((ValidationError, TypeError)):
        AdherenceModel(
            baseline_fidelity=0.7,  # type: ignore[arg-type]
            deviation_drivers={},
            deviation_target=DeviationTarget(drugs=["drug_x"]),
        )


def test_baseline_fidelity_point_value_must_lie_in_unit_interval() -> None:
    with pytest.raises(ValueError):
        _adherence(fidelity=1.2)
    with pytest.raises(ValueError):
        _adherence(fidelity=-0.01)


def test_driver_weights_must_be_point_and_nonnegative() -> None:
    with pytest.raises(ValueError):
        _adherence(fidelity=0.7, drivers={"severity": -0.1})
    with pytest.raises(ValueError):
        AdherenceModel(
            baseline_fidelity=_point("baseline_fidelity", 0.7),
            deviation_drivers={
                "severity": Parameter(
                    name="severity",
                    provenance=Provenance.ASSUMED,
                    distribution=DistributionSpec(
                        family="lognormal",
                        quantiles={0.05: 0.01, 0.5: 0.05, 0.95: 0.2},
                    ),
                    source="test://slice0",
                )
            },
            deviation_target=DeviationTarget(drugs=["drug_x"]),
        )


def test_deviation_target_requires_at_least_one_drug() -> None:
    with pytest.raises(ValidationError):
        DeviationTarget(drugs=[])


def test_effective_fidelity_equals_baseline_without_driver_state() -> None:
    adherence = _adherence(fidelity=0.7, drivers={"severity": 0.5})
    assert effective_fidelity(_host(), adherence) == pytest.approx(0.7)
    assert effective_fidelity(_host(comorbidity={"severity": 0.0}), adherence) == (
        pytest.approx(0.7)
    )


def test_effective_fidelity_falls_when_severity_rises() -> None:
    adherence = _adherence(fidelity=0.7, drivers={"severity": 0.5})
    low = effective_fidelity(_host(comorbidity={"severity": 0.0}), adherence)
    high = effective_fidelity(_host(comorbidity={"severity": 1.0}), adherence)
    assert high < low
    assert 0.0 <= high <= 1.0
    assert 0.0 <= low <= 1.0
    assert low == pytest.approx(0.7)
    # gap=0.3, boost=1.5 ⇒ fidelity = 1 - 0.3*1.5 = 0.55
    assert high == pytest.approx(0.55)


def test_effective_fidelity_is_deterministic() -> None:
    host = _host(comorbidity={"severity": 0.6, "off_hours": True})
    adherence = _adherence(fidelity=0.8, drivers={"severity": 0.4, "off_hours": 0.1})
    first = effective_fidelity(host, adherence)
    second = effective_fidelity(host, adherence)
    assert first == second
    source = inspect.getsource(effective_fidelity)
    assert "rng" not in source
    assert "random" not in source


def test_at14_fidelity_0_7_deviation_frequency_within_mc_error() -> None:
    """AT-14: baseline_fidelity=0.7 ⇒ realized deviation frequency ≈ 0.3."""
    rng = np.random.default_rng(_SEED)
    host = _host(comorbidity={"severity": 0.0})
    policy = _policy(["drug_a"])
    constraints = ConstraintSet(hard=[])
    adherence = _adherence(fidelity=0.7, drivers={"severity": 0.5}, target=["drug_x"])
    preferred = policy_preference(policy, host)
    specified = evaluate(host, preferred, constraints).admissible
    assert specified == ["drug_a"]
    assert effective_fidelity(host, adherence) == pytest.approx(0.7)

    n_dev = 0
    for _ in range(_N):
        executed = execute_choice(host, policy, constraints, adherence, rng)
        if executed != specified:
            n_dev += 1
    rate = n_dev / _N
    assert abs(rate - 0.3) <= _mc_envelope(0.3, _N)


def test_at14_deviation_rate_higher_when_severity_high() -> None:
    """AT-14: deviation correlates with drivers — uniform random deviation fails."""
    host_low = _host(host_id=1, comorbidity={"severity": 0.0})
    host_high = _host(host_id=2, comorbidity={"severity": 1.0})
    policy = _policy(["drug_a"])
    constraints = ConstraintSet(hard=[])
    adherence = _adherence(fidelity=0.7, drivers={"severity": 0.5}, target=["drug_x"])
    specified = ["drug_a"]

    fid_low = effective_fidelity(host_low, adherence)
    fid_high = effective_fidelity(host_high, adherence)
    assert fid_high < fid_low

    def _rate(host: Host, seed: int) -> float:
        rng = np.random.default_rng(seed)
        n_dev = 0
        for _ in range(_N):
            executed = execute_choice(host, policy, constraints, adherence, rng)
            if executed != specified:
                n_dev += 1
        return n_dev / _N

    rate_low = _rate(host_low, _SEED)
    rate_high = _rate(host_high, _SEED)
    expected_low = 1.0 - fid_low
    expected_high = 1.0 - fid_high
    assert abs(rate_low - expected_low) <= _mc_envelope(expected_low, _N)
    assert abs(rate_high - expected_high) <= _mc_envelope(expected_high, _N)
    assert rate_high > rate_low
    # A state-blind draw at the baseline gap cannot separate these arms.
    gap = rate_high - rate_low
    assert gap > _mc_envelope(expected_low, _N) + _mc_envelope(expected_high, _N)


def test_at14_substitute_comes_from_deviation_target() -> None:
    """Substitute is taken from deviation_target, never a global drug draw."""
    rng = np.random.default_rng(_SEED)
    all_drugs = [f"drug_{i}" for i in range(20)]
    target = ["drug_x", "drug_y"]
    host = _host()
    policy = _policy(["drug_a"])
    constraints = ConstraintSet(hard=[])
    # Always deviate so every draw is a substitute.
    adherence = _adherence(fidelity=0.0, drivers={}, target=target)
    specified = evaluate(
        host, policy_preference(policy, host), constraints
    ).admissible
    assert specified == ["drug_a"]

    seen: set[str] = set()
    for _ in range(_N):
        executed = execute_choice(host, policy, constraints, adherence, rng)
        assert executed != specified
        assert executed, "deviation must still name a feasible substitute"
        assert all(drug in target for drug in executed)
        assert not any(drug in all_drugs for drug in executed)
        seen.update(executed)
    assert seen <= set(target)
    assert "drug_x" in seen


def test_deviation_target_respects_feasibility() -> None:
    rng = np.random.default_rng(_SEED)
    host = _host(comorbidity={"allergies": ["drug_x"]})
    policy = _policy(["drug_a", "drug_b"])
    constraints = ConstraintSet(
        hard=[Rule(id="allergy_drug_x", kind="allergy", drug_id="drug_x")],
    )
    adherence = _adherence(fidelity=0.0, target=["drug_x", "drug_y"])
    executed = execute_choice(host, policy, constraints, adherence, rng)
    assert "drug_x" not in executed
    assert executed == ["drug_y"]


def test_infeasible_deviation_target_falls_back_to_first_admissible() -> None:
    rng = np.random.default_rng(_SEED)
    host = _host(comorbidity={"allergies": ["drug_x"]})
    policy = _policy(["drug_a", "drug_b"])
    constraints = ConstraintSet(
        hard=[Rule(id="allergy_drug_x", kind="allergy", drug_id="drug_x")],
    )
    adherence = _adherence(fidelity=0.0, target=["drug_x"])
    specified = evaluate(
        host, policy_preference(policy, host), constraints
    ).admissible
    assert specified == ["drug_a", "drug_b"]
    executed = execute_choice(host, policy, constraints, adherence, rng)
    assert executed == [specified[0]]
    assert executed == ["drug_a"]


def test_execute_choice_never_emits_hard_constraint_violation() -> None:
    rng = np.random.default_rng(_SEED)
    host = _host(comorbidity={"allergies": ["drug_a", "drug_x"]})
    policy = _policy(["drug_a", "drug_b"])
    constraints = ConstraintSet(
        hard=[
            Rule(id="allergy_drug_a", kind="allergy", drug_id="drug_a"),
            Rule(id="allergy_drug_x", kind="allergy", drug_id="drug_x"),
        ],
    )
    adherence = _adherence(fidelity=0.5, target=["drug_x", "drug_y"])
    for _ in range(_N):
        executed = execute_choice(host, policy, constraints, adherence, rng)
        assert "drug_a" not in executed
        assert "drug_x" not in executed


def test_no_unseeded_global_rng_in_policy_module() -> None:
    source = Path("src/stewardsim/policy.py").read_text()
    assert "np.random.random" not in source
    assert "numpy.random.random" not in source
    assert "default_rng" not in source
    assert "random.choice" not in source
