"""Append-only run record and config hash (Slice-0)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from stewardsim.study import StudyConfig

_TRACKED_DISTS = ("stewardsim", "numpy", "scipy", "pydantic", "pyyaml")
_WORLD_NAME = "world.yaml"
_HOSTS_NAME = "hosts.yaml"


@dataclass(frozen=True)
class RunContext:
    config_hash: str
    outdir: Path
    seed: int


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return _jsonable(obj.model_dump(mode="json"))
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(item) for item in obj]
    return obj


def _resolve_path(path: str | Path) -> Path:
    raw = Path(path)
    return raw if raw.is_absolute() else Path.cwd() / raw


def _existing_fixture_files(config: StudyConfig) -> list[Path]:
    """Return existing fixture files in hash order: world, hosts, tape.

    ``genetic_limit`` studies have no tape; only files that exist are hashed.
    """
    found: list[Path] = []
    if not config.restriction_tape:
        return found
    tape = _resolve_path(config.restriction_tape)
    fixture_dir = tape.parent
    for name in (_WORLD_NAME, _HOSTS_NAME):
        candidate = fixture_dir / name
        if candidate.is_file():
            found.append(candidate)
    if tape.is_file():
        found.append(tape)
    return found


def _canonical_study_json(config: StudyConfig) -> str:
    return json.dumps(_jsonable(config), sort_keys=True, default=str)


def config_hash(config: StudyConfig) -> str:
    """SHA-256 of canonical study JSON plus fixture file digests.

    Identity is::

        sha256(canonical_study_json || sha256(world.yaml)
               || sha256(hosts.yaml) || sha256(tape.csv))

    Fixture hashes are over raw file bytes. Missing files (for example a
    ``genetic_limit`` study with no tape) are omitted. ``git_commit``,
    ``dirty``, and ``dependency_versions`` are not part of this digest.
    """
    hasher = hashlib.sha256()
    hasher.update(_canonical_study_json(config).encode("utf-8"))
    for path in _existing_fixture_files(config):
        hasher.update(hashlib.sha256(path.read_bytes()).digest())
    return hasher.hexdigest()


def _config_hash(config: StudyConfig) -> str:
    return config_hash(config)


def _git_state() -> tuple[str | None, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    if not commit:
        commit = None
    try:
        porcelain = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        dirty = bool(porcelain.strip())
    except (OSError, subprocess.CalledProcessError):
        dirty = True
    return commit, dirty


def _dependency_versions() -> dict[str, str]:
    return {name: version(name) for name in _TRACKED_DISTS}


def start_run(config: StudyConfig, seed: int, outdir: str | Path) -> RunContext:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    record_path = out / "run_record.json"
    if record_path.exists():
        raise FileExistsError(f"run_record.json already exists: {record_path}")

    digest = _config_hash(config)
    git_commit, dirty = _git_state()
    record = {
        "config_hash": digest,
        "seed": int(seed),
        "git_commit": git_commit,
        "dirty": dirty,
        "dependency_versions": _dependency_versions(),
    }
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return RunContext(config_hash=digest, outdir=out, seed=int(seed))
