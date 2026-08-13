"""Policy representation and fidelity-1.0 execution (GOAL §4.4, AT-14)."""

from __future__ import annotations

import ast
import inspect
import math
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from stewardsim.episode import (
    DeEscalationRule,
    Episode,
    EscalationRule,
    TherapyLine,
    open_episode,
)
from stewardsim.feasibility import ConstraintSet, Rule, evaluate
from stewardsim.host import Host
from stewardsim.params import DistributionSpec, Parameter, Provenance
from stewardsim.policy import (
    AdherenceModel,
    DeviationTarget,
    Policy,
    PolicyRule,
    execute_choice,
    policy_preference,
)

_SEED = 20260812
_N_EPISODES = 1000
_SRC = Path("src/stewardsim")
_TEST_SRC = Path("tests")


def _point(name: str, value: float) -> Parameter:
    return Parameter(
        name=name,
        provenance=Provenance.ASSUMED,
        distribution=DistributionSpec(family="point", fitted_params={"value": value}),
        source="test://slice0",
    )


def _host(*, host_id: int = 1, comorbidity: dict | None = None) -> Host:
    return Host(id=host_id, exposure_history=[], comorbidity=comorbidity or {})


def _policy(
    preferred: list[str] | None = None,
    *,
    rules: list[PolicyRule] | None = None,
    reserve: list[str] | None = None,
) -> Policy:
    return Policy(
        id="slice0_empiric",
        rules=rules
        if rules is not None
        else [PolicyRule(preferred=list(preferred or ["drug_a", "drug_b"]))],
        reserve=list(reserve or []),
        duration=_point("duration", 5.0),
    )


def _adherence(
    *,
    fidelity: float = 1.0,
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


def test_policy_rule_and_policy_are_frozen_and_forbid_extra() -> None:
    rule = PolicyRule(preferred=["drug_a"])
    policy = _policy()
    with pytest.raises(ValidationError):
        PolicyRule(preferred=["drug_a"], invented="no")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        Policy(
            id="p",
            rules=[rule],
            duration=_point("duration", 3.0),
            escalation_invented=True,  # type: ignore[call-arg]
        )
    with pytest.raises((ValidationError, TypeError)):
        rule.preferred = ["drug_z"]  # type: ignore[misc]
    with pytest.raises((ValidationError, TypeError)):
        policy.id = "other"  # type: ignore[misc]


def test_policy_duration_must_be_parameter_not_raw_float() -> None:
    with pytest.raises((ValidationError, TypeError)):
        Policy(
            id="p",
            rules=[PolicyRule(preferred=["drug_a"])],
            duration=5.0,  # type: ignore[arg-type]
        )


def test_policy_requires_at_least_one_rule() -> None:
    with pytest.raises(ValidationError):
        Policy(id="p", rules=[], duration=_point("duration", 5.0))


def test_policy_preference_default_is_first_rule() -> None:
    policy = _policy(preferred=["drug_b", "drug_a"])
    assert policy_preference(policy, _host()) == ["drug_b", "drug_a"]


def test_policy_preference_matches_comorbidity_flag() -> None:
    policy = _policy(
        rules=[
            PolicyRule(preferred=["drug_c"], when="ckd"),
            PolicyRule(preferred=["drug_a", "drug_b"]),
        ]
    )
    assert policy_preference(policy, _host(comorbidity={"ckd": True})) == ["drug_c"]
    assert policy_preference(policy, _host()) == ["drug_a", "drug_b"]
    assert policy_preference(policy, _host(comorbidity={"ckd": False})) == [
        "drug_a",
        "drug_b",
    ]


def test_policy_preference_falls_back_to_first_rule_when_no_flag_matches() -> None:
    policy = _policy(
        rules=[
            PolicyRule(preferred=["drug_c"], when="ckd"),
            PolicyRule(preferred=["drug_d"], when="neutropenia"),
        ]
    )
    assert policy_preference(policy, _host()) == ["drug_c"]


def test_at14_fidelity_one_executed_equals_feasible_policy() -> None:
    """AT-14: baseline_fidelity=1.0 ⇒ executed == feasibility(policy(host))."""
    rng = np.random.default_rng(_SEED)
    host = _host(comorbidity={"severity": 0.9})
    policy = _policy(preferred=["drug_a", "drug_b", "drug_c"])
    constraints = ConstraintSet(
        hard=[Rule(id="allergy_drug_c", kind="allergy", drug_id="drug_c")],
    )
    host_allergic = _host(
        comorbidity={"severity": 0.9, "allergies": ["drug_c"]},
    )
    adherence = _adherence(fidelity=1.0, drivers={}, target=["drug_x"])
    preferred = policy_preference(policy, host_allergic)
    expected = evaluate(host_allergic, preferred, constraints).admissible
    assert expected == ["drug_a", "drug_b"]

    for _ in range(_N_EPISODES):
        executed = execute_choice(
            host_allergic, policy, constraints, adherence, rng
        )
        assert executed == expected

    assert host.exposure_history == []
    assert host_allergic.exposure_history == []


def test_at14_fidelity_one_preserves_policy_order() -> None:
    rng = np.random.default_rng(_SEED)
    host = _host()
    policy = _policy(preferred=["drug_c", "drug_a", "drug_b"])
    constraints = ConstraintSet(hard=[])
    adherence = _adherence(fidelity=1.0)
    expected = evaluate(
        host, policy_preference(policy, host), constraints
    ).admissible
    assert expected == ["drug_c", "drug_a", "drug_b"]
    for _ in range(200):
        assert (
            execute_choice(host, policy, constraints, adherence, rng) == expected
        )


def test_execute_choice_returns_empty_on_conflict() -> None:
    rng = np.random.default_rng(_SEED)
    host = _host(comorbidity={"cx_drug_a": True})
    policy = _policy(preferred=["drug_a"])
    constraints = ConstraintSet(
        hard=[Rule(id="cx_drug_a", kind="contraindication", drug_id="drug_a")],
    )
    adherence = _adherence(fidelity=1.0, target=["drug_a"])
    feasible = evaluate(host, policy_preference(policy, host), constraints)
    assert feasible.conflict is True
    assert feasible.admissible == []
    assert execute_choice(host, policy, constraints, adherence, rng) == []


def test_execute_choice_same_seed_is_bit_identical() -> None:
    host = _host(comorbidity={"severity": 0.4})
    policy = _policy(preferred=["drug_a"])
    constraints = ConstraintSet(hard=[])
    adherence = _adherence(fidelity=0.7, drivers={"severity": 0.3}, target=["drug_x"])

    def _run(seed: int) -> list[list[str]]:
        rng = np.random.default_rng(seed)
        return [
            execute_choice(host, policy, constraints, adherence, rng)
            for _ in range(200)
        ]

    assert _run(_SEED) == _run(_SEED)


def test_open_episode_line_one_matches_execute_choice() -> None:
    host = _host()
    policy = _policy(preferred=["drug_a", "drug_b"])
    constraints = ConstraintSet(hard=[])
    adherence = _adherence(fidelity=1.0, target=["drug_x"])
    delay = _point("culture_delay", 2.0)

    rng_a = np.random.default_rng(_SEED)
    rng_b = np.random.default_rng(_SEED)
    executed = execute_choice(host, policy, constraints, adherence, rng_a)
    episode = open_episode(
        host,
        policy,
        constraints,
        adherence,
        rng_b,
        t=4,
        culture_delay=delay,
    )
    assert isinstance(episode, Episode)
    assert episode.host_id == host.id
    assert len(episode.lines) == 1
    assert episode.lines[0] == TherapyLine(line=1, drugs=executed, t=4)
    assert episode.culture_return_t == 6
    assert episode.conflict is False
    assert episode.rounds_to_effective is None


def test_open_episode_conflict_records_empty_line() -> None:
    rng = np.random.default_rng(_SEED)
    host = _host(host_id=9, comorbidity={"cx_drug_a": True})
    policy = _policy(preferred=["drug_a"])
    constraints = ConstraintSet(
        hard=[Rule(id="cx_drug_a", kind="contraindication", drug_id="drug_a")],
    )
    adherence = _adherence(fidelity=1.0)
    episode = open_episode(host, policy, constraints, adherence, rng, t=0)
    assert episode.conflict is True
    assert episode.lines == [TherapyLine(line=1, drugs=[], t=0)]
    assert episode.rounds_to_effective is None


def test_escalation_types_exist_and_are_frozen() -> None:
    rule = EscalationRule(culture_delay=_point("culture_delay", 2.0))
    de = DeEscalationRule(culture_delay=_point("culture_delay", 3.0))
    assert rule.culture_delay.distribution.family == "point"
    assert de.culture_delay.distribution.fitted_params == {"value": 3.0}
    with pytest.raises(ValidationError):
        EscalationRule(culture_delay=_point("culture_delay", 1.0), extra=True)  # type: ignore[call-arg]
    with pytest.raises((ValidationError, TypeError)):
        rule.culture_delay = _point("culture_delay", 9.0)  # type: ignore[misc]


def test_policy_and_episode_source_has_no_banned_framing() -> None:
    banned = (
        "inappropriate" + " prescribing",
        "prescriber" + " error",
        "mis" + "use",
        "compl" + "iance",
    )
    paths = [
        _SRC / "policy.py",
        _SRC / "episode.py",
        _TEST_SRC / "test_policy.py",
        _TEST_SRC / "test_adherence.py",
    ]
    for path in paths:
        text = path.read_text().lower()
        for phrase in banned:
            assert phrase not in text, f"{phrase!r} in {path}"


def test_execute_choice_uses_only_provided_generator() -> None:
    source = inspect.getsource(execute_choice)
    tree = ast.parse(inspect.getsource(inspect.getmodule(execute_choice)))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.add(module)
    assert "random" not in imported
    assert "np.random.random(" not in source
    assert "numpy.random.random" not in source
    assert "default_rng" not in source


def test_n_episodes_at_least_one_thousand() -> None:
    assert _N_EPISODES >= 1000
    assert math.isfinite(_SEED)
