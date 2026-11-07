"""Audience collector: age/gender, country and content weight per subscribed status."""
from __future__ import annotations

from datetime import date, timedelta

from ytops.collect.context import CollectContext

SEGMENTS = {"subscribed": "SUBSCRIBED", "unsubscribed": "UNSUBSCRIBED"}
CONTENTS = {"vod": "videoOnDemand", "live": "liveStream"}
COUNTRY_MAX = 25
# Window: the 31 days ending yesterday (Analytics lags a few days; the window is fixed, not latest_day based).
WINDOW_DAYS = 31


def window(today: date) -> tuple[date, date]:
    return today - timedelta(days=WINDOW_DAYS), today - timedelta(days=1)


def _row(ctx: CollectContext, segment: str, content: str, dim: str, key: str, *,
         views=None, minutes=None, pct=None) -> dict:
    return {"channel_key": ctx.key, "as_of": ctx.today, "segment": segment, "content": content,
            "dim": dim, "key": key, "views": views, "minutes": minutes, "pct": pct}


def rows_for(ctx: CollectContext, segment: str, content: str, age_gender: list[dict],
             country: list[dict], weight: list[dict]) -> list[dict]:
    """Convert the three Analytics results of one (segment, content) pair to yt_audience rows."""
    out = [
        _row(ctx, segment, content, "age_gender", f"{r['ageGroup']}/{r['gender']}", pct=r["viewerPercentage"])
        for r in age_gender
    ]
    out += [
        _row(ctx, segment, content, "country", r["country"], views=r["views"], minutes=r["estimatedMinutesWatched"])
        for r in country
    ]
    out += [_row(ctx, segment, content, "weight", r["creatorContentType"], views=r["views"]) for r in weight]
    return out


def collect(ctx: CollectContext, start: date, end: date) -> dict[str, list[dict]]:
    start, end = window(ctx.today)
    rows: list[dict] = []
    for segment, status in SEGMENTS.items():
        # The weight query (views per content type) is shared by both contents of a segment.
        weight = ctx.analytics.query(start, end, "creatorContentType", "views",
                                     filters=f"subscribedStatus=={status}", max_results=50)
        for content, kind in CONTENTS.items():
            filters = f"subscribedStatus=={status};creatorContentType=={kind}"
            age_gender = ctx.analytics.query(start, end, "ageGroup,gender", "viewerPercentage",
                                             filters=filters, sort="-viewerPercentage", max_results=50)
            country = ctx.analytics.query(start, end, "country", "views,estimatedMinutesWatched",
                                          filters=filters, sort="-estimatedMinutesWatched",
                                          max_results=COUNTRY_MAX, top_n=True)
            rows += rows_for(ctx, segment, content, age_gender, country,
                             [w for w in weight if w["creatorContentType"] == kind])
    return {"yt_audience": rows}
