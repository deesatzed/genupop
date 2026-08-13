"""Transcript of parked Temple PDFs. Not AT-12."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived" / "antibiograms"
MANIFEST = DERIVED / "MANIFEST.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_transcript_is_not_an_at12_event() -> None:
    payload = json.loads((DERIVED / "tuh_main_transcript.json").read_text())
    assert payload["kind"] == "antibiogram_transcript"
    assert payload["not_at12"] is True
    assert not list((ROOT / "data" / "derived").glob("event_*/observed_series.json"))


def test_source_pdf_hashes_match_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for year, spec in manifest["sources"].items():
        path = ROOT / spec["path"]
        assert path.is_file(), year
        assert _sha(path) == spec["sha256"], year


def test_output_hashes_match_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for name in ("json", "csv"):
        path = ROOT / manifest["outputs"][name]["path"]
        assert _sha(path) == manifest["outputs"][name]["sha256"]


def test_spot_check_printed_cells() -> None:
    rows = list(csv.DictReader((DERIVED / "tuh_main_transcript.csv").open()))

    def one(year: str, organism: str, drug: str) -> dict:
        hits = [
            r
            for r in rows
            if r["year"] == year and r["organism"] == organism and r["drug"] == drug
        ]
        assert len(hits) == 1, (year, organism, drug, len(hits))
        return hits[0]

    ecoli_2017 = one("2017", "Escherichia coli", "ciprofloxacin")
    assert ecoli_2017["percent_susceptible"] == "70"
    assert ecoli_2017["n_isolates"] == "1255"
    assert ecoli_2017["campus_id"] == "TUH"

    ecoli_2024 = one("2024", "Escherichia coli", "ciprofloxacin")
    assert ecoli_2024["percent_susceptible"] == "60"
    assert ecoli_2024["campus_id"] == "TUH-Main"

    ecoli_2025 = one("2025", "Escherichia coli", "ciprofloxacin")
    assert ecoli_2025["percent_susceptible"] == "56"

    proteus_2017 = one("2017", "Proteus mirabilis", "meropenem")
    assert proteus_2017["flag"] == "ID"
    assert proteus_2017["percent_susceptible"] == ""

    pa_2025 = one("2025", "Pseudomonas aeruginosa", "ciprofloxacin")
    assert pa_2025["percent_susceptible"] == "68"
    assert pa_2025["n_isolates"] == "751"


def test_resistance_frequency_from_2025_ecoli_cipro() -> None:
    from stewardsim.antibiogram import resistance_frequency
    from stewardsim.policy import point_value
    from stewardsim.runner import _load_world

    p0 = resistance_frequency(
        year=2025,
        campus_id="TUH-Main",
        organism="Escherichia coli",
        drug="ciprofloxacin",
    )
    assert p0 == pytest.approx(1.0 - 56.0 / 100.0)
    world = _load_world(ROOT / "tests" / "fixtures" / "shape" / "world.yaml")
    assert world.p0.provenance.value == "registry"
    assert point_value(world.p0) == pytest.approx(p0)


def test_record_count_matches_payload() -> None:
    payload = json.loads((DERIVED / "tuh_main_transcript.json").read_text())
    csv_n = sum(1 for _ in csv.DictReader((DERIVED / "tuh_main_transcript.csv").open()))
    assert payload["n_records"] == csv_n == len(payload["records"])
    assert csv_n > 400
