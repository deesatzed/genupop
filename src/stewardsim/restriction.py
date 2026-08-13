"""Forced restriction tape (design §2).

In-window drugs are reserve/inadmissible. The tape is an input: no RNG.
Windows are half-open on the discrete day clock: a drug is restricted on
day ``t`` iff ``t0 <= t < t1``. ``t0`` is inclusive and ``>= 0``; ``t1``
is exclusive and ``t1 >= t0``. An empty interval (``t1 == t0``) restricts
no days.
"""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_REQUIRED_COLUMNS = ("drug_id", "t0", "t1")


class RestrictionInterval(BaseModel):
    """One drug restricted on days ``[t0, t1)``."""

    drug_id: str
    t0: int
    t1: int

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("drug_id")
    @classmethod
    def _drug_id_nonempty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("drug_id must be non-empty")
        return stripped

    @field_validator("t0")
    @classmethod
    def _t0_nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("t0 must be >= 0")
        return value

    @model_validator(mode="after")
    def _t1_at_least_t0(self) -> RestrictionInterval:
        if self.t1 < self.t0:
            raise ValueError("t1 must be >= t0")
        return self


class ForcedRestriction(BaseModel):
    intervals: list[RestrictionInterval]

    model_config = ConfigDict(extra="forbid", frozen=True)

    def play(self, t: int) -> frozenset[str]:
        """Drug ids restricted at day ``t``. No RNG.

        Two plays of the same ``t`` are bit-identical (frozenset equality).
        """
        return frozenset(
            interval.drug_id
            for interval in self.intervals
            if interval.t0 <= t < interval.t1
        )


def load_restriction_tape(path: str | Path) -> ForcedRestriction:
    """Read a CSV tape with columns ``drug_id,t0,t1``.

    Extra columns are ignored. Empty rows are skipped. Missing required
    columns raise ``ValueError``. No observed antibiogram numbers are
    invented here — the file is the source of the intervals.
    """
    raw_path = Path(path)
    with raw_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"restriction tape has no header: {raw_path}")
        headers = [name.strip() for name in reader.fieldnames]
        missing = [col for col in _REQUIRED_COLUMNS if col not in headers]
        if missing:
            raise ValueError(
                f"restriction tape missing columns {missing}: {raw_path}"
            )
        # Re-bind so lookups use stripped names when the file has spaces.
        reader.fieldnames = headers
        intervals: list[RestrictionInterval] = []
        for row in reader:
            if row is None:
                continue
            drug_id = (row.get("drug_id") or "").strip()
            t0_raw = (row.get("t0") or "").strip()
            t1_raw = (row.get("t1") or "").strip()
            if not drug_id and not t0_raw and not t1_raw:
                continue
            intervals.append(
                RestrictionInterval(drug_id=drug_id, t0=int(t0_raw), t1=int(t1_raw))
            )
    return ForcedRestriction(intervals=intervals)
