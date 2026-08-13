"""Study configuration kinds (Slice-0)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

StudyKind = Literal["retrodiction", "genetic_limit"]


class StudyHosts(BaseModel):
    n: int
    years: float

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("n")
    @classmethod
    def _n_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("hosts.n must be > 0")
        return value

    @field_validator("years")
    @classmethod
    def _years_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("hosts.years must be > 0")
        return value


class StudyConfig(BaseModel):
    study: str
    kind: StudyKind
    hosts: StudyHosts
    restriction_tape: str | None = None
    seed: int
    outputs: list[str] = []
    importation: dict[str, Any] | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("kind", mode="before")
    @classmethod
    def _reject_projection(cls, value: Any) -> Any:
        if value == "projection":
            raise ValueError("kind: projection is not allowed in Slice-0")
        return value

    @field_validator("importation", mode="before")
    @classmethod
    def _importation_must_be_mapping(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, bool) or isinstance(value, (int, float)):
            raise ValueError(
                "importation must be a mapping (Importation object), not a bare float"
            )
        if not isinstance(value, dict):
            raise ValueError("importation must be a mapping (Importation object)")
        return value

    @field_validator("restriction_tape")
    @classmethod
    def _blank_tape_is_missing(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    @model_validator(mode="after")
    def _require_restriction_tape_for_retrodiction(self) -> StudyConfig:
        if self.kind == "retrodiction" and self.restriction_tape is None:
            raise ValueError("kind: retrodiction requires restriction_tape path")
        return self


def load_study(path: str | Path) -> StudyConfig:
    raw_path = Path(path)
    data = yaml.safe_load(raw_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"study config must be a mapping: {raw_path}")
    return StudyConfig.model_validate(data)
