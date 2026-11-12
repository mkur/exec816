"""Shared latency sample summaries; retain the established percentile rule."""
import math

def distribution(values):
    if not values:
        return dict(count=0)
    ordered = sorted(values)
    return dict(count=len(values), median_ms=ordered[len(values)//2],
                p95_ms=ordered[math.ceil(len(values)*.95)-1], max_ms=max(values))


