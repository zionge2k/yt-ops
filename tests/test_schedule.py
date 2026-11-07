from datetime import date, datetime, timezone

from tests.fakes import fixture
from ytops.collect import schedule
from ytops.collect.context import CollectContext
from ytops.registry import Channel

CH = Channel("soombi", "soombi", "UC1", False, 0, 0, "chalna")
TODAY = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 1, 0, tzinfo=timezone.utc)


class FakeData:
    def __init__(self, items):
        self.items = items

    def uploads(self, max_items=None):
        return self.items


def test_schedule_only_private_with_publish_at():
    items = fixture("videos_list.json")["items"]
    # private without publishAt must be skipped; earlier schedule must sort first
    items.append({"id": "vid00005", "snippet": {"title": "Private draft"},
                  "contentDetails": {"duration": "PT10S"}, "status": {"privacyStatus": "private"}})
    items.append({"id": "vid00006", "snippet": {"title": "Earlier short"},
                  "contentDetails": {"duration": "PT20S"},
                  "status": {"privacyStatus": "private", "publishAt": "2026-11-08T00:00:00Z"}})
    c = CollectContext("soombi", CH, None, FakeData(items), TODAY, NOW)
    rows = schedule.collect(c, TODAY, TODAY)["yt_schedule"]
    assert rows == [
        {"channel_key": "soombi", "video_id": "vid00006", "title": "Earlier short",
         "publish_at": datetime(2026, 11, 8, tzinfo=timezone.utc),
         "content_kind": "short", "seen_at": NOW},
        {"channel_key": "soombi", "video_id": "vid00001", "title": "Scheduled long",
         "publish_at": datetime(2026, 11, 10, 9, tzinfo=timezone.utc),
         "content_kind": "long", "seen_at": NOW},
    ]
