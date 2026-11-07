"""Scheduled-upload collector: private videos that have a publishAt."""
from __future__ import annotations

from datetime import date

from ytops.collect.context import CollectContext
from ytops.videos import content_kind, parse_ts


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    rows = []
    for item in ctx.data.uploads():
        status = item.get("status", {})
        if status.get("privacyStatus") != "private" or not status.get("publishAt"):
            continue
        rows.append({
            "channel_key": ctx.key,
            "video_id": item["id"],
            "title": item.get("snippet", {}).get("title"),
            "publish_at": parse_ts(status["publishAt"]),
            "content_kind": content_kind(item),
            "seen_at": ctx.collected_at,
        })
    rows.sort(key=lambda r: r["publish_at"])
    return {"yt_schedule": rows}
