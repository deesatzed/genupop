import inspect

import pytest
from pydantic import ValidationError

from stewardsim.host import Exposure, Host


def test_host_requires_exposure_history() -> None:
    with pytest.raises((ValidationError, TypeError)):
        Host(id=1)


def test_host_accepts_empty_exposure_history() -> None:
    host = Host(id=1, exposure_history=[])
    assert host.exposure_history == []
    assert isinstance(host.exposure_history, list)


def test_append_exposure_grows_history() -> None:
    host = Host(id=1, exposure_history=[])
    grown = host.append_exposure("drug_a", 3.0, 0)
    grown = grown.append_exposure("drug_b", 2.5, 4)
    assert len(grown.exposure_history) == 2
    assert grown.exposure_history[0] == Exposure(drug_id="drug_a", dose_days=3.0, t=0)
    assert grown.exposure_history[1] == Exposure(drug_id="drug_b", dose_days=2.5, t=4)
    assert host.exposure_history == []
    assert grown is not host


def test_append_exposure_cannot_collapse_to_scalar_rate() -> None:
    host = Host(id=1, exposure_history=[])
    grown = host.append_exposure("drug_a", 4.0, 2)
    assert isinstance(grown.exposure_history, list)
    assert all(isinstance(item, Exposure) for item in grown.exposure_history)
    with pytest.raises((ValidationError, TypeError)):
        Host(id=1, exposure_history=12.0)  # type: ignore[arg-type]
    with pytest.raises((ValidationError, TypeError)):
        grown.exposure_history = 0.3  # type: ignore[misc]
    assert not hasattr(Host, "prescribing_rate")
    assert not hasattr(Host, "population_rate")
    rate_fields = [name for name in Host.model_fields if "rate" in name]
    assert rate_fields == []


def test_no_method_replaces_history_with_population_rate() -> None:
    names = {
        name
        for name, member in inspect.getmembers(Host, predicate=inspect.isfunction)
        if not name.startswith("_")
    }
    assert "append_exposure" in names
    assert "cumulative_dose_days" in names
    collapsing = {
        name
        for name in names
        if any(
            token in name.lower()
            for token in ("rate", "collapse", "replace", "aggregate", "population")
        )
    }
    assert collapsing == set()


def test_cumulative_dose_days_sums_history() -> None:
    host = Host(
        id=7,
        exposure_history=[
            Exposure(drug_id="drug_a", dose_days=3.0, t=0),
            Exposure(drug_id="drug_b", dose_days=5.0, t=3),
            Exposure(drug_id="drug_a", dose_days=2.5, t=10),
        ],
    )
    assert host.cumulative_dose_days("drug_a") == 5.5
    assert host.cumulative_dose_days("drug_b") == 5.0
    assert host.cumulative_dose_days("drug_c") == 0.0


def test_host_has_no_unit_trajectory_field() -> None:
    host = Host(id=1, exposure_history=[])
    assert "unit_trajectory" not in Host.model_fields
    assert not hasattr(host, "unit_trajectory")
    with pytest.raises(ValidationError):
        Host(id=1, exposure_history=[], unit_trajectory=[])
