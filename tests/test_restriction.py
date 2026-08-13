"""ForcedRestriction tape: deterministic, no RNG (GOAL §4.7 seam, design §2).

In-window drugs are reserve/inadmissible. Windows are half-open [t0, t1).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

from stewardsim.restriction import (
    ForcedRestriction,
    RestrictionInterval,
    load_restriction_tape,
)


def _interval(drug_id: str, t0: int, t1: int) -> RestrictionInterval:
    return RestrictionInterval(drug_id=drug_id, t0=t0, t1=t1)


def test_play_returns_frozen_drug_ids() -> None:
    tape = ForcedRestriction(
        intervals=[
            _interval("drug_a", 10, 20),
            _interval("drug_b", 15, 25),
        ]
    )
    result = tape.play(15)
    assert isinstance(result, frozenset)
    assert result == frozenset({"drug_a", "drug_b"})
    assert tape.play(10) == frozenset({"drug_a"})
    assert tape.play(19) == frozenset({"drug_a", "drug_b"})
    # t1 is exclusive: day 20 is outside drug_a's window
    assert tape.play(20) == frozenset({"drug_b"})
    assert tape.play(9) == frozenset()
    assert tape.play(25) == frozenset()


def test_two_plays_of_same_t_are_bit_identical() -> None:
    tape = ForcedRestriction(
        intervals=[
            _interval("drug_a", 0, 30),
            _interval("drug_c", 12, 18),
            _interval("drug_a", 10, 40),
        ]
    )
    first = tape.play(12)
    second = tape.play(12)
    assert first == second
    assert hash(first) == hash(second)
    assert first == frozenset({"drug_a", "drug_c"})
    # overlapping windows for the same drug collapse to one id
    assert len(first) == 2


def test_empty_tape_restricts_nothing() -> None:
    tape = ForcedRestriction(intervals=[])
    assert tape.play(0) == frozenset()
    assert tape.play(100) == frozenset()


def test_empty_interval_restricts_no_day() -> None:
    tape = ForcedRestriction(intervals=[_interval("drug_a", 5, 5)])
    assert tape.play(4) == frozenset()
    assert tape.play(5) == frozenset()
    assert tape.play(6) == frozenset()


def test_t0_inclusive_t1_exclusive() -> None:
    tape = ForcedRestriction(intervals=[_interval("drug_a", 3, 6)])
    assert tape.play(2) == frozenset()
    assert tape.play(3) == frozenset({"drug_a"})
    assert tape.play(5) == frozenset({"drug_a"})
    assert tape.play(6) == frozenset()


def test_t0_must_be_nonnegative() -> None:
    with pytest.raises(ValidationError):
        RestrictionInterval(drug_id="drug_a", t0=-1, t1=5)


def test_t1_must_be_at_least_t0() -> None:
    with pytest.raises(ValidationError):
        RestrictionInterval(drug_id="drug_a", t0=10, t1=9)


def test_t1_equal_t0_is_legal() -> None:
    interval = RestrictionInterval(drug_id="drug_a", t0=4, t1=4)
    assert interval.t0 == 4
    assert interval.t1 == 4


def test_restriction_types_are_frozen_and_forbid_extra() -> None:
    interval = _interval("drug_a", 0, 10)
    tape = ForcedRestriction(intervals=[interval])
    with pytest.raises(ValidationError):
        RestrictionInterval(drug_id="drug_a", t0=0, t1=1, invented=True)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ForcedRestriction(intervals=[], extra=True)  # type: ignore[call-arg]
    with pytest.raises((ValidationError, TypeError)):
        interval.drug_id = "drug_z"  # type: ignore[misc]
    with pytest.raises((ValidationError, TypeError)):
        tape.intervals = []  # type: ignore[misc]


def test_restriction_module_does_not_import_numpy_random() -> None:
    import stewardsim.restriction as restriction

    source = inspect.getsource(restriction)
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
    assert "np.random" not in source
    assert "default_rng" not in source
    assert "Generator" not in source


def test_load_restriction_tape_from_csv(tmp_path: Path) -> None:
    path = tmp_path / "restriction_tape.csv"
    path.write_text("drug_id,t0,t1\ndrug_a,10,20\ndrug_b,0,5\n")
    tape = load_restriction_tape(path)
    assert isinstance(tape, ForcedRestriction)
    assert tape.play(12) == frozenset({"drug_a"})
    assert tape.play(3) == frozenset({"drug_b"})
    assert tape.play(10) == frozenset({"drug_a"})
    assert tape.play(20) == frozenset()
    assert tape.play(5) == frozenset()
    assert tape.play(30) == frozenset()


def test_load_restriction_tape_header_only_is_empty(tmp_path: Path) -> None:
    path = tmp_path / "empty_tape.csv"
    path.write_text("drug_id,t0,t1\n")
    tape = load_restriction_tape(path)
    assert tape.intervals == []
    assert tape.play(0) == frozenset()


def test_load_restriction_tape_missing_columns_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad_tape.csv"
    path.write_text("drug,start,end\ndrug_a,0,10\n")
    with pytest.raises(ValueError):
        load_restriction_tape(path)
