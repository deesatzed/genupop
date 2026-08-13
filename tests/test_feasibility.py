"""AT-13 feasibility oracle: mechanical hard-rule pruning, no RNG."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from stewardsim.feasibility import (
    ConstraintSet,
    Rule,
    evaluate,
    load_constraints,
)
from stewardsim.host import Host

_SLICE0_CONSTRAINTS = Path("configs/constraints/slice0.yaml")


def _host(*, host_id: int = 1, comorbidity: dict | None = None) -> Host:
    return Host(id=host_id, exposure_history=[], comorbidity=comorbidity or {})


def test_allergy_to_drug_a_excludes_a_with_reason() -> None:
    host = _host(comorbidity={"allergies": ["drug_a"]})
    constraints = ConstraintSet(
        hard=[Rule(id="allergy_drug_a", kind="allergy", drug_id="drug_a")],
    )
    result = evaluate(host, ["drug_a", "drug_b"], constraints)
    assert "drug_a" not in result.admissible
    assert "drug_b" in result.admissible
    assert "drug_a" in result.excluded
    reason = result.excluded["drug_a"]
    assert reason
    assert "allerg" in reason.lower()
    assert result.conflict is False


def test_seeded_contraindication_of_only_policy_drug_is_conflict() -> None:
    host = _host(host_id=2, comorbidity={"cx_drug_a": True})
    constraints = ConstraintSet(
        hard=[Rule(id="cx_drug_a", kind="contraindication", drug_id="drug_a")],
    )
    result = evaluate(host, ["drug_a"], constraints)
    assert result.conflict is True
    assert result.admissible == []
    assert "drug_a" in result.excluded
    reason = result.excluded["drug_a"]
    assert reason
    assert "contraindicat" in reason.lower()
    assert result.log_entry is not None
    assert result.log_entry["host_id"] == 2
    assert result.log_entry["preferred_drugs"] == ["drug_a"]
    assert result.log_entry["excluded"] == result.excluded
    assert set(result.log_entry["excluded"]) == {"drug_a"}


def test_oracle_is_pure_function_no_rng() -> None:
    import stewardsim.feasibility as feasibility

    source = inspect.getsource(feasibility)
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.add(module)
            imported.update(f"{module}.{alias.name}" for alias in node.names)

    assert "random" not in imported
    assert "numpy.random" not in imported
    assert "numpy.random" not in source
    assert "default_rng" not in source

    host = _host(comorbidity={"allergies": ["drug_a"]})
    constraints = ConstraintSet(
        hard=[
            Rule(id="allergy_drug_a", kind="allergy", drug_id="drug_a"),
            Rule(id="cx_drug_b", kind="contraindication", drug_id="drug_b"),
        ],
    )
    preferred = ["drug_a", "drug_b", "drug_c"]
    first = evaluate(host, preferred, constraints)
    second = evaluate(host, preferred, constraints)
    assert first == second
    assert host.exposure_history == []
    assert host.comorbidity == {"allergies": ["drug_a"]}
    assert preferred == ["drug_a", "drug_b", "drug_c"]


def test_conflict_does_not_invent_a_drug() -> None:
    host = _host(host_id=3, comorbidity={"cx_drug_a": True})
    constraints = ConstraintSet(
        hard=[Rule(id="cx_drug_a", kind="contraindication", drug_id="drug_a")],
    )
    result = evaluate(host, ["drug_a"], constraints)
    assert result.admissible == []
    assert set(result.excluded) == {"drug_a"}
    assert result.log_entry is not None
    assert set(result.log_entry["excluded"]) == {"drug_a"}
    assert result.log_entry["preferred_drugs"] == ["drug_a"]


def test_allergy_rule_does_not_fire_without_listed_allergy() -> None:
    host = _host(comorbidity={"allergies": ["drug_b"]})
    constraints = ConstraintSet(
        hard=[Rule(id="allergy_drug_a", kind="allergy", drug_id="drug_a")],
    )
    result = evaluate(host, ["drug_a"], constraints)
    assert result.admissible == ["drug_a"]
    assert "drug_a" not in result.excluded
    assert result.conflict is False


def test_soft_rules_are_unused() -> None:
    host = _host(comorbidity={"allergies": ["drug_a"]})
    constraints = ConstraintSet(
        hard=[],
        soft=[Rule(id="soft_allergy_a", kind="allergy", drug_id="drug_a")],
    )
    result = evaluate(host, ["drug_a"], constraints)
    assert result.admissible == ["drug_a"]
    assert result.excluded == {}
    assert result.conflict is False


def test_admissible_preserves_policy_order() -> None:
    host = _host()
    constraints = ConstraintSet(hard=[])
    result = evaluate(host, ["drug_c", "drug_a", "drug_b"], constraints)
    assert result.admissible == ["drug_c", "drug_a", "drug_b"]
    assert result.conflict is False


def test_slice0_yaml_has_structural_allergy_and_contraindication() -> None:
    constraints = load_constraints(_SLICE0_CONSTRAINTS)
    kinds = {rule.kind for rule in constraints.hard}
    assert "allergy" in kinds
    assert "contraindication" in kinds
    assert all(rule.drug_id.startswith("drug_") for rule in constraints.hard)
    assert constraints.sources == [] or all(
        source.startswith("test://") for source in constraints.sources
    )


def test_contraindication_absent_flag_admits_drug() -> None:
    host = _host()
    constraints = ConstraintSet(
        hard=[Rule(id="cx_drug_b", kind="contraindication", drug_id="drug_b")],
    )
    result = evaluate(host, ["drug_b"], constraints)
    assert result.admissible == ["drug_b"]
    assert "drug_b" not in result.excluded
    assert result.conflict is False
    assert result.log_entry is None


def test_slice0_yaml_default_host_admits_drug_b() -> None:
    host = _host()
    constraints = load_constraints(_SLICE0_CONSTRAINTS)
    result = evaluate(host, ["drug_a", "drug_b"], constraints)
    assert "drug_b" in result.admissible
    assert "drug_b" not in result.excluded
    assert result.conflict is False
    assert result.log_entry is None


def test_empty_preferred_drugs_is_not_conflict() -> None:
    host = _host(comorbidity={"cx_drug_a": True})
    constraints = ConstraintSet(
        hard=[Rule(id="cx_drug_a", kind="contraindication", drug_id="drug_a")],
    )
    result = evaluate(host, [], constraints)
    assert result.conflict is False
    assert result.admissible == []
    assert result.excluded == {}
    assert result.log_entry is None
