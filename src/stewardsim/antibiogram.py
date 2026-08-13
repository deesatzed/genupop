"""Look up a printed antibiogram cell. Not an AT-12 event."""

from __future__ import annotations

import csv
from pathlib import Path

_TRANSCRIPT = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "derived"
    / "antibiograms"
    / "tuh_main_transcript.csv"
)


def resistance_frequency(
    *,
    year: int,
    campus_id: str,
    organism: str,
    drug: str,
    transcript: Path | None = None,
) -> float:
    """Return 1 - (percent susceptible)/100 for one printed cell.

    Raises if the cell is a flag (IR, INS, ID, ``-``, ``*``) or missing.
    """
    path = transcript if transcript is not None else _TRANSCRIPT
    if not path.is_file():
        raise FileNotFoundError(f"antibiogram transcript missing: {path}")
    hits: list[dict[str, str]] = []
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if (
                int(row["year"]) == year
                and row["campus_id"] == campus_id
                and row["organism"] == organism
                and row["drug"] == drug
            ):
                hits.append(row)
    if len(hits) != 1:
        raise ValueError(
            f"expected one transcript cell for {year} {campus_id} "
            f"{organism} {drug}; got {len(hits)}"
        )
    row = hits[0]
    if row["flag"]:
        raise ValueError(
            f"transcript cell is a flag, not a percent: {row['flag']}"
        )
    if row["percent_susceptible"] == "":
        raise ValueError("transcript cell has no percent_susceptible")
    susceptible = float(row["percent_susceptible"])
    if not 0.0 <= susceptible <= 100.0:
        raise ValueError(f"percent_susceptible out of range: {susceptible}")
    return 1.0 - susceptible / 100.0
