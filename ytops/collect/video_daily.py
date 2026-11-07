"""Per-video daily metrics collector (Analytics query 4, dims=video,day)."""
from __future__ import annotations

from datetime import date

from ytops.collect.context import CollectContext

_METRICS = (
    "views,engagedViews,estimatedMinutesWatched,averageViewDuration,"
    "averageViewPercentage,subscribersGained,subscribersLost"
)


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    result = ctx.analytics.query(start, end, "video,day", _METRICS, max_results=200)
    rows = [
        {
            "video_id": r["video"],
            "channel_key": ctx.key,
            "day": date.fromisoformat(r["day"]),
            "views": r.get("views"),
            "engaged_views": r.get("engagedViews"),
            "minutes": r.get("estimatedMinutesWatched"),
            "avd_s": r.get("averageViewDuration"),
            "avp": r.get("averageViewPercentage"),
            "subs_gained": r.get("subscribersGained"),
            "subs_lost": r.get("subscribersLost"),
        }
        for r in result
    ]
    rows.sort(key=lambda r: (r["day"], r["video_id"]))
    return {"yt_video_daily": rows}
