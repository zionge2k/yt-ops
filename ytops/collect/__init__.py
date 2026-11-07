"""Collectors: each module exposes collect(ctx, start, end) -> {table: rows}."""
from ytops.collect import channel_daily, subs

COLLECTORS = [
    ("channel_daily", channel_daily),
    ("subs", subs),
]
