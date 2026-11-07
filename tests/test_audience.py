from datetime import date, datetime, timezone

from ytops.collect import audience
from ytops.collect.context import CollectContext
from ytops.registry import Channel

CH = Channel("soombi", "soombi", "UC1", True, 0, 0, "chalna")
TODAY = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 1, 0, tzinfo=timezone.utc)


class FakeAnalytics:
    def __init__(self, answers):
        self.answers = answers  # (dims, filters) -> rows
        self.calls = []

    def query(self, start, end, dims, metrics, filters=None, sort=None, max_results=200, top_n=False):
        self.calls.append(dict(start=start, end=end, dims=dims, metrics=metrics, filters=filters,
                               sort=sort, max_results=max_results, top_n=top_n))
        return self.answers.get((dims, filters), [])


def _ctx(answers):
    return CollectContext("soombi", CH, FakeAnalytics(answers), None, TODAY, NOW)


def test_audience_rows_from_fixture_like_answers():
    sub_vod = "subscribedStatus==SUBSCRIBED;creatorContentType==videoOnDemand"
    answers = {
        ("creatorContentType", "subscribedStatus==SUBSCRIBED"): [
            {"creatorContentType": "videoOnDemand", "views": 300},
            {"creatorContentType": "liveStream", "views": 100},
            {"creatorContentType": "shorts", "views": 999}],
        ("ageGroup,gender", sub_vod): [
            {"ageGroup": "age35-44", "gender": "female", "viewerPercentage": 40.5},
            {"ageGroup": "age45-54", "gender": "male", "viewerPercentage": 10.0}],
        ("country", sub_vod): [{"country": "KR", "views": 250, "estimatedMinutesWatched": 900.5},
                               {"country": "US", "views": 50, "estimatedMinutesWatched": 120}],
    }
    c = _ctx(answers)
    rows = audience.collect(c, TODAY, TODAY)["yt_audience"]
    base = {"channel_key": "soombi", "as_of": TODAY}
    assert {"segment": "subscribed", "content": "vod", "dim": "age_gender", "key": "age35-44/female",
            "views": None, "minutes": None, "pct": 40.5, **base} in rows
    assert {"segment": "subscribed", "content": "vod", "dim": "country", "key": "KR",
            "views": 250, "minutes": 900.5, "pct": None, **base} in rows
    assert {"segment": "subscribed", "content": "vod", "dim": "weight", "key": "videoOnDemand",
            "views": 300, "minutes": None, "pct": None, **base} in rows
    assert {"segment": "subscribed", "content": "live", "dim": "weight", "key": "liveStream",
            "views": 100, "minutes": None, "pct": None, **base} in rows
    # shorts weight is not stored; unsubscribed answers are empty -> no rows, no error
    assert not [r for r in rows if r["key"] == "shorts"]
    assert not [r for r in rows if r["segment"] == "unsubscribed"]
    assert len(rows) == 2 + 2 + 2
    # primary key is unique
    assert len({(r["segment"], r["content"], r["dim"], r["key"]) for r in rows}) == len(rows)


def test_audience_queries_window_and_filters():
    c = _ctx({})
    audience.collect(c, TODAY, TODAY)
    calls = c.analytics.calls
    assert all(k["start"] == date(2026, 10, 7) and k["end"] == date(2026, 11, 6) for k in calls)
    # 2 segments x (1 weight + 2 contents x 2 queries) = 10 queries
    assert len(calls) == 10
    country = [k for k in calls if k["dims"] == "country"]
    assert all(k["sort"] == "-estimatedMinutesWatched" and k["max_results"] == 25 and k["top_n"] for k in country)
    assert {k["filters"] for k in country} == {
        "subscribedStatus==SUBSCRIBED;creatorContentType==videoOnDemand",
        "subscribedStatus==SUBSCRIBED;creatorContentType==liveStream",
        "subscribedStatus==UNSUBSCRIBED;creatorContentType==videoOnDemand",
        "subscribedStatus==UNSUBSCRIBED;creatorContentType==liveStream",
    }
    ag = [k for k in calls if k["dims"] == "ageGroup,gender"]
    assert all(k["metrics"] == "viewerPercentage" and k["sort"] == "-viewerPercentage" for k in ag)
    weight = [k for k in calls if k["dims"] == "creatorContentType"]
    assert [k["filters"] for k in weight] == ["subscribedStatus==SUBSCRIBED", "subscribedStatus==UNSUBSCRIBED"]
