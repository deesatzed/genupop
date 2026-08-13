"""Restriction-loop coupling (GOAL §6.6, design §2).

Hosts are constructed in this module (structural fixtures). Two drugs
{A, B}, one determinant conferring resistance to A only, tape that bans
A after day T.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from stewardsim.feasibility import ConstraintSet, Rule, evaluate
from stewardsim.host import Host
from stewardsim.importation import Importation
from stewardsim.params import DistributionSpec, Parameter, Provenance
from stewardsim.pathogen import Determinant, step_deterministic, step_recessive_diploid
from stewardsim.policy import AdherenceModel, DeviationTarget, Policy, PolicyRule
from stewardsim.restriction import ForcedRestriction, RestrictionInterval
from stewardsim.simulate import (
    SimulateResult,
    compose_restrictions,
    line_is_effective,
    selection_coefficient,
    simulate,
)

_SEED = 20260812
_T = 4
_HORIZON = 10
_P0 = 0.25
_S_MAX = 0.4
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


def _hosts(n: int = 3) -> list[Host]:
    return [_host(host_id=i + 1) for i in range(n)]


def _policy(
    preferred: list[str] | None = None, *, duration: float = 1.0
) -> Policy:
    return Policy(
        id="slice0_prefer_A",
        rules=[PolicyRule(preferred=list(preferred or ["A", "B"]))],
        duration=_point("duration", duration),
    )


def _adherence(*, fidelity: float = 1.0, target: list[str] | None = None) -> AdherenceModel:
    return AdherenceModel(
        baseline_fidelity=_point("baseline_fidelity", fidelity),
        deviation_drivers={},
        deviation_target=DeviationTarget(drugs=list(target or ["B"])),
    )


def _determinant(*, cost: float = 0.0, confers: list[str] | None = None) -> Determinant:
    return Determinant(
        id="det_A",
        confers_resistance_to=list(confers or ["A"]),
        fitness_cost=_point("fitness_cost", cost),
    )


def _ban_A_after(t: int, *, horizon: int = _HORIZON) -> ForcedRestriction:
    return ForcedRestriction(
        intervals=[RestrictionInterval(drug_id="A", t0=t, t1=horizon)]
    )


def _empty_tape() -> ForcedRestriction:
    return ForcedRestriction(intervals=[])


def _zero_importation() -> Importation:
    return Importation(
        rate=_point("import_rate", 0.0),
        determinant_mix={},
        source_correlation=_point("source_correlation", 0.0),
    )


def _run(
    *,
    tape: ForcedRestriction | None = None,
    p0: float = _P0,
    s_max: float = _S_MAX,
    cost: float = 0.0,
    horizon: int = _HORIZON,
    hosts: list[Host] | None = None,
    policy: Policy | None = None,
    constraints: ConstraintSet | None = None,
    adherence: AdherenceModel | None = None,
    determinant: Determinant | None = None,
    importation: Importation | None = None,
    seed: int = _SEED,
) -> SimulateResult:
    rng = np.random.default_rng(seed)
    return simulate(
        hosts if hosts is not None else _hosts(),
        policy=policy if policy is not None else _policy(),
        constraints=constraints if constraints is not None else ConstraintSet(hard=[]),
        adherence=adherence if adherence is not None else _adherence(),
        tape=tape if tape is not None else _ban_A_after(_T, horizon=horizon),
        determinant=determinant if determinant is not None else _determinant(cost=cost),
        p0=p0,
        horizon=horizon,
        rng=rng,
        s_max=s_max,
        importation=importation,
    )


def test_before_T_realized_dose_days_of_A_are_positive() -> None:
    result = _run()
    assert "A" in result.dose_days
    assert len(result.dose_days["A"]) == _HORIZON
    before = result.dose_days["A"][:_T]
    assert sum(before) > 0.0
    assert all(day > 0.0 for day in before)


def test_after_T_new_A_dose_days_stop() -> None:
    result = _run()
    after = result.dose_days["A"][_T:]
    assert after
    assert all(day == 0.0 for day in after)
    assert sum(result.dose_days["B"][_T:]) > 0.0


def test_after_T_feasibility_treats_A_as_inadmissible() -> None:
    tape = _ban_A_after(_T)
    base = ConstraintSet(hard=[])
    host = _host()
    at_T = compose_restrictions(base, tape.play(_T))
    banned = evaluate(host, ["A", "B"], at_T)
    assert "A" not in banned.admissible
    assert "A" in banned.excluded
    assert banned.excluded["A"] == "restriction:A"
    assert banned.excluded["A"].count("restriction:") == 1
    assert "B" in banned.admissible
    assert banned.conflict is False

    before_T = compose_restrictions(base, tape.play(_T - 1))
    open_day = evaluate(host, ["A", "B"], before_T)
    assert "A" in open_day.admissible
    assert "A" not in open_day.excluded


def test_frequency_trajectory_after_T_differs_from_unrestricted_control() -> None:
    restricted = _run(tape=_ban_A_after(_T), seed=_SEED)
    control = _run(tape=_empty_tape(), seed=_SEED)
    assert restricted.frequencies[:_T] == pytest.approx(control.frequencies[:_T])
    assert restricted.frequencies[_T:] != control.frequencies[_T:]
    assert list(restricted.frequencies[_T:]) != list(control.frequencies[_T:])


def test_rounds_to_effective_present_next_to_frequencies() -> None:
    result = _run()
    fields = list(SimulateResult.model_fields)
    assert "frequencies" in fields
    assert "rounds_to_effective" in fields
    freq_i = fields.index("frequencies")
    rounds_i = fields.index("rounds_to_effective")
    assert abs(freq_i - rounds_i) == 1
    assert isinstance(result.frequencies, list)
    assert len(result.frequencies) == _HORIZON
    assert isinstance(result.rounds_to_effective, float)
    assert isinstance(result.mean_rounds_to_effective, float)
    assert result.rounds_to_effective == result.mean_rounds_to_effective
    dumped = result.model_dump()
    assert "rounds_to_effective" in dumped
    assert dumped["rounds_to_effective"] == result.rounds_to_effective
    assert dumped["rounds_to_effective"] == result.mean_rounds_to_effective


def test_conflict_log_is_a_list() -> None:
    result = _run()
    assert isinstance(result.conflict_log, list)
    assert all(isinstance(entry, dict) for entry in result.conflict_log)


def test_line_is_effective_rule() -> None:
    """First drug is effective unless p > 0.5 and it is conferred."""
    det = _determinant()
    assert line_is_effective("A", 0.5, det) is True
    assert line_is_effective("A", 0.0, det) is True
    assert line_is_effective("A", 0.5000001, det) is False
    assert line_is_effective("A", 0.9, det) is False
    assert line_is_effective("B", 0.9, det) is True
    assert line_is_effective("B", 0.0, det) is True


def test_mean_rounds_follows_effective_rule() -> None:
    always_A = _run(tape=_empty_tape(), p0=0.9, s_max=0.0, cost=0.0)
    assert always_A.mean_rounds_to_effective == pytest.approx(2.0)
    banned_A = _run(tape=_ban_A_after(0), p0=0.9, s_max=0.0, cost=0.0)
    assert banned_A.mean_rounds_to_effective == pytest.approx(1.0)
    below = _run(tape=_empty_tape(), p0=0.2, s_max=0.0, cost=0.0)
    assert below.mean_rounds_to_effective == pytest.approx(1.0)


def test_selection_coefficient_is_function_of_realized_exposure() -> None:
    s_all_A = selection_coefficient(
        dose_days_by_drug={"A": 3.0, "B": 0.0},
        confers_resistance_to=["A"],
        n_treated=3,
        s_max=_S_MAX,
    )
    assert s_all_A == pytest.approx(_S_MAX)
    s_half = selection_coefficient(
        dose_days_by_drug={"A": 2.0, "B": 2.0},
        confers_resistance_to=["A"],
        n_treated=4,
        s_max=_S_MAX,
    )
    assert s_half == pytest.approx(_S_MAX * 0.5)
    s_none = selection_coefficient(
        dose_days_by_drug={"A": 0.0, "B": 3.0},
        confers_resistance_to=["A"],
        n_treated=3,
        s_max=_S_MAX,
    )
    assert s_none == 0.0
    s_idle = selection_coefficient(
        dose_days_by_drug={"A": 0.0, "B": 0.0},
        confers_resistance_to=["A"],
        n_treated=0,
        s_max=_S_MAX,
    )
    assert s_idle == 0.0


def test_frequencies_follow_haploid_map_of_realized_exposure() -> None:
    result = _run()
    p = _P0
    expected: list[float] = []
    cost = 0.0
    for t in range(_HORIZON):
        day = {drug: series[t] for drug, series in result.dose_days.items()}
        n_treated = int(round(sum(day.values())))
        s = selection_coefficient(
            dose_days_by_drug=day,
            confers_resistance_to=["A"],
            n_treated=n_treated,
            s_max=_S_MAX,
        )
        p = step_deterministic(p, s=s, fitness_cost=cost)
        expected.append(p)
    assert result.frequencies == pytest.approx(expected)
    # Not the recessive diploid map
    q = _P0
    diploid = []
    for t in range(_HORIZON):
        day = {drug: series[t] for drug, series in result.dose_days.items()}
        n_treated = int(round(sum(day.values())))
        s = selection_coefficient(
            dose_days_by_drug=day,
            confers_resistance_to=["A"],
            n_treated=n_treated,
            s_max=_S_MAX,
        )
        q = step_recessive_diploid(q, s=s, mu=0.0)
        diploid.append(q)
    assert result.frequencies != pytest.approx(diploid)


def test_no_A_exposure_and_zero_cost_leaves_frequency_unchanged() -> None:
    result = _run(tape=_ban_A_after(0), p0=0.3, cost=0.0, s_max=_S_MAX)
    assert result.dose_days["A"] == [0.0] * _HORIZON
    assert result.frequencies == pytest.approx([0.3] * _HORIZON)


def test_importation_accepted_as_typed_argument() -> None:
    result = _run(importation=_zero_importation())
    assert isinstance(result, SimulateResult)
    assert len(result.frequencies) == _HORIZON


def test_policy_duration_does_not_change_daily_loop() -> None:
    """Slice-0 incidence is daily; Policy.duration is stored, not applied."""
    daily = _run(policy=_policy(duration=1.0))
    week = _run(policy=_policy(duration=7.0))
    assert len(daily.frequencies) == _HORIZON
    assert len(week.frequencies) == _HORIZON
    assert daily.frequencies == week.frequencies
    assert daily.dose_days == week.dose_days
    assert daily.rounds_to_effective == week.rounds_to_effective
    n_hosts = 3
    assert daily.dose_days["A"][:_T] == [float(n_hosts)] * _T
    source = inspect.getsource(simulate)
    assert "point_value(policy.duration)" not in source


def test_simulate_requires_numpy_generator() -> None:
    with pytest.raises(TypeError):
        simulate(
            _hosts(),
            policy=_policy(),
            constraints=ConstraintSet(hard=[]),
            adherence=_adherence(),
            tape=_empty_tape(),
            determinant=_determinant(),
            p0=_P0,
            horizon=_HORIZON,
            rng=None,  # type: ignore[arg-type]
            s_max=_S_MAX,
        )


def test_same_seed_is_bit_identical() -> None:
    first = _run(seed=_SEED)
    second = _run(seed=_SEED)
    assert first.frequencies == second.frequencies
    assert first.dose_days == second.dose_days
    assert first.mean_rounds_to_effective == second.mean_rounds_to_effective
    assert first.conflict_log == second.conflict_log


def test_conflict_does_not_invent_a_drug() -> None:
    result = _run(
        policy=_policy(preferred=["A"]),
        tape=_ban_A_after(0),
        adherence=_adherence(target=["A"]),
    )
    assert all(day == 0.0 for day in result.dose_days["A"])
    assert "B" not in result.dose_days or all(day == 0.0 for day in result.dose_days["B"])
    assert result.conflict_log
    assert all(isinstance(entry, dict) for entry in result.conflict_log)
    for entry in result.conflict_log:
        assert entry["preferred_drugs"] == ["A"]
        assert "A" in entry["excluded"]


def test_does_not_use_recessive_diploid_map() -> None:
    import stewardsim.simulate as simulate_mod

    source = inspect.getsource(simulate_mod)
    assert "step_deterministic" in source
    assert "step_recessive_diploid" not in source


def test_structural_hosts_not_event_files() -> None:
    hosts = _hosts()
    assert all(isinstance(host, Host) for host in hosts)
    assert all(host.exposure_history == [] for host in hosts)
    event_root = "data/" + "derived/" + "event_"
    mock_mod = "unittest" + "." + "mock"
    impl = (_SRC / "simulate.py").read_text()
    tests = (_TEST_SRC / "test_simulate.py").read_text()
    assert event_root not in impl
    assert event_root not in tests
    assert mock_mod not in impl
    assert "MagicMock" not in impl


def test_no_banned_framing() -> None:
    banned = (
        "inappropriate" + " prescribing",
        "prescriber" + " error",
        "mis" + "use",
        "compl" + "iance",
    )
    for path in (_SRC / "simulate.py", _TEST_SRC / "test_simulate.py"):
        text = path.read_text().lower()
        for phrase in banned:
            assert phrase not in text, f"{phrase!r} in {path}"


def test_determinant_slice0_fields_and_fitness_cost_is_parameter() -> None:
    det = _determinant()
    assert det.id == "det_A"
    assert det.confers_resistance_to == ["A"]
    assert isinstance(det.fitness_cost, Parameter)
    with pytest.raises((ValidationError, TypeError)):
        Determinant(
            id="det_A",
            confers_resistance_to=["A"],
            fitness_cost=0.1,  # type: ignore[arg-type]
        )
    with pytest.raises((ValidationError, TypeError)):
        det.fitness_cost = _point("fitness_cost", 0.2)  # type: ignore[misc]


def test_simulate_result_is_frozen() -> None:
    result = _run()
    with pytest.raises((ValidationError, TypeError)):
        result.frequencies = []  # type: ignore[misc]
    with pytest.raises(ValidationError):
        SimulateResult(
            frequencies=[0.1],
            rounds_to_effective=1.0,
            conflict_log=[],
            dose_days={"A": [0.0]},
            invented=True,  # type: ignore[call-arg]
        )


def test_simulate_module_does_not_construct_unseeded_rng() -> None:
    import stewardsim.simulate as simulate_mod

    source = inspect.getsource(simulate_mod)
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.add(module)
    assert "random" not in imported
    assert "default_rng" not in source
