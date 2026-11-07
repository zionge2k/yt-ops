"""Playlist collector: every playlist of the channel and its video ids (replaced per run)."""
from __future__ import annotations

from datetime import date

from ytops.collect.context import CollectContext


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    playlists, items = [], []
    for p in ctx.data.playlists():
        pid = p["id"]
        playlists.append({
            "channel_key": ctx.key,
            "playlist_id": pid,
            "title": p.get("snippet", {}).get("title"),
            "item_count": p.get("contentDetails", {}).get("itemCount"),
            "seen_at": ctx.collected_at,
        })
        seen: set[str] = set()
        for it in ctx.data.playlist_items(pid):
            vid = it.get("contentDetails", {}).get("videoId")
            if vid and vid not in seen:  # a playlist may list a video twice
                seen.add(vid)
                items.append({"playlist_id": pid, "video_id": vid, "channel_key": ctx.key})
    return {"yt_playlist": playlists, "yt_playlist_item": items}
