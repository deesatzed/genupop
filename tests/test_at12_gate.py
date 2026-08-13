"""AT-12 plug-in gate (design §3).

Missing lock, tape, observed series, or cohort ⇒ BLOCK.
A fabricated observed series (mock / dummy / fake / placeholder in a
filename or value) ⇒ BLOCK. The gate never writes a results directory
and never invents an event or antibiogram.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from stewardsim.validate import validate_at12

_EVENT_ID = "plug"
_FABRICATED = ("mock", "dummy", "fake", "placeholder")
_README_PATHS = (
    Path("data/raw/README.md"),
    Path("data/derived/README.md"),
    Path("configs/locks/README.md"),
)
_ALLOWED_DIGIT_RUNS = frozenset(
    {
        "at12",
        "at-12",
        "at12_",
        "at12_<id>",
        "at12_<id>.yaml",
    }
)
_DEATH_RESISTANCE_COUNT = re.compile(
    r"(?i)(?:"
    r"(?:death|deaths|died|mortality|fatalit(?:y|ies)|excess)\W{0,24}\d+"
    r"|\d+\W{0,24}(?:death|deaths|died|mortality|fatalit(?:y|ies)|excess)"
    r"|(?:resist(?:ance|ant)?|antibiogram)\W{0,24}\d+"
    r"|\d+\W{0,24}(?:resist(?:ance|ant)?|antibiogram)"
    r")"
)


def _paths(root: Path, event_id: str) -> dict[str, Path]:
    derived = root / "data" / "derived" / f"event_{event_id}"
    return {
        "lock": root / "configs" / "locks" / f"at12_{event_id}.yaml",
        "tape": derived / "restriction_tape.csv",
        "observed_series": derived / "observed_series.json",
        "cohort": derived / "cohort.json",
    }


def _cited(citation: str) -> dict[str, str]:
    digest = hashlib.sha256(citation.encode("utf-8")).hexdigest()
    return {"citation": citation, "hash": digest}


def _write_tree(
    root: Path,
    event_id: str,
    *,
    skip: str | None = None,
    observed: dict | None = None,
    cohort: dict | None = None,
) -> dict[str, Path]:
    paths = _paths(root, event_id)
    for key, path in paths.items():
        if key == skip:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if key == "lock":
            path.write_text(f"event_id: {event_id}\n")
        elif key == "tape":
            path.write_text("drug_id,t0,t1\n")
        elif key == "observed_series":
            payload = observed if observed is not None else _cited("user-supplied")
            path.write_text(json.dumps(payload) + "\n")
        else:
            payload = cohort if cohort is not None else _cited("user-supplied-cohort")
            path.write_text(json.dumps(payload) + "\n")
    return paths


def test_missing_all_required_files_returns_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert validate_at12(_EVENT_ID) == "BLOCK"
    assert not Path("data").exists()
    assert not Path("output").exists()
    assert not Path("results").exists()


@pytest.mark.parametrize("missing", ["lock", "tape", "observed_series", "cohort"])
def test_missing_any_required_file_returns_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_tree(tmp_path, _EVENT_ID, skip=missing)
    assert validate_at12(_EVENT_ID) == "BLOCK"
    assert not Path("output").exists()
    assert not Path("results").exists()
    assert not _paths(tmp_path, _EVENT_ID)[missing].exists()


@pytest.mark.parametrize("token", list(_FABRICATED))
def test_fabricated_observed_series_filename_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    monkeypatch.chdir(tmp_path)
    event_id = f"{token}_series"
    _write_tree(tmp_path, event_id)
    assert validate_at12(event_id) == "BLOCK"
    assert not Path("output").exists()


@pytest.mark.parametrize("token", list(_FABRICATED))
def test_fabricated_observed_series_value_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    monkeypatch.chdir(tmp_path)
    observed = _cited("user-supplied")
    observed["label"] = token
    _write_tree(tmp_path, _EVENT_ID, observed=observed)
    assert validate_at12(_EVENT_ID) == "BLOCK"
    assert not Path("output").exists()


def test_observed_series_without_citation_or_hash_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_tree(tmp_path, _EVENT_ID, observed={"citation": "user-supplied"})
    assert validate_at12(_EVENT_ID) == "BLOCK"
    _write_tree(tmp_path, _EVENT_ID, observed={"hash": _cited("user-supplied")["hash"]})
    assert validate_at12(_EVENT_ID) == "BLOCK"
    _write_tree(tmp_path, _EVENT_ID, observed={})
    assert validate_at12(_EVENT_ID) == "BLOCK"


def test_cohort_without_citation_or_hash_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_tree(tmp_path, _EVENT_ID, cohort={"citation": "user-supplied-cohort"})
    assert validate_at12(_EVENT_ID) == "BLOCK"
    _write_tree(
        tmp_path,
        _EVENT_ID,
        cohort={"hash": _cited("user-supplied-cohort")["hash"]},
    )
    assert validate_at12(_EVENT_ID) == "BLOCK"


def test_ready_only_when_all_four_exist_with_citation_and_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_tree(tmp_path, _EVENT_ID)
    assert validate_at12(_EVENT_ID) == "READY"
    assert not Path("output").exists()
    assert not Path("results").exists()


def test_gate_never_writes_a_results_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    assert validate_at12(_EVENT_ID) == "BLOCK"
    after_block = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    assert after_block == before
    _write_tree(tmp_path, _EVENT_ID)
    after_write = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    assert validate_at12(_EVENT_ID) == "READY"
    after_ready = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    assert after_ready == after_write
    assert not any(part in {"output", "results"} for path in after_ready for part in path.parts)


def test_validate_module_does_not_write_or_use_network() -> None:
    path = Path("src/stewardsim/validate.py")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    for banned in (
        "mkdir",
        "write_text",
        "write_bytes",
        "output/",
        "results/",
        "socket",
        "urllib",
        "requests",
        "httpx",
        "aiohttp",
    ):
        assert banned not in lowered, banned


def test_readmes_name_required_artifacts() -> None:
    for path in _README_PATHS:
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8").strip()
    derived = Path("data/derived/README.md").read_text(encoding="utf-8")
    for name in ("restriction_tape.csv", "observed_series.json", "cohort.json"):
        assert name in derived, name
    assert "citation" in derived
    assert "hash" in derived
    locks = Path("configs/locks/README.md").read_text(encoding="utf-8")
    assert "at12_" in locks
    assert ".yaml" in locks


def test_readmes_contain_no_integer_death_or_resistance_counts() -> None:
    for path in _README_PATHS:
        text = path.read_text(encoding="utf-8")
        hit = _DEATH_RESISTANCE_COUNT.search(text)
        assert hit is None, f"{path}: {hit.group(0)!r}"
        for match in re.finditer(r"\d{2,}", text):
            start = max(0, match.start() - 8)
            end = min(len(text), match.end() + 12)
            window = text[start:end].lower()
            allowed = any(token in window for token in _ALLOWED_DIGIT_RUNS)
            assert allowed, f"{path}: digit run {match.group(0)!r} in {window!r}"


def test_repo_has_no_observed_series_or_invented_event() -> None:
    data = Path("data")
    if data.is_dir():
        assert list(data.rglob("observed_series.json")) == []
        assert list(data.rglob("cohort.json")) == []
        event_dirs = [
            path
            for path in data.rglob("*")
            if path.is_dir() and path.name.startswith("event_")
        ]
        assert event_dirs == []
    locks = Path("configs/locks")
    if locks.is_dir():
        assert list(locks.glob("at12_*.yaml")) == []
        assert list(locks.glob("at12_*.yml")) == []
