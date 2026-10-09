import math
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.geometry import (
    convex_hull,
    distance,
    flip_direction,
    pocket_area,
    polygon_area,
    segments_cross,
)


def test_distance_known_values():
    assert distance((0, 0), (3, 4)) == 5.0
    assert distance((1, 1), (1, 1)) == 0.0


def test_polygon_area_unit_square():
    assert polygon_area([(0, 0), (1, 0), (1, 1), (0, 1)]) == 1.0


def test_polygon_area_triangle():
    assert polygon_area([(0, 0), (4, 0), (0, 3)]) == 6.0


def test_segments_cross_known_crossing():
    assert segments_cross((0, 0), (2, 2), (0, 2), (2, 0)) is True


def test_segments_cross_known_non_crossing():
    assert segments_cross((0, 0), (1, 0), (0, 1), (1, 1)) is False


def test_flip_direction_known_values():
    assert flip_direction(0) == 180
    assert flip_direction(190) == 10
    assert flip_direction(350) == 170


def test_pocket_area_unordered_points_known_area():
    """Requirement 4.7: a convex-hull-area test on unordered points whose
    correct area is known, asserting the computed pocket area matches
    regardless of input ordering."""
    square = [(0, 0), (4, 0), (4, 4), (0, 4)]  # area = 16
    for _ in range(20):
        shuffled = square[:]
        random.shuffle(shuffled)
        assert abs(pocket_area(shuffled) - 16.0) < 1e-9

    # Interior point must not change the hull or its area.
    with_interior = square + [(2, 2)]
    random.shuffle(with_interior)
    assert abs(pocket_area(with_interior) - 16.0) < 1e-9


def test_convex_hull_drops_interior_points():
    pts = [(0, 0), (4, 0), (4, 4), (0, 4), (2, 2)]
    hull = convex_hull(pts)
    assert (2, 2) not in hull
    assert len(hull) == 4


# ---- Property-based tests ----


finite_floats = st.floats(
    min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False
)
points_strategy = st.lists(st.tuples(finite_floats, finite_floats), min_size=3, max_size=10)


@given(points=points_strategy)
@settings(max_examples=150)
def test_property_3_pocket_area_order_independent_and_nonnegative(points):
    """Property 3: pocket area equals the shoelace area of the convex hull,
    is >= 0, and is unchanged under any input ordering. Validates
    Requirements 4.1, 4.7."""
    area1 = pocket_area(points)
    shuffled = points[:]
    random.shuffle(shuffled)
    area2 = pocket_area(shuffled)
    assert area1 >= 0
    assert abs(area1 - area2) < 1e-6


@given(
    p=st.tuples(finite_floats, finite_floats),
    q=st.tuples(finite_floats, finite_floats),
)
@settings(max_examples=150)
def test_property_4_distance_symmetric_and_nonnegative(p, q):
    """Property 4: distance(p, q) == distance(q, p) and >= 0. Validates
    Requirement 4.7."""
    d_pq = distance(p, q)
    d_qp = distance(q, p)
    assert d_pq >= 0
    assert math.isclose(d_pq, d_qp, abs_tol=1e-9)


@given(d=st.floats(min_value=0, max_value=359.999, allow_nan=False))
@settings(max_examples=150)
def test_property_5_flip_direction_involutive(d):
    """Property 5: flipping twice returns d (mod 360). Validates
    Requirement 4.7."""
    once = flip_direction(d)
    twice = flip_direction(once)
    diff = abs(twice - d) % 360
    assert min(diff, 360 - diff) < 1e-9
