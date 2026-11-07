from datetime import date, datetime, timezone

from ytops.collect import playlists
from ytops.collect.context import CollectContext
from ytops.registry import Channel

CH = Channel("soombi", "soombi", "UC1", True, 0, 0, "chalna")
TODAY = date(2026, 11, 7)
NOW = datetime(2026, 11, 7, 1, 0, tzinfo=timezone.utc)


class FakeData:
    def __init__(self, lists, items):
        self._lists, self._items = lists, items
        self.calls = []

    def playlists(self):
        return self._lists

    def playlist_items(self, playlist_id):
        self.calls.append(playlist_id)
        return self._items.get(playlist_id, [])


def _item(vid):
    return {"contentDetails": {"videoId": vid}}


def test_playlists_rows_and_items():
    data = FakeData(
        [{"id": "pl1", "snippet": {"title": "Waltz"}, "contentDetails": {"itemCount": 2}},
         {"id": "pl2", "snippet": {"title": "Jazz"}, "contentDetails": {"itemCount": 0}}],
        {"pl1": [_item("v1"), _item("v2"), _item("v1"), {"contentDetails": {}}]},
    )
    c = CollectContext("soombi", CH, None, data, TODAY, NOW)
    out = playlists.collect(c, TODAY, TODAY)
    assert out["yt_playlist"] == [
        {"channel_key": "soombi", "playlist_id": "pl1", "title": "Waltz", "item_count": 2, "seen_at": NOW},
        {"channel_key": "soombi", "playlist_id": "pl2", "title": "Jazz", "item_count": 0, "seen_at": NOW},
    ]
    # duplicate video and item without videoId are dropped
    assert out["yt_playlist_item"] == [
        {"playlist_id": "pl1", "video_id": "v1", "channel_key": "soombi"},
        {"playlist_id": "pl1", "video_id": "v2", "channel_key": "soombi"},
    ]
    assert data.calls == ["pl1", "pl2"]


def test_playlists_empty():
    c = CollectContext("soombi", CH, None, FakeData([], {}), TODAY, NOW)
    assert playlists.collect(c, TODAY, TODAY) == {"yt_playlist": [], "yt_playlist_item": []}


def test_truncated_playlist_raises_instead_of_partial():
    import pytest
    data = FakeData(
        [{"id": "pl1", "snippet": {"title": "Big"}, "contentDetails": {"itemCount": 120}}],
        {"pl1": [_item(f"v{i}") for i in range(50)]},
    )
    c = CollectContext("soombi", CH, None, data, TODAY, NOW)
    with pytest.raises(RuntimeError, match="playlist pl1 truncated: 50/120"):
        playlists.collect(c, TODAY, TODAY)


def test_small_shortfall_is_tolerated():
    # real legacy playlist: itemCount 3 but the API lists 2 (private/deleted videos)
    data = FakeData(
        [{"id": "pl1", "snippet": {"title": "Old"}, "contentDetails": {"itemCount": 3}}],
        {"pl1": [_item("v1"), _item("v2")]},
    )
    c = CollectContext("soombi", CH, None, data, TODAY, NOW)
    out = playlists.collect(c, TODAY, TODAY)
    assert len(out["yt_playlist_item"]) == 2


def test_duplicate_items_are_not_truncation():
    # itemCount counts a video listed twice: 20 listed, 3 of them repeats -> 17 distinct, not truncated
    listed = [_item(f"v{i}") for i in range(17)] + [_item("v0"), _item("v1"), _item("v2")]
    data = FakeData(
        [{"id": "pl1", "snippet": {"title": "Dup"}, "contentDetails": {"itemCount": 20}}],
        {"pl1": listed},
    )
    c = CollectContext("soombi", CH, None, data, TODAY, NOW)
    out = playlists.collect(c, TODAY, TODAY)
    assert len(out["yt_playlist_item"]) == 17
