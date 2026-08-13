"""Determinant frequency maps (GOAL.md §6.1, AT-1/2/3/4/7).

Deterministic haploid/genic selection plus diploid Wright–Fisher sampling.
Selection coefficient and fitness cost are function arguments, not hidden
constants. HGT and compensation are not implemented here.
"""

from __future__ import annotations

import numpy as np


def step_deterministic(
    p: float,
    *,
    s: float = 0.0,
    mu: float = 0.0,
    fitness_cost: float = 0.0,
) -> float:
    """One generation of haploid selection then unidirectional mutation.

    Fitnesses: w_R = (1+s)(1-fitness_cost), w_S = 1.
    Selection: p' = p w_R / (p w_R + (1-p)).
    With fitness_cost = 0 this is the discrete logistic p' = p(1+s)/(1+s p).
    With s = 0 this is the cost map p' = p(1-c)/(1-c p).
    Mutation (S → R, after selection): p'' = p' + μ(1-p').
    """
    w_r = (1.0 + s) * (1.0 - fitness_cost)
    denom = p * w_r + (1.0 - p)
    p_sel = p if denom == 0.0 else p * w_r / denom
    return p_sel + mu * (1.0 - p_sel)


def step_wright_fisher(
    p: float,
    N: int,
    rng: np.random.Generator,
    *,
    s: float = 0.0,
    mu: float = 0.0,
    fitness_cost: float = 0.0,
) -> float:
    """One diploid Wright–Fisher generation: Binomial(2N, p*) / (2N).

    p* is the deterministic frequency after selection and mutation.
    The 2N census is the carried AT-3 contract (diploid WF variance).
    """
    p_star = step_deterministic(p, s=s, mu=mu, fitness_cost=fitness_cost)
    n_chrom = 2 * N
    return float(rng.binomial(n_chrom, p_star) / n_chrom)


def step_recessive_diploid(q: float, *, s: float, mu: float) -> float:
    """Mutation then selection against a recessive homozygote.

    Carried AT-2 contract, not a claim that bacteria are diploid.
    q_m = q + μ(1-q); q' = q_m (1 - s q_m) / (1 - s q_m²).
    Equilibrium is √(μ/s), not haploid μ/s.
    """
    q_m = q + mu * (1.0 - q)
    denom = 1.0 - s * q_m * q_m
    return q_m if denom == 0.0 else q_m * (1.0 - s * q_m) / denom
