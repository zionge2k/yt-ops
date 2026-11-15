"""Video catalog collector: every upload as one yt_video row."""
from __future__ import annotations

from datetime import date, datetime

from ytops.collect.context import CollectContext
from ytops.videos import content_kind, duration_seconds, parse_ts


def row_of(item: dict, key: str, collected_at: datetime) -> dict:
    """The yt_video row of one videos.list item."""
    snippet, status = item.get("snippet", {}), item.get("status", {})
    return {
        "video_id": item["id"],
        "channel_key": key,
        "title": snippet.get("title"),
        "published_at": parse_ts(snippet.get("publishedAt")),
        "publish_at": parse_ts(status.get("publishAt")),
        "privacy": status.get("privacyStatus"),
        "duration_s": duration_seconds(item.get("contentDetails", {}).get("duration")),
        "content_kind": content_kind(item),
        "thumbnail_url": snippet.get("thumbnails", {}).get("medium", {}).get("url"),
        "last_seen_at": collected_at,
    }


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    return {"yt_video": [row_of(item, ctx.key, ctx.collected_at) for item in ctx.data.uploads()]}
