"""Reach collector: thumbnail impressions and CTR per video and day, from Reporting API report files."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone

from ytops.collect.context import CollectContext
from ytops.videos import parse_ts

# YouTube regenerates and backfills report files, so a run re-reads the reports created in the last
# week; rows are upserted on (channel, day, video) and a later report wins an overlapping day.
LOOKBACK_DAYS = 7
# CSV columns this collector reads; channel_id is optional and only checked against the expected channel.
REQUIRED = ("date", "video_id", "video_thumbnail_impressions", "video_thumbnail_impressions_ctr")
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _day(text: str) -> date:
    """Report dates arrive as 20261107; 2026-11-07 is accepted too."""
    text = text.strip()
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    return date.fromisoformat(text)


def _count(text: str) -> int | None:
    text = text.strip()
    return int(float(text)) if text else None


def _ratio(text: str) -> float | None:
    text = text.strip()
    return float(text) if text else None


def parse_report(text: str, channel_key: str, collected_at: datetime,
                 expected_channel_id: str | None = None) -> list[dict]:
    """yt_reach_daily rows of one report file (header-driven CSV; blank lines are skipped).

    CTR is a 0..1 ratio per the docs. A value above 1 can only be a percent, and units never mix inside one
    file, so if any CTR in the file exceeds 1 the whole file is divided by 100.
    If `expected_channel_id` is given, a row of another channel raises ValueError.
    """
    text = text.lstrip("﻿")
    if not text.strip():
        return []
    reader = csv.DictReader(io.StringIO(text))
    reader.fieldnames = [name.strip() for name in reader.fieldnames or []]
    missing = [name for name in REQUIRED if name not in reader.fieldnames]
    if missing:
        raise ValueError(f"reach report is missing column(s): {', '.join(missing)}")
    rows = []
    for raw in reader:
        cells = {name: (raw.get(name) or "") for name in REQUIRED}
        row_channel = (raw.get("channel_id") or "").strip()
        if expected_channel_id and row_channel and row_channel != expected_channel_id:
            raise ValueError(f"report channel {row_channel} != {expected_channel_id}")
        if not any(cell.strip() for cell in cells.values()):
            continue  # blank or comma-only line
        video_id = cells["video_id"].strip()
        if not video_id:
            continue
        rows.append({
            "channel_key": channel_key, "day": _day(cells["date"]), "video_id": video_id,
            "impressions": _count(cells["video_thumbnail_impressions"]),
            "ctr": _ratio(cells["video_thumbnail_impressions_ctr"]),
            "collected_at": collected_at,
        })
    if any(r["ctr"] is not None and r["ctr"] > 1 for r in rows):
        for r in rows:
            if r["ctr"] is not None:
                r["ctr"] = round(r["ctr"] / 100, 10)
    return rows


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    job = ctx.reporting.reach_job_id()
    if job is None:  # the job is not created yet (or was deleted): nothing to read, not an error
        return {"yt_reach_daily": []}
    reports = ctx.reporting.reports(job, ctx.collected_at - timedelta(days=LOOKBACK_DAYS))
    merged: dict[tuple[date, str], dict] = {}
    # oldest first, so a regenerated (later) report overwrites the rows of an earlier one
    for report in sorted(reports, key=lambda r: parse_ts(r.get("createTime")) or _EPOCH):
        url = report.get("downloadUrl")
        if not url:
            continue
        for row in parse_report(ctx.reporting.download(url), ctx.key, ctx.collected_at,
                                 ctx.channel.channel_id):
            merged[(row["day"], row["video_id"])] = row
    return {"yt_reach_daily": [merged[k] for k in sorted(merged)]}
