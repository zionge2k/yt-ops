from datetime import date, datetime, timezone

from tests.fakes import fixture
from ytops.collect import video
from ytops.collect.context import CollectContext
from ytops.registry import Channel
from ytops.videos import content_kind, duration_seconds

CH = Channel("soombi", "soombi", "UC1", False, 0, 0, "chalna")
TODAY = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 1, 0, tzinfo=timezone.utc)


class FakeData:
    def __init__(self, items):
        self.items, self.upload_calls = items, 0

    def uploads(self, max_items=None):
        self.upload_calls += 1
        return self.items


def test_content_kind_short_long_live_unknown():
    def item(d, live=False):
        i = {"contentDetails": {"duration": d}}
        if live:
            i["liveStreamingDetails"] = {"actualStartTime": "2026-11-03T12:00:00Z"}
        return i

    assert content_kind(item("PT17S")) == "short"
    assert content_kind(item("PT3M")) == "short"
    assert content_kind(item("PT3M1S")) == "long"
    assert content_kind(item("PT1H2M3S")) == "long"
    assert content_kind(item("P0D", live=True)) == "live_archive"
    assert content_kind(item("PT17S", live=True)) == "live_archive"
    assert content_kind(item("garbage")) == "unknown"
    assert content_kind({}) == "unknown"
    assert duration_seconds("PT1H2M3S") == 3723
    assert duration_seconds("P0D") == 0
    assert duration_seconds("PT") is None
    assert duration_seconds("") is None


def test_video_rows_from_fixture():
    data = FakeData(fixture("videos_list.json")["items"])
    c = CollectContext("soombi", CH, None, data, TODAY, NOW)
    rows = video.collect(c, TODAY, TODAY)["yt_video"]
    assert data.upload_calls == 1
    assert len(rows) == 4
    assert rows[0] == {
        "video_id": "vid00001", "channel_key": "soombi", "title": "Scheduled long",
        "published_at": datetime(2026, 11, 5, tzinfo=timezone.utc),
        "publish_at": datetime(2026, 11, 10, 9, tzinfo=timezone.utc),
        "privacy": "private", "duration_s": 3723, "content_kind": "long",
        "thumbnail_url": "https://example.test/vid00001.jpg", "last_seen_at": NOW,
    }
    assert rows[1]["publish_at"] is None
    assert (rows[1]["duration_s"], rows[1]["content_kind"]) == (17, "short")
    assert (rows[2]["duration_s"], rows[2]["content_kind"]) == (0, "live_archive")
    assert (rows[3]["duration_s"], rows[3]["content_kind"]) == (8994, "long")
