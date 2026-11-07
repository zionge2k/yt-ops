from datetime import date, datetime, timezone

from ytops.collect import video_daily
from ytops.collect.context import CollectContext
from ytops.registry import Channel

CH = Channel("soombi", "soombi", "UC1", False, 0, 0, "chalna")
TODAY = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 1, 0, tzinfo=timezone.utc)


class FakeAnalytics:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def query(self, start, end, dims, metrics, filters=None, sort=None, max_results=200):
        self.calls.append((start, end, dims, metrics, max_results))
        return self.rows


def ctx(rows):
    return CollectContext("soombi", CH, FakeAnalytics(rows), None, TODAY, NOW)


def test_video_daily_rows():
    c = ctx([
        {"video": "vid00001", "day": "2026-11-01", "views": 10, "engagedViews": 8,
         "estimatedMinutesWatched": 5, "averageViewDuration": 30, "averageViewPercentage": 55.5,
         "subscribersGained": 1, "subscribersLost": 0},
    ])
    out = video_daily.collect(c, date(2026, 11, 1), date(2026, 11, 2))
    assert out["yt_video_daily"] == [{
        "video_id": "vid00001", "channel_key": "soombi", "day": date(2026, 11, 1),
        "views": 10, "engaged_views": 8, "minutes": 5, "avd_s": 30, "avp": 55.5,
        "subs_gained": 1, "subs_lost": 0,
    }]
    assert c.analytics.calls == [(
        date(2026, 11, 1), date(2026, 11, 2), "video,day",
        "views,engagedViews,estimatedMinutesWatched,averageViewDuration,"
        "averageViewPercentage,subscribersGained,subscribersLost", 200)]


def test_video_daily_empty():
    assert video_daily.collect(ctx([]), TODAY, TODAY) == {"yt_video_daily": []}
