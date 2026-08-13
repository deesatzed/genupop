"""Importation — colonized arrivals from outside the institution (GOAL §4.7).

A first-class parameter object with its own provenance and uncertainty.
Never a raw float. ``rate`` point value 0.0 is legal. v2 replaces the
scalar rate with a network coupling; this interface is the swap point.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from stewardsim.params import Parameter


class Importation(BaseModel):
    rate: Parameter
    determinant_mix: dict[str, Parameter]
    source_correlation: Parameter

    model_config = ConfigDict(extra="forbid", frozen=True)
