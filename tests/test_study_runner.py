"""Fixture study runner + CLI (GOAL §7, design §3, AT-8.1).

``stewardsim study configs/studies/slice0_shape.yaml`` writes
``output/slice0_shape/<config_hash>/{run_record.json,results.json,PROVENANCE.md}``.
``trace`` on ``rounds_to_effective`` (or ``mean_rounds_to_effective``)
lists every Parameter that entered the run.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
from pathlib import Path

import pytest
import yaml

from stewardsim import __version__
from stewardsim.cli import main
from stewardsim.params import Parameter, Provenance
from stewardsim.restriction import load_restriction_tape
from stewardsim.study import load_study

_STUDY_YAML = Path("configs/studies/slice0_shape.yaml")
_FIXTURE_DIR = Path("tests/fixtures/shape")
_TAPE = _FIXTURE_DIR / "restriction_tape.csv"
_WORLD = _FIXTURE_DIR / "world.yaml"
_HOSTS = _FIXTURE_DIR / "hosts.yaml"
_SRC = Path("src/stewardsim")
_TEST_SRC = Path("tests")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_PARAM_NAMES = (
    "policy.duration",
    "adherence.baseline_fidelity",
    "determinant.fitness_cost",
    "s_max",
    "p0",
)


def _fixture_texts() -> list[tuple[Path, str]]:
    return [
        (path, path.read_text())
        for path in sorted(_FIXTURE_DIR.rglob("*"))
        if path.is_file()
    ]


def _run_dir(root: Path, study: str = "slice0_shape") -> Path:
    study_root = root / study
    assert study_root.is_dir(), f"missing study directory {study_root}"
    runs = [path for path in study_root.iterdir() if path.is_dir()]
    assert len(runs) == 1, f"expected one run dir under {study_root}, got {runs}"
    return runs[0]


def _load_world() -> dict:
    data = yaml.safe_load(_WORLD.read_text())
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def shape_run(tmp_path_factory: pytest.TempPathFactory):
    from stewardsim.runner import run_study

    root = tmp_path_factory.mktemp("shape_study")
    return run_study(_STUDY_YAML, output_root=root)


def test_committed_study_yaml_matches_slice0_contract() -> None:
    assert _STUDY_YAML.is_file()
    cfg = load_study(_STUDY_YAML)
    assert cfg.study == "slice0_shape"
    assert cfg.kind == "retrodiction"
    assert cfg.hosts.n == 200
    assert cfg.hosts.years == 1.0
    assert cfg.restriction_tape == "tests/fixtures/shape/restriction_tape.csv"
    assert cfg.seed == 0
    assert cfg.outputs == [
        "rounds_to_effective",
        "determinant_trajectories",
        "conflict_log",
    ]


def test_fixtures_exist_hosts_drugs_tape_only() -> None:
    assert _TAPE.is_file()
    assert _WORLD.is_file()
    assert _HOSTS.is_file()
    names = {path.name for path in _FIXTURE_DIR.iterdir() if path.is_file()}
    assert "restriction_tape.csv" in names
    assert "world.yaml" in names
    assert "hosts.yaml" in names


def test_fixtures_cite_only_test_shape() -> None:
    found_citation = False
    for path, text in _fixture_texts():
        lower = text.lower()
        assert "doi:" not in lower, path
        assert "pubmed" not in lower, path
        assert "pmid" not in lower, path
        assert "http://" not in lower, path
        assert "https://" not in lower, path
        if "citation:" in lower:
            assert "test://shape" in text, path
            found_citation = True
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("citation:"):
                assert "test://shape" in stripped, (path, line)
            if stripped.startswith("source:") and "tuh_main_transcript" not in stripped:
                assert "test://shape" in stripped, (path, line)
    assert found_citation


def test_fixtures_have_no_event_files_or_observed_rates() -> None:
    event_root = "data/" + "derived/" + "event_"
    banned_tokens = (
        event_root,
        "mrsa",
        "vre",
        "klebsiella",
        "vancomycin",
        "observed_series",
    )
    for path, text in _fixture_texts():
        lower = text.lower()
        for token in banned_tokens:
            assert token not in lower, f"{token!r} in {path}"
        assert "event_" not in text, path


def test_tape_bans_A_after_T_with_exclusive_t1() -> None:
    tape = load_restriction_tape(_TAPE)
    assert tape.intervals
    interval = tape.intervals[0]
    assert interval.drug_id == "A"
    assert interval.t0 > 0
    assert interval.t1 > interval.t0
    t_ban = interval.t0
    assert tape.play(t_ban - 1) == frozenset()
    assert tape.play(t_ban) == frozenset({"A"})
    assert tape.play(interval.t1 - 1) == frozenset({"A"})
    assert tape.play(interval.t1) == frozenset()


def test_world_is_two_drugs_one_determinant_prefer_A() -> None:
    world = _load_world()
    drugs = world["drugs"]
    ids = [item["id"] if isinstance(item, dict) else item for item in drugs]
    assert ids == ["A", "B"]
    assert world["determinant"]["confers_resistance_to"] == ["A"]
    preferred = world["policy"]["rules"][0]["preferred"]
    assert preferred[0] == "A"
    assert "B" in preferred
    assert world["constraints"]["hard"] == []
    fidelity = world["adherence"]["baseline_fidelity"]
    assert fidelity["distribution"]["fitted_params"]["value"] == 1.0
    assert fidelity["provenance"] == "assumed"
    assert world["s_max"]["provenance"] == "assumed"
    assert world["p0"]["provenance"] == "registry"
    assert world["s_max"]["name"] == "s_max"
    assert world["p0"]["name"] == "p0"
    lookup = world["p0_from_transcript"]
    assert lookup["year"] == 2025
    assert lookup["campus_id"] == "TUH-Main"
    assert lookup["organism"] == "Escherichia coli"
    assert lookup["drug"] == "ciprofloxacin"
    assert world["days_per_year"] == 365


def test_run_study_writes_immutable_output_directory(shape_run) -> None:
    out = Path(shape_run.outdir)
    assert out.is_dir()
    assert out.parent.name == "slice0_shape"
    assert _SHA256_HEX.fullmatch(out.name)
    for name in ("run_record.json", "results.json", "PROVENANCE.md"):
        assert (out / name).is_file(), name
    record = json.loads((out / "run_record.json").read_text())
    assert record["config_hash"] == out.name
    assert record["seed"] == 0
    assert _SHA256_HEX.fullmatch(record["config_hash"])


def test_default_output_root_is_output() -> None:
    from stewardsim.runner import run_study

    default = inspect.signature(run_study).parameters["output_root"].default
    assert str(default) == "output"


def test_results_json_includes_rounds_to_effective(shape_run) -> None:
    payload = json.loads((shape_run.outdir / "results.json").read_text())
    assert "rounds_to_effective" in payload
    assert isinstance(payload["rounds_to_effective"], float)
    assert payload["rounds_to_effective"] == shape_run.result.rounds_to_effective
    trajectories = payload.get("determinant_trajectories", payload.get("frequencies"))
    assert isinstance(trajectories, list)
    assert len(trajectories) == 365
    assert payload["conflict_log"] == shape_run.result.conflict_log
    if "determinant_trajectories" in payload:
        assert payload["determinant_trajectories"] == shape_run.result.frequencies
    assert not any(str(key).startswith("event_") for key in payload)


def test_wired_fixtures_prefer_A_until_tape_bans_it(shape_run) -> None:
    tape = load_restriction_tape(_TAPE)
    t_ban = tape.intervals[0].t0
    dose_a = shape_run.result.dose_days["A"]
    assert dose_a[0] == 200.0
    assert dose_a[t_ban - 1] == 200.0
    assert dose_a[t_ban] == 0.0
    assert sum(dose_a[t_ban:]) == 0.0
    assert sum(shape_run.result.dose_days["B"][t_ban:]) == 200.0 * (365 - t_ban)


def test_trace_lists_every_parameter(shape_run) -> None:
    from stewardsim.runner import trace

    report = trace("rounds_to_effective")
    parameters = list(report.parameters)
    assert parameters
    names = [param.name for param in parameters]
    for required in REQUIRED_PARAM_NAMES:
        assert required in names, required
    for param in parameters:
        assert isinstance(param, Parameter)
        if param.name == "p0":
            assert param.provenance is Provenance.REGISTRY
            assert "tuh_main_transcript" in param.source
        else:
            assert param.provenance is Provenance.ASSUMED
            assert param.source == "test://shape"
    alias = trace("mean_rounds_to_effective")
    assert [param.name for param in alias.parameters] == names
    via_run = shape_run.trace("rounds_to_effective")
    assert [param.name for param in via_run.parameters] == names


def test_provenance_md_traces_rounds_to_effective(shape_run) -> None:
    text = (shape_run.outdir / "PROVENANCE.md").read_text()
    assert "rounds_to_effective" in text
    assert "trace" in text.lower()
    for name in REQUIRED_PARAM_NAMES:
        assert name in text
    assert "assumed" in text
    assert "test://shape" in text
    assert shape_run.outdir.name in text


def test_horizon_is_years_times_days_per_year(shape_run) -> None:
    from stewardsim.runner import DAYS_PER_YEAR, horizon_days

    cfg = load_study(_STUDY_YAML)
    assert DAYS_PER_YEAR == 365
    assert horizon_days(cfg.hosts.years) == int(cfg.hosts.years * DAYS_PER_YEAR)
    assert horizon_days(1) == 365
    assert len(shape_run.result.frequencies) == 365
    module = Path("src/stewardsim/runner.py").read_text()
    assert "DAYS_PER_YEAR" in module
    assert "365" in module
    assert "int(years" in module or "years *" in module


def test_retrodiction_missing_tape_file_raises(tmp_path: Path) -> None:
    from stewardsim.runner import run_study

    yaml_path = tmp_path / "missing_tape.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "study: missing_tape",
                "kind: retrodiction",
                "hosts: {n: 2, years: 1}",
                "restriction_tape: tests/fixtures/shape/does_not_exist.csv",
                "seed: 0",
                "",
            ]
        )
    )
    with pytest.raises((FileNotFoundError, ValueError), match="tape"):
        run_study(yaml_path, output_root=tmp_path / "out")
    invented = tmp_path / "out"
    if invented.exists():
        results = list(invented.rglob("results.json"))
        assert results == []


def test_second_run_refuses_to_overwrite(shape_run) -> None:
    from stewardsim.runner import run_study

    with pytest.raises(FileExistsError):
        run_study(_STUDY_YAML, output_root=shape_run.outdir.parent.parent)


def test_cli_no_args_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    main([])
    assert capsys.readouterr().out.strip() == __version__


def test_cli_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--version"])
    assert capsys.readouterr().out.strip() == __version__


def test_cli_study_writes_outputs(tmp_path: Path) -> None:
    main(
        [
            "study",
            str(_STUDY_YAML),
            "--output-root",
            str(tmp_path),
        ]
    )
    out = _run_dir(tmp_path)
    assert (out / "run_record.json").is_file()
    assert (out / "results.json").is_file()
    assert (out / "PROVENANCE.md").is_file()
    payload = json.loads((out / "results.json").read_text())
    assert "rounds_to_effective" in payload


def test_start_run_is_called_before_simulate() -> None:
    import stewardsim.runner as runner

    source = inspect.getsource(runner.run_study)
    start_at = source.index("start_run(")
    simulate_at = source.index("simulate(")
    assert start_at < simulate_at

    tree = ast.parse(source)

    class _Calls(ast.NodeVisitor):
        def __init__(self) -> None:
            self.names: list[str] = []

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            if isinstance(func, ast.Name):
                self.names.append(func.id)
            elif isinstance(func, ast.Attribute):
                self.names.append(func.attr)
            self.generic_visit(node)

    visitor = _Calls()
    visitor.visit(tree)
    assert "start_run" in visitor.names
    assert "simulate" in visitor.names
    assert visitor.names.index("start_run") < visitor.names.index("simulate")


def test_runner_and_cli_have_no_sockets() -> None:
    import stewardsim.runner as runner

    banned = ("socket", "urllib", "requests", "http.client", "httpx", "aiohttp")
    for path in (_SRC / "runner.py", _SRC / "cli.py"):
        text = path.read_text()
        tree = ast.parse(text)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
                imported.update(f"{module}.{alias.name}" for alias in node.names)
        for name in banned:
            assert name not in imported, f"{name} imported in {path}"
            assert name not in text, f"{name} in {path}"
    source = inspect.getsource(runner)
    assert "socket" not in source


def test_no_banned_framing() -> None:
    banned = (
        "inappropriate" + " prescribing",
        "prescriber" + " error",
        "mis" + "use",
        "compl" + "iance",
    )
    paths = [
        _SRC / "runner.py",
        _SRC / "cli.py",
        _TEST_SRC / "test_study_runner.py",
    ]
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text().lower()
        for phrase in banned:
            assert phrase not in text, f"{phrase!r} in {path}"
