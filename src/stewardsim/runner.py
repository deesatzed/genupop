"""Fixture study runner (GOAL §7, design §3).

Reads study YAML plus structural fixtures only. No network I/O.
``start_run`` is called before ``simulate``.

Horizon conversion
------------------
``hosts.years`` becomes a discrete-day horizon by

    horizon = int(years * DAYS_PER_YEAR)

with ``DAYS_PER_YEAR = 365``. A study of 200 hosts × 1 year is therefore
200 hosts × 365 days. The same constant is recorded in the shape
``world.yaml`` as ``days_per_year``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from stewardsim.antibiogram import resistance_frequency
from stewardsim.feasibility import ConstraintSet
from stewardsim.host import Host
from stewardsim.importation import Importation
from stewardsim.params import Parameter
from stewardsim.pathogen import Determinant
from stewardsim.policy import AdherenceModel, Policy, point_value
from stewardsim.provenance import config_hash, start_run
from stewardsim.restriction import load_restriction_tape
from stewardsim.simulate import SimulateResult, simulate
from stewardsim.study import StudyConfig, load_study

DAYS_PER_YEAR = 365
_HEADLINES = frozenset({"rounds_to_effective", "mean_rounds_to_effective"})
_WORLD_NAME = "world.yaml"
_HOSTS_NAME = "hosts.yaml"

_LAST_RUN: StudyRun | None = None


@dataclass(frozen=True)
class ProvenanceReport:
    name: str
    parameters: tuple[Parameter, ...]


@dataclass(frozen=True)
class WorldSpec:
    citation: str
    days_per_year: int
    drugs: tuple[str, ...]
    policy: Policy
    adherence: AdherenceModel
    determinant: Determinant
    constraints: ConstraintSet
    s_max: Parameter
    p0: Parameter


@dataclass(frozen=True)
class StudyRun:
    study: str
    outdir: Path
    config_hash: str
    seed: int
    horizon: int
    result: SimulateResult
    parameters: tuple[Parameter, ...]

    def trace(self, name: str) -> ProvenanceReport:
        if name not in _HEADLINES:
            raise ValueError(f"unknown headline: {name}")
        return ProvenanceReport(name=name, parameters=self.parameters)


def horizon_days(years: float, *, days_per_year: int = DAYS_PER_YEAR) -> int:
    """Convert ``hosts.years`` to a discrete-day horizon.

    ``horizon = int(years * days_per_year)``. Slice-0 default is 365
    days per year, so ``years=1`` is 365 days.
    """
    return int(years * days_per_year)


def trace(name: str, run: StudyRun | None = None) -> ProvenanceReport:
    """List every Parameter that entered the named headline number."""
    target = run if run is not None else _LAST_RUN
    if target is None:
        raise RuntimeError("no study run to trace; call run_study first")
    return target.trace(name)


def _resolve(path: str | Path) -> Path:
    raw = Path(path)
    return raw if raw.is_absolute() else Path.cwd() / raw


def _require_tape(config: StudyConfig) -> Path:
    if config.kind != "retrodiction":
        raise ValueError(
            f"Slice-0 runner supports kind=retrodiction; got {config.kind!r}"
        )
    if not config.restriction_tape:
        raise ValueError("kind: retrodiction requires restriction_tape path")
    tape_path = _resolve(config.restriction_tape)
    if not tape_path.is_file():
        raise FileNotFoundError(f"restriction tape missing: {tape_path}")
    return tape_path


def _fixture_paths(tape_path: Path) -> tuple[Path, Path]:
    fixture_dir = tape_path.parent
    world_path = fixture_dir / _WORLD_NAME
    hosts_path = fixture_dir / _HOSTS_NAME
    if not world_path.is_file():
        raise FileNotFoundError(f"world fixture missing: {world_path}")
    if not hosts_path.is_file():
        raise FileNotFoundError(f"hosts fixture missing: {hosts_path}")
    return world_path, hosts_path


def _drug_ids(raw: Any) -> tuple[str, ...]:
    ids: list[str] = []
    if not isinstance(raw, list):
        raise ValueError("world.drugs must be a list")
    for item in raw:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict) and "id" in item:
            ids.append(str(item["id"]))
        else:
            raise ValueError(f"world.drugs entry must be an id or {{id: ...}}: {item!r}")
    return tuple(ids)


def _load_world(path: Path) -> WorldSpec:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"world fixture must be a mapping: {path}")
    days = data.get("days_per_year", DAYS_PER_YEAR)
    return WorldSpec(
        citation=str(data.get("citation", "")),
        days_per_year=int(days),
        drugs=_drug_ids(data.get("drugs", [])),
        policy=Policy.model_validate(data["policy"]),
        adherence=AdherenceModel.model_validate(data["adherence"]),
        determinant=Determinant.model_validate(data["determinant"]),
        constraints=ConstraintSet.model_validate(data["constraints"]),
        s_max=Parameter.model_validate(data["s_max"]),
        p0=_load_p0(data),
    )


def _load_p0(data: dict[str, Any]) -> Parameter:
    """Build p0. Optional ``p0_from_transcript`` overwrites the point value."""
    spec = data.get("p0")
    if not isinstance(spec, dict):
        raise ValueError("world.p0 must be a Parameter mapping")
    lookup = data.get("p0_from_transcript")
    if lookup is None:
        return Parameter.model_validate(spec)
    if not isinstance(lookup, dict):
        raise ValueError("world.p0_from_transcript must be a mapping")
    p0 = resistance_frequency(
        year=int(lookup["year"]),
        campus_id=str(lookup["campus_id"]),
        organism=str(lookup["organism"]),
        drug=str(lookup["drug"]),
    )
    body = dict(spec)
    dist = dict(body.get("distribution") or {})
    fitted = dict(dist.get("fitted_params") or {})
    fitted["value"] = p0
    dist["family"] = "point"
    dist["fitted_params"] = fitted
    body["distribution"] = dist
    return Parameter.model_validate(body)


def _build_hosts(path: Path, *, n: int) -> list[Host]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"hosts fixture must be a mapping: {path}")
    template = data.get("template", data)
    if not isinstance(template, dict):
        raise ValueError(f"hosts template must be a mapping: {path}")
    exposure = list(template.get("exposure_history") or [])
    demographics = dict(template.get("demographics") or {})
    comorbidity = dict(template.get("comorbidity") or {})
    admission_source = template.get("admission_source", "community")
    return [
        Host(
            id=index,
            exposure_history=list(exposure),
            demographics=dict(demographics),
            comorbidity=dict(comorbidity),
            admission_source=admission_source,
        )
        for index in range(1, n + 1)
    ]


def _collect_parameters(
    world: WorldSpec, importation: Importation | None = None
) -> tuple[Parameter, ...]:
    items: list[Parameter] = [
        world.policy.duration,
        world.adherence.baseline_fidelity,
        world.determinant.fitness_cost,
        world.s_max,
        world.p0,
    ]
    for name in sorted(world.adherence.deviation_drivers):
        items.append(world.adherence.deviation_drivers[name])
    if importation is not None:
        items.append(importation.rate)
        items.append(importation.source_correlation)
        for name in sorted(importation.determinant_mix):
            items.append(importation.determinant_mix[name])
    return tuple(sorted(items, key=lambda param: param.name))


def _write_results(run: StudyRun) -> None:
    payload = {
        "conflict_log": list(run.result.conflict_log),
        "determinant_trajectories": list(run.result.frequencies),
        "frequencies": list(run.result.frequencies),
        "mean_rounds_to_effective": run.result.mean_rounds_to_effective,
        "rounds_to_effective": run.result.rounds_to_effective,
    }
    (run.outdir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


def _write_provenance(run: StudyRun) -> None:
    report = run.trace("rounds_to_effective")
    lines = [
        "# PROVENANCE",
        "",
        f"study: {run.study}",
        f"config_hash: {run.config_hash}",
        f"seed: {run.seed}",
        f"horizon_days: {run.horizon}",
        f"days_per_year: {DAYS_PER_YEAR}",
        "",
        "Horizon conversion: horizon = int(years * DAYS_PER_YEAR)",
        f"with DAYS_PER_YEAR = {DAYS_PER_YEAR}.",
        "",
        "## rounds_to_effective",
        "",
        f"value: {run.result.rounds_to_effective}",
        "",
        "trace(rounds_to_effective) ->",
    ]
    for param in report.parameters:
        lines.append(f"- name: {param.name}")
        lines.append(f"  provenance: {param.provenance.value}")
        lines.append(f"  source: {param.source}")
    (run.outdir / "PROVENANCE.md").write_text("\n".join(lines) + "\n")


def run_study(config_path: str | Path, *, output_root: str | Path = "output") -> StudyRun:
    """Run a fixture retrodiction study and write the immutable output dir."""
    global _LAST_RUN
    config = load_study(config_path)
    tape_path = _require_tape(config)
    world_path, hosts_path = _fixture_paths(tape_path)
    digest = config_hash(config)
    outdir = Path(output_root) / config.study / digest
    ctx = start_run(config, seed=config.seed, outdir=outdir)
    world = _load_world(world_path)
    hosts = _build_hosts(hosts_path, n=config.hosts.n)
    horizon = horizon_days(config.hosts.years, days_per_year=world.days_per_year)
    rng = np.random.default_rng(config.seed)
    result = simulate(
        hosts,
        policy=world.policy,
        constraints=world.constraints,
        adherence=world.adherence,
        tape=load_restriction_tape(tape_path),
        determinant=world.determinant,
        p0=point_value(world.p0),
        horizon=horizon,
        rng=rng,
        s_max=point_value(world.s_max),
        importation=None,
    )
    run = StudyRun(
        study=config.study,
        outdir=ctx.outdir,
        config_hash=ctx.config_hash,
        seed=ctx.seed,
        horizon=horizon,
        result=result,
        parameters=_collect_parameters(world),
    )
    _write_results(run)
    _write_provenance(run)
    _LAST_RUN = run
    return run
