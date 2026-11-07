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


def status_of(pct: float | None, up: float, down: float) -> str:
    if pct is None:
        return "grey"
    if pct >= up:
        return "green"
    if pct <= down:
        return "red"
    return "yellow"
