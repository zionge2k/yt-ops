"""Collection runner: per-channel collectors, upsert, run log."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from psycopg.types.json import Jsonb

from ytops import store
from ytops.analytics import for_key as analytics_for_key
from ytops.collect import COLLECTORS, subs
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
    "yt_live_snapshot": ["channel_key", "taken_at"],
}
REPLACE_PER_CHANNEL = ("yt_schedule",)  # a run finding nothing must clear the old rows
KEEP: dict[str, tuple[str, ...]] = {"yt_video": ("first_seen_at",)}


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
    return {"channel": key, "stage": stage, "error": type(e).__name__, "message": str(e)[:200]}


def _run_collector(name, module, ctx, start, end, video_start, conn, current_rows=()):
    if name == "subs":
        baseline, daily, latest_day = subs_inputs(conn, ctx.key, current_rows=current_rows)
        return {"yt_subs_snapshot": [subs.snapshot_row(ctx, ctx.data.channel_stats(), baseline, daily, latest_day)]}
    return module.collect(ctx, video_start if name == "video_daily" else start, end)


def run_collect(
    keys: list[str],
    *,
    days: int = 10,
    video_days: int = 10,
    dry_run: bool,
    conn=None,
    today: date | None = None,
) -> RunResult:
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
        for name, module in COLLECTORS:
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
                "errors": Jsonb(result.errors), "counts": Jsonb(result.counts),
            }], ["run_id"])
        except Exception as e:
            result.errors.append(_error("-", "run_log", e))
    return result
