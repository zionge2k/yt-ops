from fakes import FakeService, fixture
from ytops.data import DataClient

CHANNEL = {"items": [{"id": "chan0001", "contentDetails": {"relatedPlaylists": {"uploads": "upl0001"}},
                      "statistics": {"subscriberCount": "10"}}]}


def client(svc):
    return DataClient(svc, sleep=lambda s: None)


def _pl(start, n, token=None):
    d = {"items": [{"contentDetails": {"videoId": f"vid{i:05d}"}} for i in range(start, start + n)]}
    if token:
        d["nextPageToken"] = token
    return d


def _vids(ids):
    return {"items": [{"id": i} for i in ids.split(",")]}


def test_channel_stats():
    svc = FakeService(channels__list=[CHANNEL])
    assert client(svc).channel_stats()["statistics"]["subscriberCount"] == "10"
    assert svc.kwargs("channels.list")[0] == dict(part="snippet,statistics,contentDetails,status", mine=True)


def test_uploads_batches_50():
    svc = FakeService(
        channels__list=[CHANNEL],
        playlistItems__list=[_pl(0, 50, "t1"), _pl(50, 50, "t2"), _pl(100, 20)],
        videos__list=[_vids(",".join(f"vid{i:05d}" for i in range(0, 50))),
                      _vids(",".join(f"vid{i:05d}" for i in range(50, 100))),
                      _vids(",".join(f"vid{i:05d}" for i in range(100, 120)))],
    )
    items = client(svc).uploads()
    assert len(items) == 120
    assert svc.kwargs("channels.list")[0] == dict(part="contentDetails", mine=True)
    pl = svc.kwargs("playlistItems.list")
    assert [kw.get("pageToken") for kw in pl] == [None, "t1", "t2"]
    assert all(kw["playlistId"] == "upl0001" and kw["maxResults"] == 50 for kw in pl)
    vl = svc.kwargs("videos.list")
    assert [len(kw["id"].split(",")) for kw in vl] == [50, 50, 20]
    assert vl[0]["part"] == "snippet,contentDetails,status,liveStreamingDetails,statistics"


def test_uploads_max_items_stops_early():
    svc = FakeService(
        channels__list=[CHANNEL],
        playlistItems__list=[_pl(0, 50, "t1")],
        videos__list=[_vids(",".join(f"vid{i:05d}" for i in range(30)))],
    )
    items = client(svc).uploads(max_items=30)
    assert len(items) == 30
    assert len(svc.kwargs("playlistItems.list")) == 1
    assert len(svc.kwargs("videos.list")[0]["id"].split(",")) == 30


def test_videos_fixture_shapes():
    data = fixture("videos_list.json")
    svc = FakeService(videos__list=[data])
    items = client(svc).videos(["vid00001", "vid00002", "vid00003", "vid00004"])
    assert [i["contentDetails"]["duration"] for i in items] == ["PT1H2M3S", "PT17S", "P0D", "PT2H29M54S"]
    assert items[0]["status"]["publishAt"]
    assert svc.kwargs("videos.list")[0]["id"] == "vid00001,vid00002,vid00003,vid00004"


def test_active_broadcasts_has_no_mine_param():
    svc = FakeService(liveBroadcasts__list=[fixture("broadcasts_active.json")])
    items = client(svc).active_broadcasts()
    assert items[0]["id"] == "bcast0001"
    kw = svc.kwargs("liveBroadcasts.list")[0]
    assert "mine" not in kw
    assert kw == dict(part="snippet,contentDetails,status", broadcastStatus="active", maxResults=5)


def test_stream_health():
    svc = FakeService(liveStreams__list=[fixture("livestreams_status.json"), {}])
    c = client(svc)
    assert c.stream_health("strm0001")["healthStatus"]["status"] == "good"
    assert svc.kwargs("liveStreams.list")[0] == dict(part="status", id="strm0001")
    assert c.stream_health("none") == {}


def _ids(a, b):
    return ",".join(f"vid{i:05d}" for i in range(a, b))


def test_playlists_joins_pages():
    p1 = {"items": [{"id": "pl1", "snippet": {"title": "Waltz"}, "contentDetails": {"itemCount": 2}}],
          "nextPageToken": "t1"}
    p2 = {"items": [{"id": "pl2", "snippet": {"title": "Jazz"}, "contentDetails": {"itemCount": 0}}]}
    svc = FakeService(playlists__list=[p1, p2])
    got = client(svc).playlists()
    assert [p["id"] for p in got] == ["pl1", "pl2"]
    kw = svc.kwargs("playlists.list")
    assert [k.get("pageToken") for k in kw] == [None, "t1"]
    assert kw[0]["part"] == "snippet,contentDetails" and kw[0]["mine"] is True and kw[0]["maxResults"] == 50


def test_playlist_items_joins_pages():
    svc = FakeService(playlistItems__list=[_pl(0, 50, "t1"), _pl(50, 3)])
    got = client(svc).playlist_items("pl1")
    assert len(got) == 53 and got[-1]["contentDetails"]["videoId"] == "vid00052"
    kw = svc.kwargs("playlistItems.list")
    assert all(k["playlistId"] == "pl1" and k["part"] == "contentDetails" for k in kw)
    assert [k.get("pageToken") for k in kw] == [None, "t1"]


def test_uploads_pages_do_not_repeat():
    svc = FakeService(
        channels__list=[CHANNEL],
        playlistItems__list=[_pl(0, 50, "t1"), _pl(50, 50, "t2"), _pl(100, 20)],
        videos__list=[_vids(_ids(0, 50)), _vids(_ids(50, 100)), _vids(_ids(100, 120))],
    )
    items = client(svc).uploads()
    assert len(svc.kwargs("playlistItems.list")) == 3
    assert len({i["id"] for i in items}) == len(items) == 120


def test_uploads_dedupes_ids():
    # playlist lists a video twice (across a page boundary and within a page)
    p1 = _pl(0, 50, "t1")
    p2 = _pl(49, 21)  # vid00049 repeated
    p2["items"].append({"contentDetails": {"videoId": "vid00010"}})
    svc = FakeService(
        channels__list=[CHANNEL],
        playlistItems__list=[p1, p2],
        videos__list=[_vids(_ids(0, 50)), _vids(_ids(50, 70))],
    )
    items = client(svc).uploads()
    sent = [i for kw in svc.kwargs("videos.list") for i in kw["id"].split(",")]
    assert len(sent) == len(set(sent)) == 70
    assert [i["id"] for i in items] == _ids(0, 70).split(",")


def test_pages_stop_when_token_repeats():
    # 2026-11-07: the API returned the same nextPageToken forever -> 8,684 calls in 10 minutes
    svc = FakeService(playlistItems__list=[_pl(0, 50, "same")] * 50)
    got = client(svc).playlist_items("pl1")
    assert len(svc.kwargs("playlistItems.list")) == 2
    assert len(got) == 100


def test_pages_stop_on_empty_page_even_with_new_token():
    # the 2026-11-07 playlist answered page 2 with zero items; a fresh token each time
    # must not keep us reading empty pages up to MAX_PAGES
    svc = FakeService(playlistItems__list=[_pl(0, 2, "t1")] + [_pl(0, 0, f"t{i}") for i in range(2, 20)])
    got = client(svc).playlist_items("pl1")
    assert len(svc.kwargs("playlistItems.list")) == 2
    assert len(got) == 2


def test_pages_cap_at_max_pages():
    from ytops import data
    pages = [_pl(i * 50, 50, f"t{i}") for i in range(data.MAX_PAGES + 10)]
    svc = FakeService(playlistItems__list=pages)
    client(svc).playlist_items("pl1")
    assert len(svc.kwargs("playlistItems.list")) == data.MAX_PAGES


def test_call_budget_raises():
    import pytest
    from ytops.data import CallBudgetExceeded
    svc = FakeService(channels__list=[CHANNEL] * 10)
    c = DataClient(svc, sleep=lambda s: None, call_budget=3)
    for _ in range(3):
        c.channel_stats()
    with pytest.raises(CallBudgetExceeded):
        c.channel_stats()
    assert c.calls == 3
