from datetime import date, datetime, timezone
from types import SimpleNamespace

from ytops import runner

TODAY = date(2026, 11, 7)


def _fake_collector(rows_by_key):
    def collect(ctx, start, end):
        if ctx.analytics == "boom":
            raise RuntimeError("analytics down")
        return {"yt_channel_daily": rows_by_key(ctx)}
    return SimpleNamespace(collect=collect)


def _setup(monkeypatch, bad=()):
    monkeypatch.setattr(runner, "COLLECTORS", [("channel_daily", _fake_collector(
        lambda ctx: [{"channel_key": ctx.key, "day": date(2026, 11, 3), "views": 5, "collected_at": ctx.collected_at}]
    ))])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "boom" if k in bad else "ok")
    monkeypatch.setattr(runner, "data_for_key", lambda k: "data")
    monkeypatch.setattr(runner, "load_channels", lambda: {"soombi": "S", "a2p": "A"})


def test_collect_all_continues_after_channel_error(monkeypatch, capsys):
    _setup(monkeypatch, bad=("soombi",))
    res = runner.run_collect(["soombi", "a2p"], dry_run=True, today=TODAY)
    assert len(res.errors) == 1
    assert res.errors[0]["channel"] == "soombi" and res.errors[0]["stage"] == "channel_daily"
    assert res.errors[0]["error"] == "RuntimeError" and res.errors[0]["message"] == "analytics down"
    assert res.counts["yt_channel_daily"] > 0
    assert res.latest_day == date(2026, 11, 3)


def test_dry_run_touches_no_db(monkeypatch, capsys):
    _setup(monkeypatch)
    res = runner.run_collect(["a2p"], dry_run=True, conn=None, today=TODAY)
    out = capsys.readouterr().out
    assert "a2p yt_channel_daily: 1 rows" in out
    assert res.errors == []


def test_run_writes_upserts_and_run_log(monkeypatch):
    _setup(monkeypatch)
    calls = []
    monkeypatch.setattr(runner.store, "upsert", lambda conn, table, rows, pk, keep=(): calls.append((table, len(rows), tuple(pk), keep)) or len(rows))
    runner.run_collect(["a2p"], dry_run=False, conn=object(), today=TODAY)
    assert ("yt_channel_daily", 1, ("channel_key", "day"), ()) in calls
    assert calls[-1][0] == "yt_run_log"


def test_video_first_seen_filled(monkeypatch):
    monkeypatch.setattr(runner, "COLLECTORS", [("video", SimpleNamespace(
        collect=lambda ctx, s, e: {"yt_video": [{"video_id": "v", "last_seen_at": ctx.collected_at}]}))])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "load_channels", lambda: {"a2p": "A"})
    seen = {}
    monkeypatch.setattr(runner.store, "upsert", lambda conn, t, rows, pk, keep=(): seen.setdefault(t, (rows, keep)) and len(rows))
    runner.run_collect(["a2p"], dry_run=False, conn=object(), today=TODAY)
    rows, keep = seen["yt_video"]
    assert rows[0]["first_seen_at"] == rows[0]["last_seen_at"] and keep == ("first_seen_at",)


def test_subs_inputs_from_fake_fetch():
    answers = [
        [{"taken_on": date(2026, 9, 1), "api_subscribers": 950}],
        [{"day": date(2026, 9, 2), "subs_gained": 3, "subs_lost": 1},
         {"day": date(2026, 9, 3), "subs_gained": 2, "subs_lost": 0}],
        [{"latest": date(2026, 9, 3)}],
    ]
    seen = []

    def fake_fetch(conn, sql, params=()):
        seen.append(params)
        return answers[len(seen) - 1]

    baseline, daily, latest = runner.subs_inputs("conn", "a2p", fetch=fake_fetch)
    assert baseline == (date(2026, 9, 1), 950)
    assert daily == [(date(2026, 9, 2), 3, 1), (date(2026, 9, 3), 2, 0)]
    assert latest == date(2026, 9, 3)
    assert seen[0] == ("a2p",) and seen[1] == ("a2p", date(2026, 9, 1))


def test_subs_inputs_no_baseline():
    def fake_fetch(conn, sql, params=()):
        return [{"latest": None}] if "max(day)" in sql else []

    assert runner.subs_inputs("c", "a2p", fetch=fake_fetch) == (None, [], None)
