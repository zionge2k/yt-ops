"""Subscriber snapshot collector (Data API channels.list)."""
from __future__ import annotations

from datetime import date

from ytops.collect.context import CollectContext
from ytops.subscribers import exact_subscribers


def snapshot_row(
    ctx: CollectContext,
    stats: dict,
    baseline: tuple[date, int] | None = None,
    daily: list[tuple[date, int, int]] | tuple = (),
    latest_day: date | None = None,
) -> dict:
    api_subscribers = int(stats["statistics"]["subscriberCount"])
    monetized = bool(stats.get("status", {}).get("isChannelMonetizationEnabled", False))
    return {
        "channel_key": ctx.key,
        "taken_on": ctx.today,
        "api_subscribers": api_subscribers,
        "exact_subscribers": exact_subscribers(baseline, list(daily), latest_day, api_subscribers),
        "monetized": monetized,
    }


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    return {"yt_subs_snapshot": [snapshot_row(ctx, ctx.data.channel_stats())]}
