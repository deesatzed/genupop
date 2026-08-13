"""Reporting + AT gate (GOAL §8, §11; design §4).

``stewardsim odd`` / ``stewardsim trace`` list every registered
``Parameter.name``. Last-run names win when a run exists; otherwise the
skeletons come from live type registries and loadable fixture Parameters.

``stewardsim validate`` writes ``output/at_gate.json``. AT-5 stays
``not_run`` in Slice-0. ``stewardsim report`` refuses Tier 2/3 while
AT-5 is not green. Fixture directories are software proof, not a paper
result. No invented AT-12 numbers. No sockets. No fabricated series.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, get_args, get_origin

import pytest
import yaml

from stewardsim.cli import main
from stewardsim.importation import Importation
from stewardsim.params import DistributionSpec, Parameter, Provenance
from stewardsim.pathogen import Determinant
from stewardsim.policy import AdherenceModel, Policy

_SRC = Path("src/stewardsim")
_FIXTURE_WORLD = Path("tests/fixtures/shape/world.yaml")
_GREEN = (
    "AT-1",
    "AT-2",
    "AT-3",
    "AT-4",
    "AT-7",
    "AT-8.1",
    "AT-8.2",
    "AT-11",
    "AT-13.2",
    "AT-14",
)
_NOT_RUN_OR_BLOCK = (
    "AT-5",
    "AT-6",
    "AT-8.3",
    "AT-9",
    "AT-10",
    "AT-12",
    "AT-13",
    "AT-13.1",
)
_REGISTRY_TYPES = (Policy, AdherenceModel, Determinant, Importation)
_BANNED_NET = (
    "socket",
    "urllib",
    "requests",
    "http.client",
    "httpx",
    "aiohttp",
)


def _point(name: str) -> Parameter:
    return Parameter(
        name=name,
        provenance=Provenance.ASSUMED,
        distribution=DistributionSpec(family="point", fitted_params={"value": 0.0}),
        source="test://shape",
    )


def _mentions_parameter(annotation: Any) -> bool:
    if annotation is Parameter:
        return True
    origin = get_origin(annotation)
    if origin is None:
        return False
    return any(_mentions_parameter(arg) for arg in get_args(annotation))


def _type_parameter_fields() -> list[str]:
    names: list[str] = []
    for model in _REGISTRY_TYPES:
        for field_name, field in model.model_fields.items():
            if _mentions_parameter(field.annotation):
                names.append(field_name)
    return names


def _walk_parameter_names(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        if (
            isinstance(obj.get("name"), str)
            and "provenance" in obj
            and "distribution" in obj
        ):
            found.append(obj["name"])
        for value in obj.values():
            found.extend(_walk_parameter_names(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk_parameter_names(item))
    return found


def _fixture_parameter_names() -> list[str]:
    data = yaml.safe_load(_FIXTURE_WORLD.read_text(encoding="utf-8"))
    return _walk_parameter_names(data)


def _exit_nonzero(exc: SystemExit) -> bool:
    code = exc.code
    if code is None:
        return False
    if isinstance(code, int):
        return code != 0
    return True


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.add(module)
            imported.update(f"{module}.{alias.name}" for alias in node.names)
    return imported


@pytest.fixture
def no_last_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import stewardsim.runner as runner

    monkeypatch.setattr(runner, "_LAST_RUN", None)


def test_cli_odd_and_trace_include_last_run_parameter_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from stewardsim.runner import StudyRun
    from stewardsim.simulate import SimulateResult

    unique = "unique_last_run_param_xyzzy"
    run = StudyRun(
        study="reporting_last_run",
        outdir=tmp_path,
        config_hash="0" * 64,
        seed=0,
        horizon=1,
        result=SimulateResult(
            frequencies=[0.1],
            rounds_to_effective=1.0,
            conflict_log=[],
            dose_days={"A": [1.0]},
        ),
        parameters=(
            _point("policy.duration"),
            _point("adherence.baseline_fidelity"),
            _point("determinant.fitness_cost"),
            _point("s_max"),
            _point("p0"),
            _point(unique),
        ),
    )
    import stewardsim.runner as runner

    monkeypatch.setattr(runner, "_LAST_RUN", run)
    for command in ("odd", "trace"):
        main([command])
        out = capsys.readouterr().out
        for param in run.parameters:
            assert param.name in out, f"{command} missing {param.name}"


def test_cli_odd_and_trace_skeletons_use_live_registries_without_last_run(
    no_last_run: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    type_fields = _type_parameter_fields()
    fixture_names = _fixture_parameter_names()
    assert type_fields
    assert fixture_names
    assert "duration" in type_fields
    assert "rate" in type_fields
    assert "s_max" in fixture_names
    monkeypatch.chdir(tmp_path)

    for command in ("odd", "trace"):
        main([command])
        out = capsys.readouterr().out
        assert out.strip(), f"{command} produced empty output"
        for name in type_fields:
            assert name in out, f"{command} missing type field {name}"
        for name in fixture_names:
            assert name in out, f"{command} missing fixture Parameter {name}"


def test_added_code_parameter_changes_collector() -> None:
    from pydantic import BaseModel

    from stewardsim.reporting import parameter_field_names

    class Probe(BaseModel):
        unique_reporting_probe_param: Parameter

    assert "unique_reporting_probe_param" in parameter_field_names(Probe)


def test_added_fixture_parameter_changes_collector() -> None:
    from stewardsim.reporting import parameter_names_from_mapping

    payload = {
        "extra": {
            "name": "unique_fixture_probe_param",
            "provenance": "assumed",
            "source": "test://shape",
            "distribution": {"family": "point", "fitted_params": {"value": 0.0}},
        }
    }
    assert "unique_fixture_probe_param" in parameter_names_from_mapping(payload)


def test_reporting_module_reads_live_type_and_fixture_registries() -> None:
    path = _SRC / "reporting.py"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    for token in (
        "Policy",
        "AdherenceModel",
        "Determinant",
        "Importation",
        "model_fields",
        "world.yaml",
    ):
        assert token in text, token


def test_validate_writes_at_gate_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["validate"])
    path = Path("output/at_gate.json")
    assert path.is_file()
    gate = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(gate, dict)
    for at_id in (*_GREEN, *_NOT_RUN_OR_BLOCK):
        assert at_id in gate, at_id


def test_at_gate_marks_slice0_not_run_or_block_and_known_green(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["validate"])
    gate = json.loads(Path("output/at_gate.json").read_text(encoding="utf-8"))
    for at_id in _GREEN:
        assert gate[at_id] == "pass", at_id
    for at_id in _NOT_RUN_OR_BLOCK:
        assert gate[at_id] in {"not_run", "BLOCK"}, at_id
    assert gate["AT-5"] != "pass"
    assert gate["AT-13.1"] == "not_run"
    assert gate["AT-13"] != "pass"
    assert gate["AT-12"] in {"not_run", "BLOCK"}
    assert not isinstance(gate["AT-12"], (int, float))


def test_report_refuses_tier_2_and_3_while_at5_not_green(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["validate"])
    for argv in (["report"], ["report", "--tier", "2"], ["report", "--tier", "3"]):
        with pytest.raises(SystemExit) as excinfo:
            main(argv)
        assert _exit_nonzero(excinfo.value), argv
        err = capsys.readouterr().err
        assert "AT-5" in err, argv
        lowered = err.lower()
        assert "tier" in lowered, argv
        assert "paper" in lowered or "not a paper" in lowered, argv


def test_report_does_not_invent_at12_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["validate"])
    gate = json.loads(Path("output/at_gate.json").read_text(encoding="utf-8"))
    assert gate["AT-12"] in {"not_run", "BLOCK"}
    with pytest.raises(SystemExit):
        main(["report"])
    err = capsys.readouterr().err
    assert "AT-12" not in err or "BLOCK" in err or "not_run" in err
    for token in ("mock", "dummy", "fake", "placeholder"):
        assert token not in err.lower()


def test_reporting_and_cli_have_no_sockets() -> None:
    paths = [_SRC / "reporting.py", _SRC / "cli.py", _SRC / "validate.py"]
    for path in paths:
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        imported = _imported_modules(path)
        for name in _BANNED_NET:
            assert name not in imported, f"{name} imported in {path}"
            assert name not in text, f"{name} in {path}"


def test_no_banned_framing_in_reporting() -> None:
    banned = (
        "inappropriate" + " prescribing",
        "prescriber" + " error",
        "mis" + "use",
        "compl" + "iance",
    )
    paths = [
        _SRC / "reporting.py",
        _SRC / "validate.py",
        _SRC / "cli.py",
        Path("tests/test_reporting.py"),
    ]
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for phrase in banned:
            assert phrase not in text, f"{phrase!r} in {path}"
