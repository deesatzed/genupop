import pytest
from stewardsim.params import DistributionSpec, Parameter, Provenance


def test_elicited_id_must_resolve(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="elicitation"):
        Parameter(
            name="hgt_rate",
            provenance=Provenance.ELICITED,
            distribution=DistributionSpec(
                family="lognormal",
                quantiles={0.05: 1e-6, 0.5: 1e-4, 0.95: 1e-2},
            ),
            source="panel",
            elicitation_id="missing_record",
        )
