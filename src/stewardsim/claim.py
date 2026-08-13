"""Claim ladder (GOAL §9, ADR-011)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

Tier = Literal[1, 2, 3]


class Claim(BaseModel):
    id: str | None = None
    value: float
    unit: str
    tier: Tier
    supports: list[str]
    provenance_variance: float | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def _enforce_tier_ladder(self) -> Claim:
        if self.tier == 3:
            if self.provenance_variance is None:
                raise ValueError("Tier 3 claims require provenance_variance")
            if not self.supports:
                raise ValueError("Tier 3 claims require at least one support")
            support_tiers = {
                registered.tier
                for support_id in self.supports
                if (registered := _CLAIM_REGISTRY.get(support_id)) is not None
            }
            if 1 not in support_tiers or 2 not in support_tiers:
                raise ValueError(
                    "Tier 3 claims require at least one Tier 1 and one Tier 2 support"
                )
        if self.id is not None:
            _CLAIM_REGISTRY[self.id] = self
        return self


_CLAIM_REGISTRY: dict[str, Claim] = {}
