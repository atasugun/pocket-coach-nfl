"""Wilson score interval — a pure function with no pipeline dependencies so
it's trivially property-testable (Property 14)."""
from __future__ import annotations

import math


def wilson_interval(count: int, n: int, confidence: float = 0.90) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion. Returns
    (low, high), both clamped to [0, 1]."""
    if n <= 0:
        return (0.0, 0.0)
    z_table = {0.90: 1.6448536, 0.95: 1.959964, 0.99: 2.5758293}
    if confidence not in z_table:
        raise ValueError(f"unsupported confidence level {confidence}; add its z-score to z_table")
    z = z_table[confidence]

    p = count / n
    denom = 1 + z**2 / n
    center = p + z**2 / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)
    low = (center - margin) / denom
    high = (center + margin) / denom
    return (max(0.0, low), min(1.0, high))
