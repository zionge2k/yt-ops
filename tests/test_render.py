import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from ytops import registry, render

UTC = timezone.utc
TODAY = date(2026, 11, 7)
LATEST = date(2026, 11, 4)
KEYS = {"v", "generated_at", "latest_day", "lag_days", "order", "channels", "board",
        "subs_trend", "watch_trend", "detail", "errors"}


def _day_row(key, day, **kw):
    r = {"channel_key": key, "day": day, "views": None, "min_live": None, "min_vod": None,
         "min_lol_live": None, "min_lol_ondemand": None, "subs_gained": None, "subs_lost": None,
         "views_shorts": None, "engaged_views_shorts": None, "subs_gained_shorts": None,
         "subs_gained_vod": None, "subs_gained_live": None,
         "min_shorts": None, "min_unspec": None, "collected_at": None}
    r.update(kw)
    return r


def _daily():
    # soombi: 10 days to LATEST, 60 min live + 60 min vod a day (2.0 h), except 11-03 (1.0 h)
    rows = []
    for i in range(10):
        d = LATEST - timedelta(days=i)
        rows.append(_day_row("soombi", d, views=100, min_live=Decimal(60), min_vod=Decimal(60 if d != date(2026, 11, 3) else 0),
                             min_shorts=Decimal(500), subs_gained=5, subs_lost=1, subs_gained_shorts=3,
                             subs_gained_vod=1, subs_gained_live=0))
    rows.append(_day_row("soombi", date(2026, 10, 1), views=7, subs_gained=2, subs_lost=0))
    # a2p: behind the global latest day by one day
    rows.append(_day_row("a2p", date(2026, 11, 3), views=10, min_vod=Decimal(120)))
    return sorted(rows, key=lambda r: r["day"])


def _audience_rows():
    base = {"channel_key": "soombi", "as_of": date(2026, 11, 6)}
    old = {"channel_key": "soombi", "as_of": date(2026, 11, 1)}

    def r(segment, content, dim, key, views=None, minutes=None, pct=None, b=base):
        return {**b, "segment": segment, "content": content, "dim": dim, "key": key,
                "views": views, "minutes": minutes, "pct": pct}

    return [
        r("unsubscribed", "vod", "weight", "videoOnDemand", views=300),
        r("unsubscribed", "live", "weight", "liveStream", views=100),
        r("unsubscribed", "vod", "age_gender", "age35-44/female", pct=Decimal("40")),
        r("unsubscribed", "vod", "age_gender", "age45-54/male", pct=Decimal("10")),
        r("unsubscribed", "live", "age_gender", "age35-44/female", pct=Decimal("80")),
        r("unsubscribed", "vod", "country", "KR", views=250, minutes=Decimal(900)),
        r("unsubscribed", "vod", "country", "US", views=50, minutes=Decimal(120)),
        r("unsubscribed", "live", "country", "KR", views=100, minutes=Decimal(600)),
        r("unsubscribed", "live", "country", "JP", views=10, minutes=Decimal(10)),
        # subscribed: vod only, no weight rows -> vod alone
        r("subscribed", "vod", "age_gender", "age55-64/female", pct=Decimal("70")),
        # stale as_of must be ignored
        r("unsubscribed", "vod", "country", "FR", views=9999, minutes=Decimal(99999), b=old),
    ]


ROWS = {
    "yt_channel_daily": _daily(),
    "yt_subs_snapshot": [{"channel_key": "soombi", "taken_on": date(2026, 11, 6),
                          "api_subscribers": 900, "exact_subscribers": 905, "monetized": False},
                         {"channel_key": "a2p", "taken_on": date(2026, 11, 6),
                          "api_subscribers": 1200, "exact_subscribers": None, "monetized": True}],
    "yt_live_snapshot": [
        {"channel_key": "soombi", "taken_at": datetime(2026, 11, 7, 1, tzinfo=UTC), "broadcast_id": "b1",
         "life_cycle": "live", "concurrent": 3, "health": "good", "stream_status": "active", "title": "x", "views": 100},
        {"channel_key": "soombi", "taken_at": datetime(2026, 11, 7, 1, tzinfo=UTC), "broadcast_id": "b2",
         "life_cycle": "live", "concurrent": None, "health": "good", "stream_status": "active", "title": "y", "views": 50},
        {"channel_key": "soombi", "taken_at": datetime(2026, 11, 7, 1, tzinfo=UTC), "broadcast_id": "b3",
         "life_cycle": "complete", "concurrent": 9, "health": None, "stream_status": None, "title": "z", "views": 9},
        {"channel_key": "soombi", "taken_at": datetime(2026, 11, 6, 1, tzinfo=UTC), "broadcast_id": "old",
         "life_cycle": "live", "concurrent": 99, "health": "good", "stream_status": "active", "title": "old", "views": 1},
        {"channel_key": "backthen", "taken_at": datetime(2026, 11, 7, 1, tzinfo=UTC), "broadcast_id": "none",
         "life_cycle": "none", "concurrent": None, "health": None, "stream_status": None, "title": None, "views": None},
    ],
    "yt_yearly_minutes": [{"channel_key": "soombi", "as_of": date(2026, 11, 4),
                           "min_live": Decimal(6000), "min_vod": Decimal(6000), "min_shorts": Decimal(99999)}],
    "yt_manual": [{"channel_key": "soombi", "field": "peak_hours", "value": Decimal(0), "as_of": date(2026, 11, 1),
                   "note": "평일 저녁"},
                  {"channel_key": "soombi", "field": "official_watch_hours_365", "value": Decimal(150),
                   "as_of": date(2026, 11, 1), "note": None}],
    "yt_run_log": [{"run_id": "r", "errors": [{"channel": "pliwav", "stage": "x"}]}],
    "yt_video_daily": [
        {"video_id": "L1", "channel_key": "soombi", "day": LATEST, "views": 10, "minutes": Decimal(600)},
        {"video_id": "L1", "channel_key": "soombi", "day": LATEST - timedelta(days=27), "views": 5, "minutes": Decimal(60)},
        {"video_id": "L2", "channel_key": "soombi", "day": LATEST, "views": 1, "minutes": Decimal(120)},
        {"video_id": "L3", "channel_key": "soombi", "day": LATEST, "views": 1, "minutes": Decimal(30)},
        {"video_id": "L4", "channel_key": "soombi", "day": LATEST, "views": 1, "minutes": Decimal(6)},
        {"video_id": "A1", "channel_key": "soombi", "day": LATEST, "views": 2, "minutes": Decimal(300)},
        {"video_id": "S1", "channel_key": "soombi", "day": LATEST, "views": 900, "minutes": Decimal(9000)},
    ],
    "yt_video": [
        {"video_id": v, "channel_key": "soombi", "title": f"t-{v}", "thumbnail_url": f"https://x/{v}.jpg",
         "published_at": datetime(2026, 10, 1, tzinfo=UTC), "content_kind": k}
        for v, k in (("L1", "long"), ("L2", "long"), ("L3", "long"), ("L4", "long"),
                     ("A1", "live_archive"), ("S1", "short"))
    ],
    "yt_playlist": [{"channel_key": "soombi", "playlist_id": "p1", "title": "Waltz", "item_count": 2},
                    {"channel_key": "soombi", "playlist_id": "p2", "title": "Jazz", "item_count": 2}],
    "yt_playlist_item": [{"playlist_id": "p1", "video_id": "L1", "channel_key": "soombi"},
                         {"playlist_id": "p1", "video_id": "S1", "channel_key": "soombi"},
                         {"playlist_id": "p2", "video_id": "L1", "channel_key": "soombi"},
                         {"playlist_id": "p2", "video_id": "A1", "channel_key": "soombi"}],
    "yt_audience": _audience_rows(),
}


def _table(sql):
    return sql.split(" from ", 1)[1].split()[0]


def _fake_fetch(conn, sql, params=()):
    if _table(sql) in ROWS:
        return ROWS[_table(sql)]
    raise AssertionError(sql)


def _cfg():
    return {"channels": registry.load_channels(), "thresholds": registry.load_thresholds()}


def _build(monkeypatch, **override):
    def fetch(conn, sql, params=()):
        if _table(sql) in override:
            return override[_table(sql)]
        return _fake_fetch(conn, sql, params)

    monkeypatch.setattr(render, "fetch", fetch)
    return json.loads(json.dumps(render.build(None, today=TODAY, config=_cfg()), default=render._json_default))


def test_v3_top_level_shape(monkeypatch):
    d = _build(monkeypatch)
    assert set(d) == KEYS and d["v"] == 3
    assert d["latest_day"] == "2026-11-04" and d["lag_days"] == 3
    assert d["order"] == list(render.ORDER) == [
        "soombi", "backthen", "urachacha", "a2p", "justsoombi", "soombicafe", "groovewav", "pliwav"]
    assert [c["key"] for c in d["channels"]] == d["order"]
    assert set(d["channels"][0]) == {"key", "display", "is_live", "collect_failed", "errors"}
    for section in ("board", "subs_trend", "watch_trend", "detail"):
        assert list(d[section]) == d["order"], section
    assert d["errors"] == [{"channel": "pliwav", "stage": "x", "run_started_at": None}]


def test_board_h48_and_subscribers(monkeypatch):
    b = _build(monkeypatch)["board"]["soombi"]
    assert set(b) == {"subscribers", "h48", "live", "health", "monet"}
    assert b["subscribers"] == 905  # exact wins over api
    # 11-03 (1.0h) + 11-04 (2.0h) = 3.0 vs 11-01 + 11-02 = 4.0 -> -25%
    assert b["h48"] == {"cur": 3.0, "prev": 4.0, "pct": -25.0, "status": "blue", "days": ["2026-11-03", "2026-11-04"]}
    a2p = _build(monkeypatch)["board"]["a2p"]
    assert a2p["subscribers"] == 1200  # api when exact is None
    # behind the global latest day: current window shown, no comparison
    assert a2p["h48"]["cur"] == 2.0 and a2p["h48"]["prev"] is None and a2p["h48"]["status"] == "grey"
    assert _build(monkeypatch)["board"]["groovewav"]["h48"]["cur"] is None


def test_board_live_state(monkeypatch):
    d = _build(monkeypatch)["board"]
    # newest taken_at only; broadcast b3 (complete) excluded; viewers sum skips None
    assert d["soombi"]["live"] == {"on": True, "dual": True, "count": 2, "viewers": 3, "views": 150,
                                   "title": "x", "taken_at": "2026-11-07T01:00:00+00:00"}
    assert d["backthen"]["live"] == {"on": False, "dual": False, "count": 0, "viewers": None, "views": None,
                                     "title": None, "taken_at": "2026-11-07T01:00:00+00:00"}
    assert d["justsoombi"]["live"]["taken_at"] is None and d["justsoombi"]["live"]["on"] is False
    assert d["urachacha"]["live"] is None  # not a live channel


def test_board_monet_and_health(monkeypatch):
    d = _build(monkeypatch)
    m = d["board"]["soombi"]["monet"]
    assert m == {"subs": 905, "subs_pct": 90.5, "hours": 200.0, "hours_pct": 5.0, "monetized": False}
    assert d["board"]["soombi"]["health"] == "blue"  # min(90.5, 5.0) < 30
    assert d["detail"]["soombi"]["monet"] == m
    assert d["board"]["a2p"]["health"] == "red"  # monetized wins
    assert d["board"]["groovewav"]["health"] == "grey" and d["board"]["groovewav"]["monet"]["subs"] is None


def test_health_of_thresholds():
    def m(s, h, mon=False):
        return {"subs_pct": s, "hours_pct": h, "monetized": mon}
    assert render.health_of(m(70, 80)) == "red"
    assert render.health_of(m(30, 100)) == "purple"
    assert render.health_of(m(100, 29.9)) == "blue"
    assert render.health_of(m(None, 50)) == "grey"
    assert render.health_of(m(None, None, True)) == "red"


def test_subs_trend_restores_totals(monkeypatch):
    d = _build(monkeypatch)["subs_trend"]["soombi"]
    assert set(d) == {"365", "14"}
    t = d["365"]
    assert t["start"] == "2026-10-01" and t["end"] == "2026-11-04"  # clamped to the first data day
    assert len(t["series"]) == 35
    last, prev = t["series"][-1], t["series"][-2]
    assert last == {"day": "2026-11-04", "total": 905, "net": 4}
    assert prev == {"day": "2026-11-03", "total": 901, "net": 4}
    # a day without data: net null, total carried (nothing subtracted)
    gap = next(s for s in t["series"] if s["day"] == "2026-10-20")
    assert gap["net"] is None and gap["total"] == 905 - 4 * 10
    first = t["series"][0]
    assert first["day"] == "2026-10-01" and first["net"] == 2 and first["total"] == 905 - 40
    assert t["total_net"] == 42 and t["status"] == "red"  # second half (all 10 days) vs first half (2)
    s14 = d["14"]
    assert s14["start"] == "2026-10-22" and len(s14["series"]) == 14 and s14["total_net"] == 40
    assert s14["series"][0] == {"day": "2026-10-22", "total": 865, "net": None}
    # no subscriber snapshot: totals null, nets still there
    g = _build(monkeypatch)["subs_trend"]["groovewav"]["14"]
    assert g["total_net"] is None and g["status"] == "grey" and all(s["total"] is None for s in g["series"])


def test_subs_trend_total_null_without_snapshot(monkeypatch):
    d = _build(monkeypatch, yt_subs_snapshot=[])["subs_trend"]["soombi"]["14"]
    assert all(s["total"] is None for s in d["series"]) and d["series"][-1]["net"] == 4


def test_watch_trend_windows(monkeypatch):
    w = _build(monkeypatch)["watch_trend"]["soombi"]
    assert set(w) == {"365", "28", "7"}
    assert w["7"]["start"] == "2026-10-29" and w["7"]["end"] == "2026-11-04"
    assert [s["hours"] for s in w["7"]["series"]] == [2.0, 2.0, 2.0, 2.0, 2.0, 1.0, 2.0]
    assert w["7"]["total"] == 13.0 and w["7"]["status"] == "blue"
    # 7 days: middle day dropped; first 3 mean (2+2+2)/3 = 2.0, last 3 mean (2+1+2)/3 = 1.667 -> -16.7% -> blue
    assert w["28"]["total"] == 19.0 and len(w["28"]["series"]) == 28 and w["28"]["series"][0]["hours"] is None
    assert w["365"]["start"] == "2026-10-01" and len(w["365"]["series"]) == 35
    # shorts minutes never count
    assert w["28"]["total"] < 100
    e = _build(monkeypatch)["watch_trend"]["groovewav"]["7"]
    assert e["total"] is None and e["status"] == "grey" and len(e["series"]) == 7


def test_detail_top_videos_and_genres(monkeypatch):
    dt = _build(monkeypatch)["detail"]["soombi"]
    assert set(dt) == {"monet", "audience", "top_long", "top_live", "subs_sources", "genres"}
    assert [v["video_id"] for v in dt["top_long"]] == ["L1", "L2", "L3"]  # top 3 by minutes, shorts excluded
    assert dt["top_long"][0] == {"video_id": "L1", "title": "t-L1", "thumb": "https://x/L1.jpg",
                                 "published_at": "2026-10-01T00:00:00+00:00", "hours": 11.0, "views": 15}
    assert [v["video_id"] for v in dt["top_live"]] == ["A1"] and dt["top_live"][0]["hours"] == 5.0
    # genres: L1 counts in both playlists, S1 (short) never, total = 660 + 960 = 1620 min
    assert dt["genres"] == [{"name": "Jazz", "hours": 16.0, "share": 59.3},
                            {"name": "Waltz", "hours": 11.0, "share": 40.7}]
    assert _build(monkeypatch)["detail"]["a2p"]["genres"] == []
    assert _build(monkeypatch)["detail"]["a2p"]["top_long"] == []


def test_detail_subs_sources(monkeypatch):
    s = _build(monkeypatch)["detail"]["soombi"]["subs_sources"]
    # 28-day window, 10 days with data x (5 gained: 3 shorts, 1 vod, 0 live -> 1 other), 10 lost
    assert s == {"days": 10, "shorts": 30, "vod": 10, "live": 0, "other": 10, "lost": 10}
    assert _build(monkeypatch)["detail"]["groovewav"]["subs_sources"] == {
        "days": 0, "shorts": None, "vod": None, "live": None, "other": None, "lost": None}


def test_subs_sources_skip_days_without_split(monkeypatch):
    # 10 days with the full split (5 gained = 3 shorts + 1 vod + 0 live + 1 other) and 18 older
    # days from before the split columns existed (gained 5, split None): they must not inflate "other"
    rows = list(_daily())
    for i in range(10, 28):
        rows.append(_day_row("soombi", LATEST - timedelta(days=i), views=1, subs_gained=5, subs_lost=1))
    s = _build(monkeypatch, yt_channel_daily=sorted(rows, key=lambda r: r["day"]))["detail"]["soombi"]["subs_sources"]
    assert s["days"] == 10 and s["other"] == 10 and s["shorts"] == 30 and s["vod"] == 10 and s["live"] == 0


def test_detail_audience(monkeypatch):
    a = _build(monkeypatch)["detail"]["soombi"]["audience"]
    assert set(a) == {"subscribers", "viewers"}
    v = a["viewers"]
    assert v["as_of"] == "2026-11-06" and v["peak_hours"] is None
    # weighted: vod 300 / live 100 -> 35-44 female = (40*300 + 80*100)/400 = 50 ; 45-54 male = 10*300/400 = 7.5
    assert v["age_gender"] == [{"age": "age35-44", "gender": "female", "pct": 50.0},
                               {"age": "age45-54", "gender": "male", "pct": 7.5}]
    # country: vod + live merged, by minutes, stale as_of dropped
    assert v["country"] == [{"country": "KR", "views": 350, "minutes": 1500.0},
                            {"country": "US", "views": 50, "minutes": 120.0},
                            {"country": "JP", "views": 10, "minutes": 10.0}]
    s = a["subscribers"]
    assert s["peak_hours"] == "평일 저녁"
    assert s["age_gender"] == [{"age": "age55-64", "gender": "female", "pct": 70.0}] and s["country"] == []
    empty = _build(monkeypatch)["detail"]["a2p"]["audience"]["viewers"]
    assert empty == {"age_gender": [], "country": [], "peak_hours": None, "as_of": None}


def test_collect_failed_flag_from_run_log(monkeypatch):
    log = [{"run_id": "r", "errors": [
        {"channel": "a2p", "stage": "client", "error": "TokenExpired"},
        {"channel": "pliwav", "stage": "channel_daily", "error": "HttpError"},
        {"channel": "backthen", "stage": "live", "error": "HttpError"},
        {"channel": "groovewav", "stage": "store:yt_channel_daily", "error": "OperationalError"}]}]
    d = _build(monkeypatch, yt_run_log=log)
    flags = {c["key"]: c["collect_failed"] for c in d["channels"]}
    assert flags["a2p"] is True and flags["pliwav"] is True
    assert flags["groovewav"] is True
    assert flags["backthen"] is False and flags["soombi"] is False


def test_failed_channel_has_no_h48_comparison(monkeypatch):
    log = [{"run_id": "r", "errors": [{"channel": "soombi", "stage": "channel_daily", "error": "HttpError"}]}]
    h = _build(monkeypatch, yt_run_log=log)["board"]["soombi"]["h48"]
    assert h["cur"] == 3.0 and h["prev"] is None and h["pct"] is None and h["status"] == "grey"


def test_collect_failed_uses_last_run_covering_channel(monkeypatch):
    t1, t2 = datetime(2026, 11, 6, 0, 30, tzinfo=UTC), datetime(2026, 11, 7, 0, 30, tzinfo=UTC)
    log = [  # newest first, as the query returns them
        {"run_id": "r2", "started_at": t2, "channels": ["soombi"], "errors": []},
        {"run_id": "r1", "started_at": t1, "channels": ["a2p", "soombi"],
         "errors": [{"channel": "a2p", "stage": "client", "error": "TokenExpired", "message": "m"}]},
    ]
    d = _build(monkeypatch, yt_run_log=log)
    flags = {c["key"]: c["collect_failed"] for c in d["channels"]}
    assert flags["a2p"] is True and flags["soombi"] is False
    assert d["errors"] == [{"channel": "a2p", "stage": "client", "error": "TokenExpired",
                            "message": "m", "run_started_at": t1.isoformat()}]


def test_run_without_channels_value_covers_every_channel(monkeypatch):
    log = [{"run_id": "old", "started_at": datetime(2026, 11, 6, tzinfo=UTC), "channels": None,
            "errors": [{"channel": "a2p", "stage": "client", "error": "E", "message": "m"}]}]
    d = _build(monkeypatch, yt_run_log=log)
    flags = {c["key"]: c["collect_failed"] for c in d["channels"]}
    assert flags["a2p"] is True and flags["soombi"] is False


def test_missing_v3_tables_do_not_stop_render(monkeypatch):
    def fetch(conn, sql, params=()):
        if _table(sql) in ("yt_audience", "yt_playlist", "yt_playlist_item", "yt_video", "yt_video_daily"):
            raise RuntimeError("relation does not exist")
        return _fake_fetch(conn, sql, params)

    monkeypatch.setattr(render, "fetch", fetch)
    d = json.loads(json.dumps(render.build(None, today=TODAY, config=_cfg()), default=render._json_default))
    dt = d["detail"]["soombi"]
    assert dt["top_long"] == [] and dt["genres"] == []
    assert dt["audience"]["viewers"]["age_gender"] == []
    assert d["board"]["soombi"]["subscribers"] == 905


def test_empty_db(monkeypatch):
    d = _build(monkeypatch, **{t: [] for t in ROWS})
    assert d["latest_day"] is None and d["lag_days"] is None
    b = d["board"]["soombi"]
    assert b["h48"] == {"cur": None, "prev": None, "pct": None, "status": "grey", "days": []}
    assert d["subs_trend"]["soombi"]["365"]["series"] == [] and d["watch_trend"]["soombi"]["7"]["total"] is None
