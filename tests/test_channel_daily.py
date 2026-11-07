from datetime import date, datetime, timezone

from ytops.collect import channel_daily
from ytops.collect.context import CollectContext
from ytops.registry import Channel

CH = Channel("soombi", "soombi", "UC1", False, 0, 0, "chalna")
TODAY = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 1, 0, tzinfo=timezone.utc)

Q1 = "day"
Q2 = "day,creatorContentType"
Q3 = "day,liveOrOnDemand"
Q5 = "creatorContentType"


class FakeAnalytics:
    def __init__(self, by_dims):
        self.by_dims = by_dims
        self.calls = []

    def query(self, start, end, dims, metrics, filters=None, sort=None, max_results=200):
        self.calls.append((start, end, dims, metrics))
        self.caps = getattr(self, 'caps', []) + [max_results]
        return self.by_dims.get(dims, [])


def ctx(by_dims):
    return CollectContext("soombi", CH, FakeAnalytics(by_dims), None, TODAY, NOW)


def full():
    return {
        Q1: [
            {"day": "2026-11-01", "views": 100, "subscribersGained": 4, "subscribersLost": 1},
            {"day": "2026-11-02", "views": 80, "subscribersGained": 0, "subscribersLost": 2},
        ],
        Q2: [
            {"day": "2026-11-01", "creatorContentType": "shorts", "estimatedMinutesWatched": 30,
             "views": 60, "engagedViews": 50, "subscribersGained": 3},
            {"day": "2026-11-01", "creatorContentType": "videoOnDemand", "estimatedMinutesWatched": 200,
             "views": 30, "engagedViews": 25, "subscribersGained": 1},
            {"day": "2026-11-01", "creatorContentType": "liveStream", "estimatedMinutesWatched": 500,
             "views": 10, "engagedViews": 9, "subscribersGained": 0},
            {"day": "2026-11-02", "creatorContentType": "shorts", "estimatedMinutesWatched": 12,
             "views": 70, "engagedViews": 66, "subscribersGained": 0},
        ],
        Q3: [
            {"day": "2026-11-01", "liveOrOnDemand": "LIVE", "estimatedMinutesWatched": 480},
            {"day": "2026-11-01", "liveOrOnDemand": "ON_DEMAND", "estimatedMinutesWatched": 250},
            {"day": "2026-11-02", "liveOrOnDemand": "ON_DEMAND", "estimatedMinutesWatched": 12},
        ],
        Q5: [
            {"creatorContentType": "liveStream", "estimatedMinutesWatched": 1500},
            {"creatorContentType": "shorts", "estimatedMinutesWatched": 70},
            {"creatorContentType": "videoOnDemand", "estimatedMinutesWatched": 9},
        ],
    }


def test_channel_daily_merges_three_queries():
    out = channel_daily.collect(ctx(full()), date(2026, 11, 1), date(2026, 11, 2))
    rows = out["yt_channel_daily"]
    assert [r["day"] for r in rows] == [date(2026, 11, 1), date(2026, 11, 2)]
    assert rows[0] == {
        "channel_key": "soombi", "day": date(2026, 11, 1), "views": 100,
        "min_shorts": 30, "min_live": 500, "min_vod": 200, "min_unspec": 0,
        "min_lol_live": 480, "min_lol_ondemand": 250,
        "subs_gained": 4, "subs_lost": 1,
        "views_shorts": 60, "engaged_views_shorts": 50, "subs_gained_shorts": 3,
        "collected_at": NOW,
    }
    d2 = rows[1]
    assert (d2["views"], d2["subs_gained"], d2["subs_lost"]) == (80, 0, 2)
    assert (d2["min_shorts"], d2["min_live"], d2["min_vod"]) == (12, 0, 0)
    assert (d2["min_lol_live"], d2["min_lol_ondemand"]) == (0, 12)


def test_channel_daily_missing_query_leaves_none():
    data = full()
    data[Q3] = []
    data[Q2] = [r for r in data[Q2] if r["day"] == "2026-11-01"]
    rows = channel_daily.collect(ctx(data), date(2026, 11, 1), date(2026, 11, 2))["yt_channel_daily"]
    d2 = rows[1]
    assert d2["views"] == 80 and d2["subs_lost"] == 2
    for col in ("min_shorts", "min_live", "min_vod", "min_unspec", "views_shorts",
                "engaged_views_shorts", "subs_gained_shorts", "min_lol_live", "min_lol_ondemand"):
        assert d2[col] is None, col
    assert rows[0]["min_lol_live"] is None


def test_yearly_minutes_row():
    c = ctx(full())
    out = channel_daily.collect(c, date(2026, 11, 1), date(2026, 11, 2))
    assert out["yt_yearly_minutes"] == [{
        "channel_key": "soombi", "as_of": TODAY, "min_live": 1500, "min_vod": 9,
        "min_shorts": 70, "start_day": date(2025, 11, 7), "end_day": date(2026, 11, 6),
    }]
    yearly_call = [x for x in c.analytics.calls if x[2] == Q5][0]
    assert yearly_call[:2] == (date(2025, 11, 7), date(2026, 11, 6))
    assert channel_daily.yearly_minutes(c)["min_live"] == 1500


def test_all_queries_request_1000_rows():
    # 90-day backfill: day x creatorContentType can reach 360 rows, above the 200 default.
    c = ctx(full())
    channel_daily.collect(c, date(2026, 11, 1), date(2026, 11, 2))
    assert len(c.analytics.caps) >= 4 and set(c.analytics.caps) == {1000}
