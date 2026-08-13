from pathlib import Path

import pytest
import yaml

from stewardsim.study import StudyConfig, load_study


def _write_yaml(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False))
    return path


def _retrodiction(**overrides: object) -> dict:
    data: dict = {
        "study": "slice0_shape",
        "kind": "retrodiction",
        "hosts": {"n": 200, "years": 1},
        "restriction_tape": "tests/fixtures/shape/restriction_tape.csv",
        "seed": 0,
        "outputs": ["rounds_to_effective", "determinant_trajectories"],
    }
    data.update(overrides)
    return data


def test_load_study_parses_kind_and_hosts(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path / "study.yaml", _retrodiction())
    cfg = load_study(path)
    assert cfg.study == "slice0_shape"
    assert cfg.kind == "retrodiction"
    assert cfg.hosts.n == 200
    assert cfg.hosts.years == 1.0
    assert cfg.restriction_tape == "tests/fixtures/shape/restriction_tape.csv"
    assert cfg.seed == 0
    assert cfg.outputs == ["rounds_to_effective", "determinant_trajectories"]


def test_genetic_limit_does_not_require_restriction_tape(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "limits.yaml",
        {
            "study": "genetic_limits",
            "kind": "genetic_limit",
            "hosts": {"n": 1, "years": 0.1},
            "seed": 7,
        },
    )
    cfg = load_study(path)
    assert cfg.kind == "genetic_limit"
    assert cfg.restriction_tape is None
    assert cfg.hosts.n == 1
    assert cfg.hosts.years == 0.1


def test_unknown_kind_raises(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path / "unknown.yaml", _retrodiction(kind="not_a_kind"))
    with pytest.raises(ValueError):
        load_study(path)


def test_projection_kind_raises(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path / "projection.yaml", _retrodiction(kind="projection"))
    with pytest.raises(ValueError):
        load_study(path)


def test_retrodiction_without_restriction_tape_raises(tmp_path: Path) -> None:
    data = _retrodiction()
    del data["restriction_tape"]
    path = _write_yaml(tmp_path / "no_tape.yaml", data)
    with pytest.raises(ValueError):
        load_study(path)


def test_retrodiction_without_restriction_tape_on_model_raises() -> None:
    with pytest.raises(ValueError):
        StudyConfig(
            study="slice0_shape",
            kind="retrodiction",
            hosts={"n": 200, "years": 1},
            seed=0,
        )


def test_bare_float_importation_raises(tmp_path: Path) -> None:
    path = tmp_path / "bare_import.yaml"
    path.write_text(
        """
study: slice0_shape
kind: retrodiction
hosts:
  n: 200
  years: 1
restriction_tape: tests/fixtures/shape/restriction_tape.csv
seed: 0
importation: 0.01
"""
    )
    with pytest.raises(ValueError):
        load_study(path)


def test_importation_mapping_accepted(tmp_path: Path) -> None:
    path = _write_yaml(
        tmp_path / "import_map.yaml",
        _retrodiction(
            importation={
                "rate": {
                    "name": "import_rate",
                    "provenance": "assumed",
                    "source": "test://shape",
                }
            }
        ),
    )
    cfg = load_study(path)
    assert isinstance(cfg.importation, dict)
    assert cfg.importation["rate"]["source"] == "test://shape"
