import json
from datetime import date, datetime, timezone
from decimal import Decimal

from ytops import registry, render

UTC = timezone.utc
TODAY = date(2026, 11, 7)


def _sched(day, kind, hour=3):
    return {"publish_at": datetime(2026, 11, day, hour, tzinfo=UTC), "content_kind": kind}


def test_period_summary_with_no_days():
    s = render.period_summary([], None, None, lambda r: r["views"], 5.0, -5.0)
    assert s == {"cur": None, "prev": None, "pct": None, "status": "grey", "spark": []}


def test_shortage_no_plan_no_warning():
    r = render.shortage(0, 0, [], TODAY)
    assert r["long"] == {"need": 0, "have": 0, "status": "none"}
    assert r["shorts"]["status"] == "none"


def test_shortage_short_when_under_plan():
    sched = [_sched(7, "long"), _sched(8, "short"), _sched(20, "short")]
    r = render.shortage(7, 2, sched, TODAY)
    assert r["long"] == {"need": 3, "have": 1, "status": "short"}
    assert r["shorts"] == {"need": 6, "have": 1, "status": "short"}
    ok = render.shortage(7, 0, [_sched(7, "long")] * 3, TODAY)
    assert ok["long"]["status"] == "ok"


def _fake_fetch(conn, sql, params=()):
    rows = {
        "yt_channel_daily": [
            {"channel_key": "soombi", "day": date(2026, 11, 4), "views": 100, "min_live": Decimal(60),
             "min_vod": Decimal(60), "min_lol_live": Decimal(120), "min_lol_ondemand": Decimal(30),
             "subs_gained": 5, "subs_lost": 1, "views_shorts": 50, "engaged_views_shorts": 25,
             "subs_gained_shorts": 2, "min_shorts": None, "min_unspec": None, "collected_at": None},
            {"channel_key": "soombi", "day": date(2026, 10, 25), "views": 80, "min_live": None,
             "min_vod": None, "min_lol_live": 0, "min_lol_ondemand": 0, "subs_gained": None,
             "subs_lost": None, "views_shorts": None, "engaged_views_shorts": None,
             "subs_gained_shorts": None, "min_shorts": None, "min_unspec": None, "collected_at": None},
        ],
        "yt_subs_snapshot": [{"channel_key": "soombi", "taken_on": date(2026, 11, 6),
                              "api_subscribers": 900, "exact_subscribers": 905}],
        "yt_schedule": [{"channel_key": "soombi", "video_id": "v", "title": "t",
                         "publish_at": datetime(2026, 11, 8, 3, tzinfo=UTC), "content_kind": "long"}],
        "yt_live_snapshot": [{"channel_key": "soombi", "taken_at": datetime(2026, 11, 7, 1, tzinfo=UTC),
                              "life_cycle": "live", "concurrent": 3, "health": "good",
                              "stream_status": "active", "title": "x"}],
        "yt_yearly_minutes": [{"channel_key": "soombi", "as_of": date(2026, 11, 4),
                               "min_live": Decimal(6000), "min_vod": Decimal(6000)}],
        "yt_manual": [{"channel_key": "soombi", "field": "official_watch_hours_365",
                       "value": Decimal(150), "as_of": date(2026, 11, 1)}],
        "yt_run_log": [{"run_id": "r", "errors": [{"channel": "a2p", "stage": "x"}]}],
    }
    for table, r in rows.items():
        if table in sql:
            return r
    raise AssertionError(sql)


def test_build_shape_from_fake_rows(monkeypatch):
    monkeypatch.setattr(render, "fetch", _fake_fetch)
    cfg = {"channels": registry.load_channels(), "thresholds": registry.load_thresholds()}
    d = json.loads(json.dumps(render.build(None, today=TODAY, config=cfg), default=render._json_default))
    assert set(d) == {"generated_at", "latest_day", "lag_days", "trust", "channels", "periods",
                      "live", "schedule", "monetization", "shorts", "errors"}
    assert d["latest_day"] == "2026-11-04" and d["lag_days"] == 3
    assert set(d["periods"]) == {"7", "28", "90"}
    p7 = d["periods"]["7"]
    assert set(p7) == {"start", "end", "prev_start", "prev_end", "channels"}
    m = p7["channels"]["soombi"]
    assert set(m) == {"views", "subs_net", "watch_hours"}
    assert m["views"]["cur"] == 100 and len(m["views"]["spark"]) == 7 and m["views"]["spark"][-1] == 100
    assert m["watch_hours"]["cur"] == 2.0 and m["subs_net"]["cur"] == 4
    assert d["periods"]["28"]["channels"]["soombi"]["views"]["cur"] == 180
    assert p7["channels"]["a2p"]["views"]["cur"] is None
    assert d["channels"][0]["subscribers"] == {"api": 900, "exact": 905}
    assert set(d["live"]) == {k for k, c in cfg["channels"].items() if c.is_live}
    assert d["live"]["soombi"]["hours_live"] == 2.0
    assert d["live"]["soombi"]["last_snapshot"]["life_cycle"] == "live"
    sc = d["schedule"]["soombi"]
    assert set(sc) == {"long", "shorts", "next_long", "next_shorts", "next7", "shortage"}
    assert sc["long"] == 1 and len(sc["next7"]) == 7 and sc["next7"][1]["long"] == 1
    mo = d["monetization"]["soombi"]
    assert mo["subs_exact"] == 905 and mo["subs_pct"] == 90.5 and mo["hours_approx"] == 200.0
    assert mo["hours_pct"] == 5.0 and mo["official"] == {"value": 150.0, "as_of": "2026-11-01"}
    assert d["shorts"]["soombi"] == {"views": 50, "engaged_ratio": 0.5, "subs_per_1k": 40.0}
    assert d["errors"] == [{"channel": "a2p", "stage": "x"}]
