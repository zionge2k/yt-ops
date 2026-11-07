"""Live snapshot collector: one row per active broadcast; nothing is written while the channel is off-air."""
from __future__ import annotations

import json
from datetime import date

from googleapiclient.errors import HttpError

from ytops.collect.context import CollectContext
from ytops.videos import parse_ts


def _concurrent(video: dict) -> int | None:
    value = video.get("liveStreamingDetails", {}).get("concurrentViewers")
    return int(value) if value is not None else None  # absent stays None, never 0


def _views(video: dict) -> int | None:
    value = video.get("statistics", {}).get("viewCount")
    return int(value) if value is not None else None


def http_error_reason(e: HttpError) -> str | None:
    """First API error reason (e.g. quotaExceeded), from error_details or the JSON body."""
    details = getattr(e, "error_details", None)
    if isinstance(details, list):
        for d in details:
            if isinstance(d, dict) and d.get("reason"):
                return d["reason"]
    try:
        return json.loads(e.content)["error"]["errors"][0]["reason"]
    except (ValueError, TypeError, KeyError, IndexError):
        return None


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    if not ctx.channel.is_live:
        return {}
    try:
        broadcasts = ctx.data.active_broadcasts()
    except HttpError as e:
        # Only "live streaming not enabled" means no live; quota / permission 403s must surface.
        if e.resp.status == 403 and http_error_reason(e) == "liveStreamingNotEnabled":
            return {}
        raise
    if not broadcasts:
        return {}
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
            "views": _views(videos[0]) if videos else None,
        })
    return {"yt_live_snapshot": rows}
