from datetime import date, datetime, timezone

from tests.fakes import fixture, http_error
from ytops.collect import live
from ytops.collect.context import CollectContext
from ytops.registry import Channel

CH = Channel("soombi", "soombi", "UC1", True, 0, 0, "chalna")
TODAY = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 1, 0, tzinfo=timezone.utc)


class FakeData:
    def __init__(self, broadcasts, videos=(), health=None):
        self.broadcasts, self._videos, self.health = broadcasts, list(videos), health or {}
        self.calls = []

    def active_broadcasts(self):
        if isinstance(self.broadcasts, Exception):
            raise self.broadcasts
        return self.broadcasts

    def videos(self, ids):
        self.calls.append(("videos", ids))
        return self._videos

    def stream_health(self, stream_id):
        self.calls.append(("stream_health", stream_id))
        return self.health


def ctx(data):
    return CollectContext("soombi", CH, None, data, TODAY, NOW)


def test_live_none_row_when_no_broadcast():
    data = FakeData([])
    rows = live.collect(ctx(data), TODAY, TODAY)["yt_live_snapshot"]
    assert rows == [{
        "channel_key": "soombi", "taken_at": NOW, "broadcast_id": "none", "life_cycle": "none",
        "concurrent": None, "health": None, "stream_status": None, "actual_start": None,
        "title": None,
    }]
    assert data.calls == []


def _video(live_details):
    return {"id": "bcast0001", "liveStreamingDetails": live_details}


def test_live_active_row_from_fixtures():
    health = fixture("livestreams_status.json")["items"][0]["status"]
    data = FakeData(fixture("broadcasts_active.json")["items"],
                    [_video({"actualStartTime": "2026-11-07T01:00:00Z", "concurrentViewers": "42"})],
                    health)
    rows = live.collect(ctx(data), TODAY, TODAY)["yt_live_snapshot"]
    assert rows == [{
        "channel_key": "soombi", "taken_at": NOW, "broadcast_id": "bcast0001",
        "life_cycle": "live", "concurrent": 42, "health": "good", "stream_status": "active",
        "actual_start": datetime(2026, 11, 7, 1, tzinfo=timezone.utc), "title": "Live now",
    }]
    assert data.calls == [("videos", ["bcast0001"]), ("stream_health", "strm0001")]


def test_live_concurrent_none_not_zero():
    data = FakeData(fixture("broadcasts_active.json")["items"],
                    [_video({"actualStartTime": "2026-11-07T01:00:00Z"})], {})
    row = live.collect(ctx(data), TODAY, TODAY)["yt_live_snapshot"][0]
    assert row["concurrent"] is None
    assert (row["health"], row["stream_status"]) == (None, None)
    zero = FakeData(fixture("broadcasts_active.json")["items"], [_video({"concurrentViewers": "0"})])
    assert live.collect(ctx(zero), TODAY, TODAY)["yt_live_snapshot"][0]["concurrent"] == 0


def test_live_skips_api_when_not_live_channel():
    off = Channel("urachacha", "urachacha", "UC2", False, 0, 0, "morrow")
    data = FakeData(http_error(500))
    c = CollectContext("urachacha", off, None, data, TODAY, NOW)
    row = live.collect(c, TODAY, TODAY)["yt_live_snapshot"][0]
    assert (row["channel_key"], row["broadcast_id"], row["life_cycle"]) == ("urachacha", "none", "none")
    assert data.calls == []


def test_live_403_yields_none_row():
    rows = live.collect(ctx(FakeData(http_error(403, "liveStreamingNotEnabled"))), TODAY, TODAY)["yt_live_snapshot"]
    assert rows == [{
        "channel_key": "soombi", "taken_at": NOW, "broadcast_id": "none", "life_cycle": "none",
        "concurrent": None, "health": None, "stream_status": None, "actual_start": None,
        "title": None,
    }]


def test_live_other_http_error_propagates():
    import pytest
    from googleapiclient.errors import HttpError

    with pytest.raises(HttpError):
        live.collect(ctx(FakeData(http_error(500))), TODAY, TODAY)


def test_live_403_quota_propagates():
    import pytest
    from googleapiclient.errors import HttpError

    with pytest.raises(HttpError):
        live.collect(ctx(FakeData(http_error(403, "quotaExceeded"))), TODAY, TODAY)


def test_live_403_without_reason_propagates():
    import pytest
    from googleapiclient.errors import HttpError

    with pytest.raises(HttpError):
        live.collect(ctx(FakeData(http_error(403))), TODAY, TODAY)


def test_http_error_reason():
    assert live.http_error_reason(http_error(403, "quotaExceeded")) == "quotaExceeded"
    assert live.http_error_reason(http_error(403)) is None


def test_live_two_broadcasts_two_rows():
    items = fixture("broadcasts_active.json")["items"]
    second = {**items[0], "id": "bcast0002", "contentDetails": {}}
    data = FakeData([items[0], second], [_video({"concurrentViewers": "3"})])
    rows = live.collect(ctx(data), TODAY, TODAY)["yt_live_snapshot"]
    assert [r["broadcast_id"] for r in rows] == ["bcast0001", "bcast0002"]
    assert len({(r["channel_key"], r["taken_at"], r["broadcast_id"]) for r in rows}) == 2
