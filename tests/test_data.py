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
    assert vl[0]["part"] == "snippet,contentDetails,status,liveStreamingDetails"


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
