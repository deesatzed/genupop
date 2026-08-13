"""Host individual with per-person exposure history (GOAL §4.3; design §2).

Slice-0 fields only: no unit_trajectory. exposure_history is required and
must remain a list of Exposure records — never a population prescribing rate.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

AdmissionSource = Literal["community", "transfer", "post_acute", "readmission"]


class Exposure(BaseModel):
    drug_id: str
    dose_days: float
    t: int

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("dose_days")
    @classmethod
    def _dose_days_positive(cls, value: float) -> float:
        if value <= 0.0:
            raise ValueError("dose_days must be > 0")
        return value

    @field_validator("t")
    @classmethod
    def _t_nonnegative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("t must be >= 0")
        return value


class Host(BaseModel):
    id: int
    demographics: dict = {}
    comorbidity: dict = {}
    exposure_history: list[Exposure]
    colonization: dict[str, list[str]] = {}
    admission_source: AdmissionSource = "community"

    model_config = ConfigDict(extra="forbid", frozen=True)

    def append_exposure(self, drug_id: str, dose_days: float, t: int) -> Host:
        exposure = Exposure(drug_id=drug_id, dose_days=dose_days, t=t)
        return self.model_copy(
            update={"exposure_history": [*self.exposure_history, exposure]}
        )

    def cumulative_dose_days(self, drug_id: str) -> float:
        return float(
            sum(item.dose_days for item in self.exposure_history if item.drug_id == drug_id)
        )
