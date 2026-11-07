"""Video catalog collector: every upload as one yt_video row."""
from __future__ import annotations

from datetime import date

from ytops.collect.context import CollectContext
from ytops.videos import content_kind, duration_seconds, parse_ts


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    rows = []
    for item in ctx.data.uploads():
        snippet, status = item.get("snippet", {}), item.get("status", {})
        rows.append({
            "video_id": item["id"],
            "channel_key": ctx.key,
            "title": snippet.get("title"),
            "published_at": parse_ts(snippet.get("publishedAt")),
            "publish_at": parse_ts(status.get("publishAt")),
            "privacy": status.get("privacyStatus"),
            "duration_s": duration_seconds(item.get("contentDetails", {}).get("duration")),
            "content_kind": content_kind(item),
            "thumbnail_url": snippet.get("thumbnails", {}).get("medium", {}).get("url"),
            "last_seen_at": ctx.collected_at,
        })
    return {"yt_video": rows}
