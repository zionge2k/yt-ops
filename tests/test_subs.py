from datetime import date, datetime, timezone

from ytops.collect import subs
from ytops.collect.context import CollectContext
from ytops.registry import Channel

CH = Channel("soombi", "soombi", "UC1", False, 0, 0, "chalna")
TODAY = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 1, 0, tzinfo=timezone.utc)


class FakeData:
    def __init__(self, stats):
        self.stats = stats

    def channel_stats(self):
        return self.stats


def ctx(stats):
    return CollectContext("soombi", CH, None, FakeData(stats), TODAY, NOW)


def test_subs_snapshot_row():
    stats = {"statistics": {"subscriberCount": "1230"}, "status": {"isChannelMonetizationEnabled": True}}
    out = subs.collect(ctx(stats), date(2026, 11, 1), date(2026, 11, 6))
    assert out == {"yt_subs_snapshot": [{
        "channel_key": "soombi", "taken_on": TODAY, "api_subscribers": 1230,
        "exact_subscribers": None, "monetized": True,
    }]}


def test_subs_snapshot_exact_under_1000_and_monetized_default():
    stats = {"statistics": {"subscriberCount": "742"}, "status": {}}
    row = subs.collect(ctx(stats), TODAY, TODAY)["yt_subs_snapshot"][0]
    assert row["api_subscribers"] == 742 and row["exact_subscribers"] == 742
    assert row["monetized"] is False


def test_snapshot_row_uses_baseline():
    stats = {"statistics": {"subscriberCount": "1000"}, "status": {}}
    row = subs.snapshot_row(ctx(stats), stats, baseline=(date(2026, 11, 1), 998),
                            daily=[(date(2026, 11, 2), 5, 1)], latest_day=date(2026, 11, 2))
    assert row["exact_subscribers"] == 1002
