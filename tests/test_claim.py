import pytest
from stewardsim.claim import Claim


def test_tier3_requires_variance_and_supports():
    with pytest.raises(ValueError):
        Claim(value=1.0, unit="rounds", tier=3, supports=[], provenance_variance=None)


def test_tier3_requires_tier1_and_tier2_support():
    with pytest.raises(ValueError):
        Claim(
            value=1.0, unit="rounds", tier=3,
            supports=["c3"], provenance_variance=0.2,
        )


def test_valid_tier3():
    Claim(id="c1", value=0.0, unit="freq", tier=1, supports=[], provenance_variance=None)
    Claim(id="c2", value=0.1, unit="freq", tier=2, supports=["c1"], provenance_variance=None)
    Claim(
        id="c3", value=1.2, unit="rounds", tier=3,
        supports=["c1", "c2"], provenance_variance=0.4,
    )
