import math

import pytest
from pydantic import ValidationError
from scipy import stats

from stewardsim.params import DistributionSpec, Parameter, Provenance

_PS = (0.05, 0.5, 0.95)


def _quantiles(ppf, *args, **kwargs) -> dict[float, float]:
    return {p: float(ppf(p, *args, **kwargs)) for p in _PS}


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


def test_family_inconsistent_lognormal_raises():
    # Monotone, but not representable as a 2-parameter lognormal: a huge 95th
    # must not hide a 5th/50th miss (GOAL §4.3 fail-loud).
    with pytest.raises(ValueError):
        DistributionSpec(
            family="lognormal",
            quantiles={0.05: 1.0, 0.5: 1.0001, 0.95: 1000.0},
        )


def test_moments_only_rejected():
    with pytest.raises(ValueError):
        DistributionSpec(family="normal", fitted_params={"mean": 0.0, "sd": 1.0})


def test_recovers_exact_lognormal():
    mu, sigma = -1.0, 0.5
    spec = DistributionSpec(
        family="lognormal",
        quantiles=_quantiles(stats.lognorm.ppf, s=sigma, scale=math.exp(mu)),
    )
    assert spec.fitted_params is not None
    assert spec.fitted_params["mu"] == pytest.approx(mu, rel=1e-3, abs=1e-4)
    assert spec.fitted_params["sigma"] == pytest.approx(sigma, rel=1e-3, abs=1e-4)
    assert spec.residual is not None
    assert spec.residual == pytest.approx(0.0, abs=1e-8)


def test_recovers_exact_normal():
    mean, sd = 3.0, 2.0
    spec = DistributionSpec(
        family="normal",
        quantiles=_quantiles(stats.norm.ppf, loc=mean, scale=sd),
    )
    assert spec.fitted_params is not None
    assert spec.fitted_params["mean"] == pytest.approx(mean, rel=1e-3, abs=1e-4)
    assert spec.fitted_params["sd"] == pytest.approx(sd, rel=1e-3, abs=1e-4)
    assert spec.residual is not None
    assert spec.residual == pytest.approx(0.0, abs=1e-8)


def test_recovers_exact_gamma():
    shape, scale = 2.0, 1.0
    spec = DistributionSpec(
        family="gamma",
        quantiles=_quantiles(stats.gamma.ppf, a=shape, scale=scale),
    )
    assert spec.fitted_params is not None
    assert spec.fitted_params["shape"] == pytest.approx(shape, rel=1e-3, abs=1e-4)
    assert spec.fitted_params["scale"] == pytest.approx(scale, rel=1e-3, abs=1e-4)
    assert spec.residual is not None
    assert spec.residual == pytest.approx(0.0, abs=1e-8)


def test_recovers_exact_beta():
    a, b = 2.0, 5.0
    spec = DistributionSpec(
        family="beta",
        quantiles=_quantiles(stats.beta.ppf, a=a, b=b),
    )
    assert spec.fitted_params is not None
    assert spec.fitted_params["a"] == pytest.approx(a, rel=1e-3, abs=1e-4)
    assert spec.fitted_params["b"] == pytest.approx(b, rel=1e-3, abs=1e-4)
    assert spec.residual is not None
    assert spec.residual == pytest.approx(0.0, abs=1e-8)


def test_recovers_exact_triangular():
    left, mode, right = 0.0, 1.0, 4.0
    c = (mode - left) / (right - left)
    spec = DistributionSpec(
        family="triangular",
        quantiles=_quantiles(stats.triang.ppf, c=c, loc=left, scale=right - left),
    )
    assert spec.fitted_params is not None
    assert spec.fitted_params["left"] == pytest.approx(left, rel=1e-3, abs=1e-3)
    assert spec.fitted_params["mode"] == pytest.approx(mode, rel=1e-3, abs=1e-3)
    assert spec.fitted_params["right"] == pytest.approx(right, rel=1e-3, abs=1e-3)
    assert spec.residual is not None
    assert spec.residual == pytest.approx(0.0, abs=1e-6)


def test_ordinary_elicited_gamma_constructs():
    spec = DistributionSpec(
        family="gamma",
        quantiles={0.05: 0.5, 0.5: 2.0, 0.95: 6.0},
    )
    assert spec.fitted_params is not None
    assert spec.fitted_params["shape"] > 0.0
    assert spec.fitted_params["scale"] > 0.0
    assert spec.residual is not None


def test_overconfidence_lognormal_stays_positive_and_widens():
    quantiles = {0.05: 0.01, 0.5: 0.05, 0.95: 0.2}
    base = DistributionSpec(family="lognormal", quantiles=quantiles)
    wide = DistributionSpec(
        family="lognormal",
        quantiles=quantiles,
        overconfidence_correction=1.5,
    )
    assert wide.quantiles == quantiles
    assert base.fitted_params is not None
    assert wide.fitted_params is not None

    def ppf(spec: DistributionSpec, p: float) -> float:
        params = spec.fitted_params
        assert params is not None
        return float(stats.lognorm.ppf(p, s=params["sigma"], scale=math.exp(params["mu"])))

    low_base, low_wide = ppf(base, 0.05), ppf(wide, 0.05)
    high_base, high_wide = ppf(base, 0.95), ppf(wide, 0.95)
    assert low_wide > 0.0
    assert low_wide < low_base
    assert high_wide > high_base
    assert wide.fitted_params["sigma"] > base.fitted_params["sigma"]


def test_quantile_probability_outside_unit_interval_raises():
    with pytest.raises(ValueError, match=r"\(0, 1\)"):
        DistributionSpec(
            family="normal",
            quantiles={0.0: -1.0, 0.5: 0.0, 0.95: 1.0},
        )


def test_parameter_frozen_cannot_clear_elicitation_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    record = tmp_path / "configs" / "elicitation" / "panel1.yaml"
    record.parent.mkdir(parents=True)
    record.write_text("citation: test://elicitation\n")
    param = Parameter(
        name="hgt_rate",
        provenance=Provenance.ELICITED,
        distribution=DistributionSpec(
            family="lognormal",
            quantiles={0.05: 1e-6, 0.5: 1e-4, 0.95: 1e-2},
        ),
        source="panel",
        elicitation_id="panel1",
    )
    with pytest.raises((ValidationError, TypeError)):
        param.elicitation_id = None


def test_distribution_frozen_cannot_set_sigma():
    spec = DistributionSpec(
        family="lognormal",
        quantiles={0.05: 0.01, 0.5: 0.05, 0.95: 0.2},
    )
    with pytest.raises((ValidationError, TypeError)):
        spec.fitted_params = {"mu": 0.0, "sigma": -1.0}


def test_elicitation_id_rejects_unsafe_path():
    with pytest.raises(ValueError, match="elicitation_id"):
        Parameter(
            name="hgt_rate",
            provenance=Provenance.ASSUMED,
            distribution=DistributionSpec(family="point", fitted_params={"value": 1.0}),
            source="test",
            elicitation_id="../secret",
        )
