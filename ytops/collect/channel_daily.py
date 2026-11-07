"""Channel daily collector: three Analytics queries merged on day, plus yearly minutes."""
from __future__ import annotations

from datetime import date, timedelta

from ytops.collect.context import CollectContext

_BY_TYPE = {"shorts": "min_shorts", "liveStream": "min_live", "videoOnDemand": "min_vod"}
_BY_LOL = {"LIVE": "min_lol_live", "ON_DEMAND": "min_lol_ondemand"}
# Per-request cap (TruncationError otherwise). Largest query is day,creatorContentType:
# 185-day backfill x <=5 content types = <=925 rows, still below it.
MAX_ROWS = 1000
_MINUTES = "estimatedMinutesWatched"

_COLS = (
    "views", "min_shorts", "min_live", "min_vod", "min_unspec", "min_lol_live",
    "min_lol_ondemand", "subs_gained", "subs_lost", "views_shorts",
    "engaged_views_shorts", "subs_gained_shorts",
)


def _day(value: str) -> date:
    return date.fromisoformat(value)


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    days: dict[date, dict] = {}

    def row(day: date) -> dict:
        # Columns stay None until a query actually reports that day.
        return days.setdefault(day, dict.fromkeys(_COLS))

    # Query 1: totals per day
    for r in ctx.analytics.query(start, end, "day", "views,subscribersGained,subscribersLost", max_results=MAX_ROWS):
        d = row(_day(r["day"]))
        d["views"], d["subs_gained"], d["subs_lost"] = r["views"], r["subscribersGained"], r["subscribersLost"]

    # Query 2: per content type (day present => absent types are a true 0)
    for r in ctx.analytics.query(
        start, end, "day,creatorContentType",
        f"{_MINUTES},views,engagedViews,subscribersGained", max_results=MAX_ROWS,
    ):
        d = row(_day(r["day"]))
        for col in ("min_shorts", "min_live", "min_vod", "min_unspec",
                    "views_shorts", "engaged_views_shorts", "subs_gained_shorts"):
            d[col] = d[col] or 0
        d[_BY_TYPE.get(r["creatorContentType"], "min_unspec")] += r[_MINUTES]
        if r["creatorContentType"] == "shorts":
            d["views_shorts"] += r["views"]
            d["engaged_views_shorts"] += r["engagedViews"]
            d["subs_gained_shorts"] += r["subscribersGained"]

    # Query 3: live vs on-demand minutes
    for r in ctx.analytics.query(start, end, "day,liveOrOnDemand", _MINUTES, max_results=MAX_ROWS):
        d = row(_day(r["day"]))
        d["min_lol_live"] = d["min_lol_live"] or 0
        d["min_lol_ondemand"] = d["min_lol_ondemand"] or 0
        col = _BY_LOL.get(r["liveOrOnDemand"])
        if col:
            d[col] += r[_MINUTES]

    collected_at = ctx.collected_at
    rows = [
        {"channel_key": ctx.key, "day": day, **cols, "collected_at": collected_at}
        for day, cols in sorted(days.items())
    ]
    y = yearly_minutes(ctx)
    yearly = {
        "channel_key": ctx.key, "as_of": ctx.today,
        "min_live": y["min_live"], "min_vod": y["min_vod"], "min_shorts": y["min_shorts"],
        "start_day": y["start"], "end_day": y["end"],
    }
    return {"yt_channel_daily": rows, "yt_yearly_minutes": [yearly]}


def yearly_minutes(ctx: CollectContext) -> dict:
    """Watch minutes by content type over the last 365 days (query 5)."""
    start, end = ctx.today - timedelta(days=365), ctx.today - timedelta(days=1)
    rows = ctx.analytics.query(start, end, "creatorContentType", _MINUTES, max_results=MAX_ROWS)
    out: dict = {"min_live": None, "min_vod": None, "min_shorts": None, "start": start, "end": end}
    if rows:  # no rows at all stays None (no data), otherwise absent types are 0
        out.update(min_live=0, min_vod=0, min_shorts=0)
    for r in rows:
        col = _BY_TYPE.get(r["creatorContentType"])
        if col:
            out[col] += r[_MINUTES]
    return out
