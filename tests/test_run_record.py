import json
import re
import subprocess
from importlib.metadata import version
from pathlib import Path

import pytest
import yaml

from stewardsim.params import DistributionSpec, Parameter, Provenance
from stewardsim.provenance import start_run
from stewardsim.study import StudyConfig, load_study

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

_STUDY_YAML = """\
study: slice0_shape
kind: retrodiction
hosts:
  n: 200
  years: 1
restriction_tape: tests/fixtures/shape/restriction_tape.csv
seed: 0
"""


def _config(**overrides: object) -> StudyConfig:
    data: dict = {
        "study": "slice0_shape",
        "kind": "retrodiction",
        "hosts": {"n": 200, "years": 1},
        "restriction_tape": "tests/fixtures/shape/restriction_tape.csv",
        "seed": 0,
    }
    data.update(overrides)
    return StudyConfig.model_validate(data)


def _read_record(outdir: Path) -> dict:
    path = outdir / "run_record.json"
    assert path.is_file(), f"run_record.json missing in {outdir}"
    payload = json.loads(path.read_text())
    assert isinstance(payload, dict)
    return payload


def test_start_run_writes_record_before_returning(tmp_path: Path) -> None:
    outdir = tmp_path / "nested" / "run"
    assert not outdir.exists()
    ctx = start_run(_config(), seed=42, outdir=outdir)
    record_path = outdir / "run_record.json"
    assert record_path.is_file()
    record = json.loads(record_path.read_text())
    assert ctx.config_hash == record["config_hash"]
    assert Path(ctx.outdir) == outdir
    assert ctx.seed == 42
    assert record["seed"] == 42


def test_run_record_contains_required_fields(tmp_path: Path) -> None:
    param = Parameter(
        name="import_rate",
        provenance=Provenance.ASSUMED,
        distribution=DistributionSpec(family="point", fitted_params={"value": 0.01}),
        source="test://shape",
    )
    ctx = start_run(
        _config(importation={"rate": param}),
        seed=7,
        outdir=tmp_path,
    )
    record = _read_record(tmp_path)
    assert _SHA256_HEX.fullmatch(record["config_hash"])
    assert record["config_hash"] == ctx.config_hash
    assert record["seed"] == 7
    assert "git_commit" in record
    assert "dirty" in record
    assert record["git_commit"] is None or isinstance(record["git_commit"], str)
    assert isinstance(record["dirty"], bool)
    assert record["git_commit"] or record["dirty"] is True

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    porcelain = subprocess.check_output(
        ["git", "status", "--porcelain"], text=True
    )
    if record["git_commit"] is not None:
        assert record["git_commit"] == head
    if porcelain.strip():
        assert record["dirty"] is True
    else:
        assert record["dirty"] is False
        assert record["git_commit"] == head

    deps = record["dependency_versions"]
    assert isinstance(deps, dict)
    for name in ("stewardsim", "numpy", "scipy", "pydantic", "pyyaml"):
        assert deps[name] == version(name)


def test_config_hash_changes_when_one_yaml_byte_changes(tmp_path: Path) -> None:
    original = tmp_path / "original.yaml"
    flipped = tmp_path / "flipped.yaml"
    original.write_text(_STUDY_YAML)
    assert _STUDY_YAML[(_STUDY_YAML.index("n: 20") + 4)] == "0"
    flipped.write_text(_STUDY_YAML.replace("n: 200", "n: 201", 1))
    assert original.read_bytes() != flipped.read_bytes()
    assert len(original.read_bytes()) == len(flipped.read_bytes())

    loaded_original = yaml.safe_load(original.read_text())
    loaded_flipped = yaml.safe_load(flipped.read_text())
    assert loaded_original["hosts"]["n"] == 200
    assert loaded_flipped["hosts"]["n"] == 201

    ctx_a = start_run(load_study(original), seed=0, outdir=tmp_path / "a")
    ctx_b = start_run(load_study(flipped), seed=0, outdir=tmp_path / "b")
    assert ctx_a.config_hash != ctx_b.config_hash
    assert _read_record(tmp_path / "a")["config_hash"] == ctx_a.config_hash
    assert _read_record(tmp_path / "b")["config_hash"] == ctx_b.config_hash


def test_start_run_does_not_overwrite_existing_record(tmp_path: Path) -> None:
    first = start_run(_config(), seed=0, outdir=tmp_path)
    original = (tmp_path / "run_record.json").read_text()
    with pytest.raises(FileExistsError):
        start_run(_config(study="other"), seed=1, outdir=tmp_path)
    assert (tmp_path / "run_record.json").read_text() == original
    assert json.loads(original)["config_hash"] == first.config_hash
    assert json.loads(original)["seed"] == 0
