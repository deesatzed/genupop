"""Treatment episode: lines of therapy and rounds (GOAL §6.5, design §2).

Slice-0 opens an episode at empiric line 1 via policy ∘ feasibility ∘
adherence. Culture delay is a point Parameter. Escalation and
de-escalation types exist; this module does not run the restriction loop
and does not invent rounds_to_effective.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

from stewardsim.feasibility import ConstraintSet
from stewardsim.host import Host
from stewardsim.params import Parameter
from stewardsim.policy import AdherenceModel, Policy, execute_choice, point_value


class EscalationRule(BaseModel):
    culture_delay: Parameter

    model_config = ConfigDict(extra="forbid", frozen=True)


class DeEscalationRule(BaseModel):
    culture_delay: Parameter

    model_config = ConfigDict(extra="forbid", frozen=True)


class TherapyLine(BaseModel):
    line: int
    drugs: list[str]
    t: int

    model_config = ConfigDict(extra="forbid", frozen=True)


class Episode(BaseModel):
    host_id: int
    lines: list[TherapyLine]
    culture_return_t: int | None = None
    rounds_to_effective: int | None = None
    conflict: bool = False

    model_config = ConfigDict(extra="forbid", frozen=True)


def open_episode(
    host: Host,
    policy: Policy,
    constraints: ConstraintSet,
    adherence: AdherenceModel,
    rng: np.random.Generator,
    *,
    t: int = 0,
    culture_delay: Parameter | None = None,
) -> Episode:
    """Line 1 empiric choice. ``rounds_to_effective`` stays unset."""
    drugs = execute_choice(host, policy, constraints, adherence, rng)
    delay_t = None
    if culture_delay is not None:
        delay_t = t + int(point_value(culture_delay))
    return Episode(
        host_id=host.id,
        lines=[TherapyLine(line=1, drugs=list(drugs), t=t)],
        culture_return_t=delay_t,
        rounds_to_effective=None,
        conflict=len(drugs) == 0,
    )
