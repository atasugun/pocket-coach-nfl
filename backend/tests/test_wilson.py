from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.wilson import wilson_interval


@given(n=st.integers(min_value=1, max_value=10000))
@settings(max_examples=150)
def test_property_14_wilson_bounds_well_formed(n):
    """Property 14: for count k and opportunities n, rate == k/n and the
    Wilson 90% interval satisfies 0 <= low <= rate <= high <= 1. Validates
    Requirement 9.3."""
    import random

    k = random.randint(0, n)
    rate = k / n
    low, high = wilson_interval(k, n, confidence=0.90)
    assert 0 <= low <= rate + 1e-9
    assert rate - 1e-9 <= high <= 1
    assert low <= high
