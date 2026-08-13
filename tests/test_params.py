import pytest
from pydantic import ValidationError
from stewardsim.params import DistributionSpec, Parameter, Provenance


def test_parameter_requires_provenance():
    with pytest.raises((ValidationError, TypeError)):
        Parameter(
            name="x",
            distribution=DistributionSpec(family="point", fitted_params={"value": 1.0}),
            source="test",
        )


def test_elicited_without_id_raises():
    with pytest.raises(ValueError):
        Parameter(
            name="fitness_cost",
            provenance=Provenance.ELICITED,
            distribution=DistributionSpec(
                family="lognormal",
                quantiles={0.05: 0.01, 0.5: 0.05, 0.95: 0.2},
            ),
            source="panel",
            elicitation_id=None,
        )


def test_inconsistent_quantiles_raise():
    with pytest.raises(ValueError):
        DistributionSpec(family="lognormal", quantiles={0.05: 0.9, 0.5: 0.1, 0.95: 0.2})


def test_moments_only_rejected():
    with pytest.raises(ValueError):
        DistributionSpec(family="normal", fitted_params={"mean": 0.0, "sd": 1.0})
