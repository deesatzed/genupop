"""Analytic-limit acceptance tests (GOAL.md §8): AT-1, AT-2, AT-3, AT-4, AT-7, AT-11."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pytest

from stewardsim.pathogen import (
    step_deterministic,
    step_recessive_diploid,
    step_wright_fisher,
)

_SLICE0_STUDY = Path("configs/studies/slice0_shape.yaml")
_SHAPE_FIXTURES = Path("tests/fixtures/shape")
_WALL_CLOCK_KEYS = frozenset(
    {
        "created_at",
        "datetime",
        "finished_at",
        "generated_at",
        "now",
        "started_at",
        "timestamp",
        "wall_clock",
    }
)


def _assert_no_wall_clock(obj: object) -> None:
    if isinstance(obj, dict):
        overlap = _WALL_CLOCK_KEYS.intersection(obj)
        assert not overlap, f"wall-clock keys in results.json: {sorted(overlap)}"
        for value in obj.values():
            _assert_no_wall_clock(value)
    elif isinstance(obj, list):
        for item in obj:
            _assert_no_wall_clock(item)


def test_at1_hardy_weinberg_neutral_frequency_constant() -> None:
    """AT-1: no selection / mutation / drift ⇒ frequency constant to < 1e-12."""
    p0 = 0.37
    p = p0
    for _ in range(1000):
        p = step_deterministic(p, s=0.0, mu=0.0, fitness_cost=0.0)
        assert abs(p - p0) < 1e-12


def test_at2_selection_mutation_balance() -> None:
    """AT-2: recessive diploid equilibrium converges to √(μ/s) within 1%.

    Carried AT-2 contract (diploid-recessive v1), not a claim that bacteria
    are diploid. Map: mutation then selection against the recessive
    homozygote, whose equilibrium is √(μ/s), not haploid μ/s.
    """
    mu = 1e-6
    s = 0.1
    expected = math.sqrt(mu / s)
    q = 0.0
    for _ in range(1_000_000):
        q_next = step_recessive_diploid(q, s=s, mu=mu)
        if abs(q_next - q) < 1e-18:
            q = q_next
            break
        q = q_next
    assert q == pytest.approx(expected, rel=0.01)


def test_at3_wright_fisher_drift_variance() -> None:
    """AT-3: Var(Δp) matches p(1-p)/(2N) within Monte Carlo error.

    Diploid Wright–Fisher: p' = Binomial(2N, p) / (2N). Fixed seed.
    Sample-variance SE for near-Gaussian Δp is σ² √(2/(n-1)); four SEs
    is a Monte Carlo envelope, not a loosened analytic tolerance.
    """
    rng = np.random.default_rng(20260812)
    p = 0.3
    n = 200
    n_rep = 20_000
    expected = p * (1.0 - p) / (2 * n)
    deltas = np.empty(n_rep)
    for i in range(n_rep):
        deltas[i] = step_wright_fisher(p, n, rng, s=0.0, mu=0.0) - p
    observed = float(np.var(deltas, ddof=1))
    se = expected * math.sqrt(2.0 / (n_rep - 1))
    assert abs(observed - expected) < 4.0 * se


def test_at4_selection_sweep_logistic() -> None:
    """AT-4: constant s ⇒ discrete logistic trajectory within 1e-6.

    Map: p' = p(1+s)/(1 + s p). Closed form:
    p_t = p0 (1+s)^t / (p0 (1+s)^t + (1-p0)).
    """
    s = 0.1
    p0 = 0.02
    p = p0
    for t in range(1, 81):
        p = step_deterministic(p, s=s, mu=0.0, fitness_cost=0.0)
        growth = (1.0 + s) ** t
        expected = p0 * growth / (p0 * growth + (1.0 - p0))
        assert p == pytest.approx(expected, abs=1e-6)


def test_at7_zero_fitness_cost_does_not_decline() -> None:
    """AT-7: withdraw selection, fitness_cost == 0 ⇒ frequency does not decline."""
    p = 0.05
    for _ in range(50):
        p = step_deterministic(p, s=0.2, mu=0.0, fitness_cost=0.0)
    assert p > 0.05
    withdrawn = p
    for _ in range(200):
        p = step_deterministic(p, s=0.0, mu=0.0, fitness_cost=0.0)
        assert p >= withdrawn - 1e-12


def test_at7_positive_cost_decline_bounded_by_fitness_cost() -> None:
    """AT-7: after s=0, per-generation decline is bounded above by fitness cost.

    Haploid cost map p' = p(1-c)/(1 - c p) gives decline
    c p (1-p)/(1 - c p) ≤ c. A sign error would raise costless (or costly)
    resistance after withdrawal.
    """
    cost = 0.08
    for p0 in (0.15, 0.5, 0.9):
        p = p0
        for _ in range(40):
            p_next = step_deterministic(p, s=0.0, mu=0.0, fitness_cost=cost)
            decline = p - p_next
            assert decline >= -1e-15
            assert decline <= cost
            p = p_next
        assert p < p0


def test_at11_two_runs_produce_identical_results_json(tmp_path: Path) -> None:
    """AT-11: identical (config_hash, seed) ⇒ bit-identical results.json."""
    from stewardsim.runner import run_study

    run_a = run_study(_SLICE0_STUDY, output_root=tmp_path / "run_a")
    run_b = run_study(_SLICE0_STUDY, output_root=tmp_path / "run_b")
    path_a = run_a.outdir / "results.json"
    path_b = run_b.outdir / "results.json"
    bytes_a = path_a.read_bytes()
    bytes_b = path_b.read_bytes()
    assert bytes_a
    assert hashlib.sha256(bytes_a).hexdigest() == hashlib.sha256(bytes_b).hexdigest()
    assert run_a.config_hash == run_b.config_hash
    assert run_a.outdir != run_b.outdir

    payload = json.loads(bytes_a)
    _assert_no_wall_clock(payload)
    canonical = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    assert bytes_a.decode("utf-8") == canonical


def test_at11_config_hash_changes_when_fixture_byte_flips(tmp_path: Path) -> None:
    """AT-11: fixture file bytes enter config_hash; one flipped byte must change it."""
    from stewardsim.provenance import config_hash, start_run
    from stewardsim.study import load_study

    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    for name in ("world.yaml", "hosts.yaml", "restriction_tape.csv"):
        shutil.copy(_SHAPE_FIXTURES / name, fixtures / name)

    study_yaml = tmp_path / "study.yaml"
    study_yaml.write_text(
        "\n".join(
            [
                "study: slice0_shape",
                "kind: retrodiction",
                "hosts: {n: 2, years: 1}",
                f"restriction_tape: {fixtures / 'restriction_tape.csv'}",
                "seed: 0",
                "",
            ]
        )
    )
    cfg = load_study(study_yaml)
    hash_before = config_hash(cfg)
    ctx_a = start_run(cfg, seed=0, outdir=tmp_path / "a")
    assert ctx_a.config_hash == hash_before

    world = fixtures / "world.yaml"
    raw = bytearray(world.read_bytes())
    marker = b"Discrete"
    idx = raw.find(marker)
    assert idx >= 0, "expected comment marker in world.yaml so the flip stays parse-irrelevant"
    raw[idx] ^= 0x01
    world.write_bytes(bytes(raw))
    assert (fixtures / "world.yaml").read_bytes() != (_SHAPE_FIXTURES / "world.yaml").read_bytes()

    hash_after = config_hash(cfg)
    assert hash_after != hash_before
    ctx_b = start_run(cfg, seed=0, outdir=tmp_path / "b")
    assert ctx_b.config_hash == hash_after
    assert ctx_b.config_hash != ctx_a.config_hash
