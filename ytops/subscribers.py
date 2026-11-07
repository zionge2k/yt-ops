"""Exact subscriber count, reconstructed from a sub-1000 baseline."""
from __future__ import annotations

from datetime import date

ROUNDING_FLOOR = 1000  # the API rounds subscriberCount at and above this


def exact_subscribers(
    baseline: tuple[date, int] | None,
    daily: list[tuple[date, int, int]],
    latest_day: date | None,
    api_now: int,
) -> int | None:
    """Exact subscribers, or None when unknowable.

    baseline: (day, exact count) saved while the channel was under 1,000.
    daily: (day, gained, lost) rows. Only days in (baseline day, latest_day]
    are applied; later days are unknown and left out.
    """
    if baseline is None:
        return api_now if api_now < ROUNDING_FLOOR else None
    base_day, base_count = baseline
    if latest_day is None:
        return base_count
    delta = sum(g - l for d, g, l in daily if base_day < d <= latest_day)
    return base_count + delta
