"""Collection runner: per-channel collectors, upsert, run log."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from googleapiclient.errors import HttpError
from psycopg.types.json import Jsonb

from ytops import store
from ytops.analytics import for_key as analytics_for_key
from ytops.collect import COLLECTORS, live, subs
from ytops.collect.context import CollectContext
from ytops.data import for_key as data_for_key
from ytops.registry import load_channels

PRIMARY_KEYS: dict[str, list[str]] = {
    "yt_channel_daily": ["channel_key", "day"],
    "yt_yearly_minutes": ["channel_key", "as_of"],
    "yt_subs_snapshot": ["channel_key", "taken_on"],
    "yt_video": ["video_id"],
    "yt_video_daily": ["video_id", "day"],
    "yt_schedule": ["channel_key", "video_id"],
    "yt_live_snapshot": ["channel_key", "taken_at", "broadcast_id"],
    "yt_audience": ["channel_key", "as_of", "segment", "content", "dim", "key"],
    "yt_playlist": ["playlist_id"],
    "yt_playlist_item": ["playlist_id", "video_id"],
}
# a run finding nothing must clear the old rows (deleted schedules / playlists must not linger)
REPLACE_PER_CHANNEL = ("yt_schedule", "yt_playlist", "yt_playlist_item")
KEEP: dict[str, tuple[str, ...]] = {"yt_video": ("first_seen_at",)}
# Analytics query 2 (day x creatorContentType, <=5 types) must stay under its 1,000-row cap,
# so a long channel_daily window is collected in slices of this many days.
CHANNEL_DAILY_SLICE = 180


@dataclass
class RunResult:
    run_id: str
    started_at: datetime
    latest_day: date | None
    errors: list[dict] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def subs_inputs(conn, key: str, fetch=store.fetch, current_rows=()):
    """Baseline / daily deltas / latest aggregated day for the exact-subscriber estimate.

    current_rows: yt_channel_daily rows collected this run (not yet in the DB); they
    win over DB rows on the same day and extend latest_day.
    """
    baseline = None
    db_daily: dict[date, tuple[int, int]] = {}
    db_latest = None
    if conn is not None:
        rows = fetch(
            conn,
            "select taken_on, api_subscribers from yt_subs_snapshot "
            "where channel_key = %s and api_subscribers < 1000 order by taken_on desc limit 1",
            (key,),
        )
        baseline = (rows[0]["taken_on"], rows[0]["api_subscribers"]) if rows else None
        if baseline:
            for r in fetch(
                conn,
                "select day, subs_gained, subs_lost from yt_channel_daily "
                "where channel_key = %s and day >= %s order by day",
                (key, baseline[0]),
            ):
                db_daily[r["day"]] = (r["subs_gained"], r["subs_lost"])
        latest = fetch(conn, "select max(day) as latest from yt_channel_daily where channel_key = %s", (key,))
        db_latest = latest[0]["latest"] if latest else None
    merged = dict(db_daily)
    for r in current_rows:
        merged[r["day"]] = (r["subs_gained"], r["subs_lost"])
    # a day missing from the totals query leaves None; treat as 0 gained/lost
    daily = [(d, g or 0, l or 0) for d, (g, l) in sorted(merged.items())
             if baseline is None or d >= baseline[0]]
    days = [d for d in (db_latest, *(r["day"] for r in current_rows)) if d is not None]
    return baseline, daily, (max(days) if days else None)


def _error(key: str, stage: str, e: Exception) -> dict:
    err = {"channel": key, "stage": stage, "error": type(e).__name__, "message": str(e)[:200]}
    if isinstance(e, HttpError):  # machine-readable, since the message is cut at 200 chars
        err["status"], err["reason"] = e.resp.status, live.http_error_reason(e)
    return err


def slices(start: date, end: date, size: int = CHANNEL_DAILY_SLICE) -> list[tuple[date, date]]:
    """Split [start, end] into consecutive inclusive windows of at most `size` days."""
    out = []
    lo = start
    while lo <= end:
        hi = min(end, lo + timedelta(days=size - 1))
        out.append((lo, hi))
        lo = hi + timedelta(days=1)
    return out


def _collect_channel_daily(module, ctx, start, end):
    merged: dict[str, list[dict]] = {}
    for i, (lo, hi) in enumerate(slices(start, end)):
        # yearly minutes do not depend on the slice: query them with the first slice only
        out = module.collect(ctx, lo, hi, with_yearly=(i == 0))
        for table, rows in out.items():
            merged.setdefault(table, []).extend(rows)
    return merged


def _run_collector(name, module, ctx, start, end, video_start, conn, current_rows=()):
    if name == "subs":
        baseline, daily, latest_day = subs_inputs(conn, ctx.key, current_rows=current_rows)
        return {"yt_subs_snapshot": [subs.snapshot_row(ctx, ctx.data.channel_stats(), baseline, daily, latest_day)]}
    if name == "channel_daily":
        return _collect_channel_daily(module, ctx, start, end)
    return module.collect(ctx, video_start if name == "video_daily" else start, end)


def run_collect(
    keys: list[str],
    *,
    days: int = 10,
    video_days: int = 10,
    dry_run: bool,
    conn=None,
    today: date | None = None,
    only: list[str] | tuple[str, ...] | None = None,
) -> RunResult:
    """only: restrict to these collector names (e.g. ["live"]); None runs every collector."""
    collectors = COLLECTORS if only is None else [(n, m) for n, m in COLLECTORS if n in set(only)]
    unknown = set(only or ()) - {n for n, _ in COLLECTORS}
    if unknown:
        raise ValueError(f"unknown collector(s): {', '.join(sorted(unknown))}")
    started_at = datetime.now(timezone.utc)
    # calendar "today" is the Seoul date, same as render/commands
    today = today or datetime.now(ZoneInfo("Asia/Seoul")).date()
    start, end, video_start = today - timedelta(days=days), today - timedelta(days=1), today - timedelta(days=video_days)
    channels = load_channels()
    result = RunResult(uuid.uuid4().hex, started_at, None)
    days_seen: list[date] = []
    db = None if dry_run else conn

    for key in keys:
        collected: dict[str, list[dict]] = {}
        try:
            ctx = CollectContext(
                key=key, channel=channels[key], analytics=analytics_for_key(key),
                data=data_for_key(key), today=today, collected_at=datetime.now(timezone.utc),
            )
        except Exception as e:  # auth / registry failure: skip this channel only
            result.errors.append(_error(key, "client", e))
            continue
        for name, module in collectors:
            try:
                out = _run_collector(name, module, ctx, start, end, video_start, db, collected.get("yt_channel_daily", ()))
            except Exception as e:
                result.errors.append(_error(key, name, e))
                continue
            for table, rows in out.items():
                if table == "yt_video":
                    for r in rows:
                        r["first_seen_at"] = ctx.collected_at
                collected.setdefault(table, []).extend(rows)
        for table, rows in collected.items():
            if table == "yt_channel_daily":
                days_seen += [r["day"] for r in rows]
            if dry_run:
                print(f"{key} {table}: {len(rows)} rows")
                for sample in rows[:2]:
                    print(f"  {sample!r}")
                result.counts[table] = result.counts.get(table, 0) + len(rows)
            elif db is not None:
                try:
                    if table in REPLACE_PER_CHANNEL:
                        n = store.replace_channel(db, table, key, rows, PRIMARY_KEYS[table])
                    else:
                        n = store.upsert(db, table, rows, PRIMARY_KEYS[table], KEEP.get(table, ()))
                    result.counts[table] = result.counts.get(table, 0) + n
                except Exception as e:
                    result.errors.append(_error(key, f"store:{table}", e))
            else:
                result.counts[table] = result.counts.get(table, 0) + len(rows)

    result.latest_day = max(days_seen) if days_seen else None
    if db is not None:
        try:
            store.upsert(db, "yt_run_log", [{
                "run_id": result.run_id, "started_at": started_at,
                "finished_at": datetime.now(timezone.utc), "ok": not result.errors,
                "latest_day": result.latest_day,
                "channels": Jsonb(list(keys)),
                "collectors": Jsonb([n for n, _ in collectors]),
                "errors": Jsonb(result.errors), "counts": Jsonb(result.counts),
            }], ["run_id"])
        except Exception as e:
            result.errors.append(_error("-", "run_log", e))
    return result
