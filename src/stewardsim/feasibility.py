"""Constraint / guideline-conflict oracle (GOAL §6.4, AT-13; ADR-003).

Mechanical only. No learned component, no RNG, no global mutation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from stewardsim.host import Host

RuleKind = Literal["allergy", "contraindication"]


class Rule(BaseModel):
    id: str
    kind: RuleKind
    drug_id: str

    model_config = ConfigDict(extra="forbid", frozen=True)


class ConstraintSet(BaseModel):
    hard: list[Rule]
    soft: list[Rule] = []
    sources: list[str] = []

    model_config = ConfigDict(extra="forbid", frozen=True)


class FeasibilityResult(BaseModel):
    admissible: list[str]
    excluded: dict[str, str]
    conflict: bool

    model_config = ConfigDict(extra="forbid", frozen=True)


def _allergies(host: Host) -> list[str]:
    raw = host.comorbidity.get("allergies")
    if raw is None:
        raw = host.demographics.get("allergies", [])
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def _hard_reason(host: Host, drug_id: str, rule: Rule) -> str | None:
    if rule.drug_id != drug_id:
        return None
    if rule.kind == "allergy":
        if drug_id in _allergies(host):
            return f"allergy:{rule.id}"
        return None
    if rule.kind == "contraindication":
        flag = host.comorbidity.get(rule.id)
        if flag is None or bool(flag):
            return f"contraindication:{rule.id}"
        return None
    return None


def evaluate(
    host: Host,
    preferred_drugs: list[str],
    constraints: ConstraintSet,
) -> FeasibilityResult:
    """Return admissible preferred drugs after hard constraints.

    ``preferred_drugs`` is the policy's ordered list. Conflict if hard
    constraints admit none of them. Soft rules are unused in Slice-0.
    """
    admissible: list[str] = []
    excluded: dict[str, str] = {}
    seen: set[str] = set()
    for drug_id in preferred_drugs:
        if drug_id in seen:
            continue
        seen.add(drug_id)
        reason: str | None = None
        for rule in constraints.hard:
            reason = _hard_reason(host, drug_id, rule)
            if reason is not None:
                break
        if reason is not None:
            excluded[drug_id] = reason
        else:
            admissible.append(drug_id)
    return FeasibilityResult(
        admissible=admissible,
        excluded=excluded,
        conflict=len(admissible) == 0,
    )


def load_constraints(path: str | Path) -> ConstraintSet:
    raw_path = Path(path)
    data = yaml.safe_load(raw_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"constraint set must be a mapping: {raw_path}")
    return ConstraintSet.model_validate(data)
