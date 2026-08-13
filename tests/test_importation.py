"""Importation is a first-class Parameter object, never a raw float (GOAL §4.7)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from stewardsim.importation import Importation
from stewardsim.params import DistributionSpec, Parameter, Provenance


def _point(name: str, value: float) -> Parameter:
    return Parameter(
        name=name,
        provenance=Provenance.ASSUMED,
        distribution=DistributionSpec(family="point", fitted_params={"value": value}),
        source="test://slice0",
    )


def test_importation_raw_float_rate_raises() -> None:
    with pytest.raises((ValidationError, TypeError)):
        Importation(rate=0.01)  # type: ignore[arg-type]


def test_importation_requires_parameter_fields() -> None:
    rate = _point("import_rate", 0.01)
    mix = {"det_a": _point("mix_det_a", 1.0)}
    corr = _point("source_correlation", 0.0)
    with pytest.raises((ValidationError, TypeError)):
        Importation(
            rate=rate,
            determinant_mix={"det_a": 0.5},  # type: ignore[dict-item]
            source_correlation=corr,
        )
    with pytest.raises((ValidationError, TypeError)):
        Importation(
            rate=rate,
            determinant_mix=mix,
            source_correlation=0.2,  # type: ignore[arg-type]
        )
    with pytest.raises((ValidationError, TypeError)):
        Importation(
            rate=0.01,  # type: ignore[arg-type]
            determinant_mix=mix,
            source_correlation=corr,
        )


def test_zero_rate_is_legal() -> None:
    importation = Importation(
        rate=_point("import_rate", 0.0),
        determinant_mix={"det_a": _point("mix_det_a", 1.0)},
        source_correlation=_point("source_correlation", 0.0),
    )
    fitted = importation.rate.distribution.fitted_params
    assert fitted is not None
    assert fitted["value"] == 0.0
    assert importation.rate.distribution.family == "point"


def test_positive_rate_with_mix_is_legal() -> None:
    importation = Importation(
        rate=_point("import_rate", 0.01),
        determinant_mix={
            "det_a": _point("mix_det_a", 0.7),
            "det_b": _point("mix_det_b", 0.3),
        },
        source_correlation=_point("source_correlation", 0.1),
    )
    assert set(importation.determinant_mix) == {"det_a", "det_b"}
    assert all(
        isinstance(value, Parameter) for value in importation.determinant_mix.values()
    )
    assert isinstance(importation.source_correlation, Parameter)


def test_empty_determinant_mix_is_legal() -> None:
    importation = Importation(
        rate=_point("import_rate", 0.0),
        determinant_mix={},
        source_correlation=_point("source_correlation", 0.0),
    )
    assert importation.determinant_mix == {}


def test_importation_is_frozen_and_forbids_extra() -> None:
    importation = Importation(
        rate=_point("import_rate", 0.0),
        determinant_mix={},
        source_correlation=_point("source_correlation", 0.0),
    )
    with pytest.raises(ValidationError):
        Importation(
            rate=_point("import_rate", 0.0),
            determinant_mix={},
            source_correlation=_point("source_correlation", 0.0),
            invented=True,  # type: ignore[call-arg]
        )
    with pytest.raises((ValidationError, TypeError)):
        importation.rate = _point("import_rate", 0.2)  # type: ignore[misc]
