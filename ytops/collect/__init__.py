"""Collectors: each module exposes collect(ctx, start, end) -> {table: rows}."""
from ytops.collect import audience, channel_daily, live, playlists, reach, schedule, subs, video, video_daily

COLLECTORS = [
    ("channel_daily", channel_daily),
    ("subs", subs),
    ("video", video),
    ("video_daily", video_daily),
    ("schedule", schedule),
    ("live", live),
    ("audience", audience),
    ("playlists", playlists),
    ("reach", reach),
]
