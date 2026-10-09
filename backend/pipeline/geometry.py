"""Pure, unit-tested geometry primitives (Requirement 4.7). `features.py`
composes these into play/player measurements; nothing here touches Parquet
or config.
"""
from __future__ import annotations

import math

Point = tuple[float, float]


def distance(p: Point, q: Point) -> float:
    """Euclidean distance; symmetric and non-negative (Property 4)."""
    return math.hypot(p[0] - q[0], p[1] - q[1])


def polygon_area(points: list[Point]) -> float:
    """Shoelace formula, absolute value — always >= 0. `points` must already
    be in polygon order (e.g. the CCW output of `convex_hull`)."""
    n = len(points)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def convex_hull(points: list[Point]) -> list[Point]:
    """Monotone-chain convex hull of an unordered point set, returned in
    counter-clockwise order. Duplicate/collinear points are handled by the
    standard cross-product turn test."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o: Point, a: Point, b: Point) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    hull = lower[:-1] + upper[:-1]
    return hull


def pocket_area(points: list[Point]) -> float:
    """Pocket area = shoelace area of the convex hull of `points` (pass
    blockers + QB), independent of input order (Property 3)."""
    return polygon_area(convex_hull(points))


def _orientation(p: Point, q: Point, r: Point) -> int:
    val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
    if abs(val) < 1e-12:
        return 0
    return 1 if val > 0 else -1


def _on_segment(p: Point, q: Point, r: Point) -> bool:
    return (
        min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
        and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9
    )


def segments_cross(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    """Orientation-sign test for whether segment a1-a2 crosses segment
    b1-b2; symmetric in segment order."""
    o1 = _orientation(a1, a2, b1)
    o2 = _orientation(a1, a2, b2)
    o3 = _orientation(b1, b2, a1)
    o4 = _orientation(b1, b2, a2)

    if o1 != o2 and o3 != o4:
        return True

    if o1 == 0 and _on_segment(a1, b1, a2):
        return True
    if o2 == 0 and _on_segment(a1, b2, a2):
        return True
    if o3 == 0 and _on_segment(b1, a1, b2):
        return True
    if o4 == 0 and _on_segment(b1, a2, b2):
        return True

    return False


def flip_direction(d: float) -> float:
    """(d + 180) mod 360; involutive (Property 5)."""
    return (d + 180) % 360
