"""Live snapshot collector: one row per active broadcast, or a single 'none' row."""
from __future__ import annotations

from datetime import date

from googleapiclient.errors import HttpError

from ytops.collect.context import CollectContext
from ytops.videos import parse_ts


def _concurrent(video: dict) -> int | None:
    value = video.get("liveStreamingDetails", {}).get("concurrentViewers")
    return int(value) if value is not None else None  # absent stays None, never 0


def _none_row(ctx: CollectContext) -> dict[str, list[dict]]:
    return {"yt_live_snapshot": [{
        "channel_key": ctx.key, "taken_at": ctx.collected_at, "broadcast_id": None,
        "life_cycle": "none", "concurrent": None, "health": None,
        "stream_status": None, "actual_start": None, "title": None,
    }]}


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    if not ctx.channel.is_live:
        return _none_row(ctx)
    try:
        broadcasts = ctx.data.active_broadcasts()
    except HttpError as e:
        # Channels that never enabled live streaming answer 403.
        if e.resp.status == 403:
            return _none_row(ctx)
        raise
    if not broadcasts:
        return _none_row(ctx)
    rows = []
    for b in broadcasts:
        broadcast_id = b["id"]
        videos = ctx.data.videos([broadcast_id])
        details = (videos[0] if videos else {}).get("liveStreamingDetails", {})
        stream_id = b.get("contentDetails", {}).get("boundStreamId")
        stream = ctx.data.stream_health(stream_id) if stream_id else {}
        rows.append({
            "channel_key": ctx.key,
            "taken_at": ctx.collected_at,
            "broadcast_id": broadcast_id,
            "life_cycle": b.get("status", {}).get("lifeCycleStatus"),
            "concurrent": _concurrent(videos[0]) if videos else None,
            "health": stream.get("healthStatus", {}).get("status"),
            "stream_status": stream.get("streamStatus"),
            "actual_start": parse_ts(details.get("actualStartTime")),
            "title": b.get("snippet", {}).get("title"),
        })
    return {"yt_live_snapshot": rows}
