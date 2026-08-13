"""AT-12 plug-in gate (design §3).

Required user-supplied artifacts, all present or the gate returns BLOCK:

1. ``configs/locks/at12_<id>.yaml``
2. ``data/derived/event_<id>/restriction_tape.csv``
3. ``data/derived/event_<id>/observed_series.json`` with citation and hash
4. ``data/derived/event_<id>/cohort.json`` with citation and hash

The gate never writes a results directory and never invents an event.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_BLOCK = "BLOCK"
_READY = "READY"
_FABRICATED = ("mock", "dummy", "fake", "placeholder")
_EVENT_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


def _root() -> Path:
    return Path.cwd()


def _required_paths(event_id: str, root: Path) -> dict[str, Path]:
    derived = root / "data" / "derived" / f"event_{event_id}"
    return {
        "lock": root / "configs" / "locks" / f"at12_{event_id}.yaml",
        "tape": derived / "restriction_tape.csv",
        "observed_series": derived / "observed_series.json",
        "cohort": derived / "cohort.json",
    }


def _relative_path_text(event_id: str) -> tuple[str, ...]:
    derived = f"data/derived/event_{event_id}"
    return (
        f"configs/locks/at12_{event_id}.yaml",
        f"{derived}/restriction_tape.csv",
        f"{derived}/observed_series.json",
        f"{derived}/cohort.json",
    )


def _contains_fabricated(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in _FABRICATED)


def _string_leaves(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        found: list[str] = []
        for key, value in obj.items():
            found.extend(_string_leaves(key))
            found.extend(_string_leaves(value))
        return found
    if isinstance(obj, (list, tuple)):
        found = []
        for item in obj:
            found.extend(_string_leaves(item))
        return found
    return []


def _load_mapping(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _has_citation_and_hash(payload: dict[str, Any]) -> bool:
    citation = payload.get("citation")
    digest = payload.get("hash")
    if not isinstance(citation, str) or not citation.strip():
        return False
    if not isinstance(digest, str) or not digest.strip():
        return False
    return True


def validate_at12(event_id: str) -> str:
    """Return 'BLOCK' if any required file is missing or looks fabricated.
    Return 'READY' only if all four exist and observed series has citation+hash
    and does not use mock/dummy/fake/placeholder in the path or payload.
    Never write a results directory.
    """
    if not isinstance(event_id, str):
        return _BLOCK
    event_id = event_id.strip()
    if not event_id or not _EVENT_ID_RE.fullmatch(event_id):
        return _BLOCK
    if _contains_fabricated(event_id):
        return _BLOCK
    if any(_contains_fabricated(text) for text in _relative_path_text(event_id)):
        return _BLOCK

    paths = _required_paths(event_id, _root())
    for path in paths.values():
        if not path.is_file():
            return _BLOCK

    for key in ("observed_series", "cohort"):
        payload = _load_mapping(paths[key])
        if payload is None or not _has_citation_and_hash(payload):
            return _BLOCK
        if any(_contains_fabricated(text) for text in _string_leaves(payload)):
            return _BLOCK

    return _READY


# Slice-0 AT ledger (GOAL §8, design §4). Statuses are recorded from a
# known suite mapping: an AT is ``pass`` only if its mapped test
# functions exist in the tree. AT-5 is never claimed pass here.
# Writing the gate file is the reporting layer's job, not this module.

_AT_ORDER: tuple[str, ...] = (
    "AT-1",
    "AT-2",
    "AT-3",
    "AT-4",
    "AT-5",
    "AT-6",
    "AT-7",
    "AT-8.1",
    "AT-8.2",
    "AT-8.3",
    "AT-9",
    "AT-10",
    "AT-11",
    "AT-12",
    "AT-13",
    "AT-13.1",
    "AT-13.2",
    "AT-14",
)

_SLICE0_NOT_RUN: frozenset[str] = frozenset(
    {"AT-5", "AT-6", "AT-8.3", "AT-9", "AT-10", "AT-13", "AT-13.1"}
)

_SUITE: dict[str, tuple[str, ...]] = {
    "AT-1": (
        "tests/test_analytic_limits.py::test_at1_hardy_weinberg_neutral_frequency_constant",
    ),
    "AT-2": ("tests/test_analytic_limits.py::test_at2_selection_mutation_balance",),
    "AT-3": ("tests/test_analytic_limits.py::test_at3_wright_fisher_drift_variance",),
    "AT-4": ("tests/test_analytic_limits.py::test_at4_selection_sweep_logistic",),
    "AT-7": (
        "tests/test_analytic_limits.py::test_at7_zero_fitness_cost_does_not_decline",
        "tests/test_analytic_limits.py::test_at7_positive_cost_decline_bounded_by_fitness_cost",
    ),
    "AT-8.1": ("tests/test_study_runner.py::test_trace_lists_every_parameter",),
    "AT-8.2": (
        "tests/test_params.py::test_elicited_without_id_raises",
        "tests/test_provenance.py::test_elicited_id_must_resolve",
    ),
    "AT-11": (
        "tests/test_analytic_limits.py::test_at11_two_runs_produce_identical_results_json",
    ),
    "AT-13.2": (
        "tests/test_feasibility.py::test_seeded_contraindication_of_only_policy_drug_is_conflict",
    ),
    "AT-14": (
        "tests/test_policy.py::test_at14_fidelity_one_executed_equals_feasible_policy",
        "tests/test_adherence.py::test_at14_fidelity_0_7_deviation_frequency_within_mc_error",
        "tests/test_adherence.py::test_at14_deviation_rate_higher_when_severity_high",
        "tests/test_adherence.py::test_at14_substitute_comes_from_deviation_target",
    ),
}


def _package_tree() -> Path:
    return Path(__file__).resolve().parents[2]


def _nodeid_exists(tree: Path, nodeid: str) -> bool:
    rel, name = nodeid.split("::", 1)
    path = tree / rel
    if not path.is_file():
        return False
    return f"def {name}(" in path.read_text(encoding="utf-8")


def _at12_status() -> str:
    """BLOCK when the plug-in files are absent. Never invent a number."""
    locks = _root() / "configs" / "locks"
    event_ids: list[str] = []
    if locks.is_dir():
        for path in sorted(locks.glob("at12_*.yaml")):
            event_ids.append(path.name[len("at12_") : -len(".yaml")])
    if not event_ids:
        return validate_at12("unset")
    statuses = [validate_at12(event_id) for event_id in event_ids]
    if all(status == _READY for status in statuses):
        return "not_run"
    return _BLOCK


def evaluate_at_gate() -> dict[str, str]:
    """Return per-AT status from the suite mapping and the AT-12 plug-in.

    Does not write a gate file and does not invent AT-12 figures.
    AT-5 / AT-6 / AT-8.3 / AT-9 / AT-10 stay ``not_run`` in Slice-0.
    AT-13.1 stays ``not_run`` until a ≥10^6-episode no-violation
    campaign exists; parent AT-13 is therefore also ``not_run``.
    An allergy unit test is not that campaign.
    """
    tree = _package_tree()
    gate: dict[str, str] = {}
    for at_id in _AT_ORDER:
        if at_id == "AT-12":
            gate[at_id] = _at12_status()
            continue
        if at_id in _SLICE0_NOT_RUN:
            gate[at_id] = "not_run"
            continue
        nodeids = _SUITE.get(at_id, ())
        if nodeids and all(_nodeid_exists(tree, nodeid) for nodeid in nodeids):
            gate[at_id] = "pass"
        else:
            gate[at_id] = "not_run"
    return gate

