"""Period arithmetic for the dashboard (pure functions)."""
from __future__ import annotations

from datetime import date, timedelta


def window(latest_day: date, days: int) -> tuple[date, date]:
    return latest_day - timedelta(days=days - 1), latest_day


def previous(win: tuple[date, date]) -> tuple[date, date]:
    start, _ = win
    length = (win[1] - start).days + 1
    return start - timedelta(days=length), start - timedelta(days=1)


def pct_change(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / prev * 100, 1)


def status_of(pct: float | None, up: float, down: float) -> str:
    if pct is None:
        return "grey"
    if pct >= up:
        return "green"
    if pct <= down:
        return "red"
    return "yellow"
