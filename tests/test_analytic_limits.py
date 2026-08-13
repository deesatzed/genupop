"""Analytic-limit acceptance tests (GOAL.md §8): AT-1, AT-2, AT-3, AT-4, AT-7."""

from __future__ import annotations

import math

import numpy as np
import pytest

from stewardsim.pathogen import (
    step_deterministic,
    step_recessive_diploid,
    step_wright_fisher,
)


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
