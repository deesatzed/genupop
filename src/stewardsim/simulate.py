"""Restriction-loop coupling driver (GOAL §6.6, design §2).

Daily discrete clock. Slice-0 incidence is daily: every supplied host
needs therapy every day and receives 1 dose-day of the first chosen
drug. ``Policy.duration`` is stored on the policy but is not applied —
it is not a course length and does not change loop length or dose-days.

For each day ``t`` and each host:

1. ``restricted = tape.play(t)`` — half-open ``[t0, t1)``.
2. Restricted drugs are extra hard constraints (``kind="restriction"``).
   Compose with the caller's ``ConstraintSet``. Do not invent a drug.
3. ``drugs = execute_choice(host, policy, constraints_today, adherence, rng)``.
4. ``append_exposure`` for the first chosen drug (1 dose-day).
5. Institution-wide dose-days that day, per drug.
6. ``s(det)`` from realized exposure (map below).
7. ``p = step_deterministic(p, s=s, fitness_cost=cost)`` — haploid map.
8. Hosts on day ``t+1`` see the updated ``p`` when scoring effective.

Importation is accepted as a typed argument and ignored in the loop
(Slice-0 rate-0 seam). No units, HGT, SIS, search, or SBI.

Selection map
-------------
``s = s_max * (today's dose-days of drugs in det.confers_resistance_to)
/ n_treated_today``. If ``n_treated_today == 0``, ``s = 0``. This is a
function of realized exposure, not a hidden constant.

Effective-therapy rule
----------------------
The chosen first drug is effective unless current frequency ``p`` is
strictly greater than 0.5 **and** that drug is in
``determinant.confers_resistance_to``. ``rounds_to_effective`` is 1 if
effective, else 2 (a second line would be required; Slice-0 does not
invent that line). Population mean sits beside the frequency series.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from stewardsim.feasibility import ConstraintSet, Rule, evaluate
from stewardsim.host import Host
from stewardsim.importation import Importation
from stewardsim.pathogen import Determinant, step_deterministic
from stewardsim.policy import (
    AdherenceModel,
    Policy,
    execute_choice,
    point_value,
    policy_preference,
)
from stewardsim.restriction import ForcedRestriction

EFFECTIVE_FREQUENCY_THRESHOLD = 0.5


class SimulateResult(BaseModel):
    """Primary Slice-0 loop outputs (design §2).

    ``frequencies[t]`` is ``p`` at the end of day ``t``.
    ``rounds_to_effective`` is the population mean of per-treatment
    rounds (serialized; Task 14 output name). ``mean_rounds_to_effective``
    is a property alias of that field.
    """

    frequencies: list[float]
    rounds_to_effective: float
    conflict_log: list[dict]
    dose_days: dict[str, list[float]]

    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def mean_rounds_to_effective(self) -> float:
        """Population mean rounds to effective therapy (alias)."""
        return self.rounds_to_effective


def compose_restrictions(
    constraints: ConstraintSet, restricted: frozenset[str]
) -> ConstraintSet:
    """Treat tape-restricted drugs as extra hard constraints for this day."""
    if not restricted:
        return constraints
    extra = [
        Rule(id=drug_id, kind="restriction", drug_id=drug_id)
        for drug_id in sorted(restricted)
    ]
    return ConstraintSet(
        hard=[*constraints.hard, *extra],
        soft=list(constraints.soft),
        sources=list(constraints.sources),
    )


def selection_coefficient(
    *,
    dose_days_by_drug: dict[str, float],
    confers_resistance_to: list[str],
    n_treated: int,
    s_max: float,
) -> float:
    """``s = s_max * (conferred dose-days) / n_treated``, else 0 if idle.

    Conferred dose-days are today's realized dose-days of drugs in
    ``confers_resistance_to``. ``s_max`` is a caller-supplied scale, not
    a module constant used in place of exposure.
    """
    if n_treated <= 0:
        return 0.0
    conferred = sum(
        float(dose_days_by_drug.get(drug_id, 0.0)) for drug_id in confers_resistance_to
    )
    return float(s_max) * conferred / float(n_treated)


def line_is_effective(first_drug: str, p: float, determinant: Determinant) -> bool:
    """Slice-0 rule: effective unless ``p > 0.5`` and the drug is conferred."""
    if (
        p > EFFECTIVE_FREQUENCY_THRESHOLD
        and first_drug in determinant.confers_resistance_to
    ):
        return False
    return True


def _rounds_to_effective(first_drug: str, p: float, determinant: Determinant) -> int:
    return 1 if line_is_effective(first_drug, p, determinant) else 2


def _collect_drug_ids(
    policy: Policy,
    adherence: AdherenceModel,
    determinant: Determinant,
) -> list[str]:
    ordered: list[str] = []
    for rule in policy.rules:
        ordered.extend(rule.preferred)
    ordered.extend(policy.reserve)
    ordered.extend(adherence.deviation_target.drugs)
    ordered.extend(determinant.confers_resistance_to)
    return list(dict.fromkeys(ordered))


def simulate(
    hosts: list[Host],
    *,
    policy: Policy,
    constraints: ConstraintSet,
    adherence: AdherenceModel,
    tape: ForcedRestriction,
    determinant: Determinant,
    p0: float,
    horizon: int,
    rng: np.random.Generator,
    s_max: float,
    importation: Importation | None = None,
) -> SimulateResult:
    """Run the daily restriction loop on structural hosts.

    Slice-0 incidence is daily: every host is treated every day of
    ``horizon`` with 1 dose-day. ``Policy.duration`` is not read and does
    not change the number of days, who is treated, or dose-days.

    ``importation`` is accepted and unused (rate-0 seam). ``rng`` must be
    a seeded ``numpy.random.Generator``.
    """
    del importation  # Slice-0: typed seam only; dynamics not run.
    if not isinstance(rng, np.random.Generator):
        raise TypeError(
            f"rng must be numpy.random.Generator, got {type(rng).__name__}"
        )
    if horizon < 0:
        raise ValueError("horizon must be >= 0")

    cost = point_value(determinant.fitness_cost)
    drug_ids = _collect_drug_ids(policy, adherence, determinant)
    dose_days: dict[str, list[float]] = {
        drug_id: [0.0] * horizon for drug_id in drug_ids
    }
    frequencies: list[float] = []
    conflict_log: list[dict] = []
    rounds: list[int] = []
    p = float(p0)
    live_hosts = list(hosts)

    for t in range(horizon):
        restricted = tape.play(t)
        constraints_today = compose_restrictions(constraints, restricted)
        day_dose = {drug_id: 0.0 for drug_id in dose_days}
        n_treated = 0
        next_hosts: list[Host] = []
        for host in live_hosts:
            drugs = execute_choice(host, policy, constraints_today, adherence, rng)
            if not drugs:
                preferred = policy_preference(policy, host)
                feasible = evaluate(host, preferred, constraints_today)
                if feasible.log_entry is not None:
                    conflict_log.append({"t": t, **feasible.log_entry})
                next_hosts.append(host)
                continue
            first = drugs[0]
            if first not in dose_days:
                dose_days[first] = [0.0] * horizon
                day_dose[first] = 0.0
            dose_days[first][t] += 1.0
            day_dose[first] += 1.0
            n_treated += 1
            rounds.append(_rounds_to_effective(first, p, determinant))
            next_hosts.append(host.append_exposure(first, 1.0, t))
        live_hosts = next_hosts
        s = selection_coefficient(
            dose_days_by_drug=day_dose,
            confers_resistance_to=determinant.confers_resistance_to,
            n_treated=n_treated,
            s_max=s_max,
        )
        p = step_deterministic(p, s=s, fitness_cost=cost)
        frequencies.append(p)

    mean_rounds = float(sum(rounds) / len(rounds)) if rounds else 0.0
    return SimulateResult(
        frequencies=frequencies,
        rounds_to_effective=mean_rounds,
        conflict_log=conflict_log,
        dose_days=dose_days,
    )
