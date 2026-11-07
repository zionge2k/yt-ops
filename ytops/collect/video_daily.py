"""Per-video daily metrics collector (Analytics query 4, dims=video,day)."""
from __future__ import annotations

from datetime import date

from ytops.collect.context import CollectContext

_METRICS = (
    "views,engagedViews,estimatedMinutesWatched,averageViewDuration,"
    "averageViewPercentage,subscribersGained,subscribersLost"
)


# The Analytics API rejects video,day without a video filter; 50 ids per query is the tested max.
FILTER_CHUNK = 50
# One request must never reach this cap (the client raises TruncationError if it does).
MAX_ROWS = 1000


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    ids = [item["id"] for item in ctx.data.uploads()]
    n_days = (end - start).days + 1
    chunk = max(1, min(FILTER_CHUNK, MAX_ROWS // n_days))
    result = []
    for i in range(0, len(ids), chunk):
        result.extend(ctx.analytics.query(
            start, end, "video,day", _METRICS,
            filters="video==" + ",".join(ids[i:i + chunk]), max_results=MAX_ROWS))
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
