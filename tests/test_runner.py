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
    logged = []

    def fake_upsert(conn, table, rows, pk, keep=()):
        calls.append((table, len(rows), tuple(pk), keep))
        if table == "yt_run_log":
            logged.extend(rows)
        return len(rows)

    monkeypatch.setattr(runner.store, "upsert", fake_upsert)
    runner.run_collect(["a2p"], dry_run=False, conn=object(), today=TODAY)
    assert ("yt_channel_daily", 1, ("channel_key", "day"), ()) in calls
    assert calls[-1][0] == "yt_run_log"
    log = logged[0]
    assert log["errors"].obj == [] and log["counts"].obj == {"yt_channel_daily": 1}
    assert log["ok"] is True


def test_run_log_ok_false_and_payload_with_errors(monkeypatch):
    _setup(monkeypatch, bad=("a2p",))
    logged = []
    monkeypatch.setattr(runner.store, "upsert", lambda conn, t, rows, pk, keep=(): logged.extend(rows) if t == "yt_run_log" else None)
    runner.run_collect(["a2p"], dry_run=False, conn=object(), today=TODAY)
    assert logged[0]["ok"] is False
    assert logged[0]["errors"].obj[0]["error"] == "RuntimeError"


def test_subs_exact_uses_this_runs_rows_before_db_write(monkeypatch):
    # DB has the baseline but no channel_daily rows yet; this run's rows must count
    base = date(2026, 11, 1)
    monkeypatch.setattr(runner, "COLLECTORS", [
        ("channel_daily", SimpleNamespace(collect=lambda ctx, s, e: {"yt_channel_daily": [
            {"channel_key": "a2p", "day": date(2026, 11, 2), "subs_gained": 5, "subs_lost": 1},
            {"channel_key": "a2p", "day": date(2026, 11, 3), "subs_gained": 2, "subs_lost": None}]})),
        ("subs", runner.subs),
    ])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k: SimpleNamespace(
        channel_stats=lambda: {"statistics": {"subscriberCount": "990"}}))
    monkeypatch.setattr(runner, "load_channels", lambda: {"a2p": "A"})

    def fake_fetch(conn, sql, params=()):
        if "yt_subs_snapshot" in sql:
            return [{"taken_on": base, "api_subscribers": 900}]
        return [{"latest": None}] if "max(day)" in sql else []

    monkeypatch.setattr(runner.store, "fetch", fake_fetch)
    monkeypatch.setattr(runner, "subs_inputs", lambda conn, key, current_rows=(), _f=runner.subs_inputs: _f(conn, key, fake_fetch, current_rows))
    seen = {}
    monkeypatch.setattr(runner.store, "upsert", lambda conn, t, rows, pk, keep=(): seen.setdefault(t, rows) and len(rows))
    runner.run_collect(["a2p"], dry_run=False, conn=object(), today=TODAY)
    # api 990 < 1000 is exact already; the baseline is not used
    assert seen["yt_subs_snapshot"][0]["exact_subscribers"] == 990


def test_subs_exact_over_1000_uses_this_runs_rows(monkeypatch):
    base = date(2026, 11, 1)
    monkeypatch.setattr(runner, "COLLECTORS", [
        ("channel_daily", SimpleNamespace(collect=lambda ctx, s, e: {"yt_channel_daily": [
            {"channel_key": "a2p", "day": date(2026, 11, 1), "subs_gained": 3, "subs_lost": 0},
            {"channel_key": "a2p", "day": date(2026, 11, 2), "subs_gained": 5, "subs_lost": 1}]})),
        ("subs", runner.subs),
    ])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k: SimpleNamespace(
        channel_stats=lambda: {"statistics": {"subscriberCount": "1000"}}))
    monkeypatch.setattr(runner, "load_channels", lambda: {"a2p": "A"})

    def fake_fetch(conn, sql, params=()):
        if "yt_subs_snapshot" in sql:
            return [{"taken_on": base, "api_subscribers": 998}]
        return [{"latest": None}] if "max(day)" in sql else []

    monkeypatch.setattr(runner, "subs_inputs", lambda conn, key, current_rows=(), _f=runner.subs_inputs: _f(conn, key, fake_fetch, current_rows))
    seen = {}
    monkeypatch.setattr(runner.store, "upsert", lambda conn, t, rows, pk, keep=(): seen.setdefault(t, rows) and len(rows))
    runner.run_collect(["a2p"], dry_run=False, conn=object(), today=TODAY)
    # baseline day 11-01 is included (inclusive lower bound)
    assert seen["yt_subs_snapshot"][0]["exact_subscribers"] == 998 + 3 + 4


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
    seen, sqls = [], []

    def fake_fetch(conn, sql, params=()):
        seen.append(params)
        sqls.append(sql)
        return answers[len(seen) - 1]

    baseline, daily, latest = runner.subs_inputs("conn", "a2p", fetch=fake_fetch)
    assert baseline == (date(2026, 9, 1), 950)
    assert daily == [(date(2026, 9, 2), 3, 1), (date(2026, 9, 3), 2, 0)]
    assert latest == date(2026, 9, 3)
    assert seen[0] == ("a2p",) and seen[1] == ("a2p", date(2026, 9, 1))
    assert "day >= %s" in sqls[1]  # the baseline day itself is included


def test_subs_inputs_no_baseline():
    def fake_fetch(conn, sql, params=()):
        return [{"latest": None}] if "max(day)" in sql else []

    assert runner.subs_inputs("c", "a2p", fetch=fake_fetch) == (None, [], None)


def test_subs_inputs_merges_current_rows_and_coalesces_none():
    def fake_fetch(conn, sql, params=()):
        if "yt_subs_snapshot" in sql:
            return [{"taken_on": date(2026, 9, 1), "api_subscribers": 950}]
        if "max(day)" in sql:
            return [{"latest": date(2026, 9, 2)}]
        return [{"day": date(2026, 9, 2), "subs_gained": 1, "subs_lost": 1}]

    cur = [{"day": date(2026, 9, 2), "subs_gained": 4, "subs_lost": None},
           {"day": date(2026, 9, 3), "subs_gained": None, "subs_lost": 2}]
    baseline, daily, latest = runner.subs_inputs("c", "a2p", fetch=fake_fetch, current_rows=cur)
    assert daily == [(date(2026, 9, 2), 4, 0), (date(2026, 9, 3), 0, 2)]
    assert latest == date(2026, 9, 3)
