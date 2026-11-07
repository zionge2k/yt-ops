"""Period arithmetic for the dashboard (pure functions)."""
from __future__ import annotations

from datetime import date, timedelta


def window(latest_day: date, days: int) -> tuple[date, date]:
    return latest_day - timedelta(days=days - 1), latest_day


def compare_window(win: tuple[date, date], min_days: int = 28) -> tuple[date, date]:
    """The stretch a window is judged against: the days just before it, at least
    min_days long, so a short window is compared with a multi-week average instead
    of one noisy week (2026-11-07 decision)."""
    start, _ = win
    length = max((win[1] - start).days + 1, min_days)
    return start - timedelta(days=length), start - timedelta(days=1)


def previous(win: tuple[date, date]) -> tuple[date, date]:
    return compare_window(win, min_days=1)


def pct_change(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / abs(prev) * 100, 1)


def half_trend(values) -> float | None:
    """Percent change of the second half of a window over the first half.

    values: daily numbers in date order (None = no data, skipped). The window is split in
    two (the middle day goes to the second half when the length is odd). None when there
    are fewer than two values or the first half has no usable total.
    """
    vals = list(values)
    if len(vals) < 2:
        return None
    mid = len(vals) // 2
    first = [v for v in vals[:mid] if v is not None]
    second = [v for v in vals[mid:] if v is not None]
    if not first or not second:
        return None
    return pct_change(sum(second), sum(first))


def color_of(pct: float | None, up: float, down: float) -> str:
    """Trend color (v3): red = rising, blue = falling, purple = flat, grey = unknown."""
    if pct is None:
        return "grey"
    if pct >= up:
        return "red"
    if pct <= down:
        return "blue"
    return "purple"


def status_of(pct: float | None, up: float, down: float) -> str:
    if pct is None:
        return "grey"
    if pct >= up:
        return "green"
    if pct <= down:
        return "red"
    return "yellow"
