from datetime import date, datetime, timezone
from types import SimpleNamespace

from ytops import runner

TODAY = date(2026, 11, 7)


def _fake_collector(rows_by_key):
    def collect(ctx, start, end, with_yearly=True):
        if ctx.analytics == "boom":
            raise RuntimeError("analytics down")
        return {"yt_channel_daily": rows_by_key(ctx)}
    return SimpleNamespace(collect=collect)


def _setup(monkeypatch, bad=()):
    monkeypatch.setattr(runner, "COLLECTORS", [("channel_daily", _fake_collector(
        lambda ctx: [{"channel_key": ctx.key, "day": date(2026, 11, 3), "views": 5, "collected_at": ctx.collected_at}]
    ))])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "boom" if k in bad else "ok")
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: "data")
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
        ("channel_daily", SimpleNamespace(collect=lambda ctx, s, e, **kw: {"yt_channel_daily": [
            {"channel_key": "a2p", "day": date(2026, 11, 2), "subs_gained": 5, "subs_lost": 1},
            {"channel_key": "a2p", "day": date(2026, 11, 3), "subs_gained": 2, "subs_lost": None}]})),
        ("subs", runner.subs),
    ])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: SimpleNamespace(
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
        ("channel_daily", SimpleNamespace(collect=lambda ctx, s, e, **kw: {"yt_channel_daily": [
            {"channel_key": "a2p", "day": date(2026, 11, 1), "subs_gained": 3, "subs_lost": 0},
            {"channel_key": "a2p", "day": date(2026, 11, 2), "subs_gained": 5, "subs_lost": 1}]})),
        ("subs", runner.subs),
    ])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: SimpleNamespace(
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
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: "x")
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


def test_default_today_is_kst_date(monkeypatch):
    # 2026-11-06 20:00 UTC is already 2026-11-07 in Seoul
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc).astimezone(tz)

    seen = {}
    monkeypatch.setattr(runner, "datetime", FixedDatetime)
    monkeypatch.setattr(runner, "COLLECTORS", [("channel_daily", SimpleNamespace(
        collect=lambda ctx, s, e, **kw: seen.update(today=ctx.today, end=e) or {}))])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: "x")
    monkeypatch.setattr(runner, "load_channels", lambda: {"a2p": "A"})
    runner.run_collect(["a2p"], dry_run=True)
    assert seen["today"] == date(2026, 11, 7) and seen["end"] == date(2026, 11, 6)


def _schedule_setup(monkeypatch, rows):
    monkeypatch.setattr(runner, "COLLECTORS", [("schedule", SimpleNamespace(
        collect=lambda ctx, s, e, **kw: {"yt_schedule": rows, "yt_channel_daily": [
            {"channel_key": "a2p", "day": date(2026, 11, 3), "views": 1}]}))])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: "x")
    monkeypatch.setattr(runner, "load_channels", lambda: {"a2p": "A"})
    calls = []
    monkeypatch.setattr(runner.store, "upsert", lambda conn, t, rows, pk, keep=(): calls.append(("upsert", t)) or len(rows))
    monkeypatch.setattr(runner.store, "replace_channel",
                        lambda conn, t, key, rows, pk: calls.append(("replace", t, key, len(rows))) or len(rows))
    return calls


def test_runner_replaces_schedule_rows(monkeypatch):
    calls = _schedule_setup(monkeypatch, [{"channel_key": "a2p", "video_id": "v"}])
    runner.run_collect(["a2p"], dry_run=False, conn=object(), today=TODAY)
    assert ("replace", "yt_schedule", "a2p", 1) in calls
    assert ("upsert", "yt_channel_daily") in calls and ("upsert", "yt_schedule") not in calls


def test_runner_empty_schedule_still_replaces(monkeypatch):
    calls = _schedule_setup(monkeypatch, [])
    runner.run_collect(["a2p"], dry_run=False, conn=object(), today=TODAY)
    assert ("replace", "yt_schedule", "a2p", 0) in calls


def test_slices_split_long_windows():
    s, e = date(2025, 11, 7), date(2026, 11, 6)  # 365 days
    got = runner.slices(s, e)
    assert got == [(date(2025, 11, 7), date(2026, 5, 5)), (date(2026, 5, 6), date(2026, 11, 1)),
                   (date(2026, 11, 2), date(2026, 11, 6))]
    assert [(hi - lo).days + 1 for lo, hi in got] == [180, 180, 5]
    assert runner.slices(date(2026, 11, 1), date(2026, 11, 6)) == [(date(2026, 11, 1), date(2026, 11, 6))]
    assert runner.slices(date(2026, 11, 1), date(2026, 11, 1), size=1) == [(date(2026, 11, 1), date(2026, 11, 1))]


def test_backfill_365_collects_channel_daily_in_slices(monkeypatch):
    calls = []

    def collect(ctx, s, e, with_yearly=True):
        calls.append((s, e))
        out = {"yt_channel_daily": [{"channel_key": "a2p", "day": s, "views": 1}]}
        if with_yearly:
            out["yt_yearly_minutes"] = [{"channel_key": "a2p", "as_of": ctx.today}]
        return out

    monkeypatch.setattr(runner, "COLLECTORS", [("channel_daily", SimpleNamespace(collect=collect))])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: "x")
    monkeypatch.setattr(runner, "load_channels", lambda: {"a2p": "A"})
    res = runner.run_collect(["a2p"], days=365, dry_run=True, today=TODAY)
    assert calls == [(date(2025, 11, 7), date(2026, 5, 5)), (date(2026, 5, 6), date(2026, 11, 1)),
                     (date(2026, 11, 2), date(2026, 11, 6))]
    assert res.counts == {"yt_channel_daily": 3, "yt_yearly_minutes": 1}  # yearly kept once


def test_backfill_365_queries_yearly_once(monkeypatch):
    from ytops.collect import channel_daily

    class Analytics:
        def __init__(self):
            self.dims = []

        def query(self, start, end, dims, metrics, filters=None, sort=None, max_results=200):
            self.dims.append(dims)
            return []

    an = Analytics()
    monkeypatch.setattr(runner, "COLLECTORS", [("channel_daily", channel_daily)])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: an)
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: "x")
    monkeypatch.setattr(runner, "load_channels", lambda: {"a2p": "A"})
    res = runner.run_collect(["a2p"], days=365, dry_run=True, today=TODAY)
    # 3 slices x 3 daily queries, but the 365-day creatorContentType query runs only once
    assert an.dims.count("creatorContentType") == 1
    assert an.dims.count("day") == 3 and len(an.dims) == 10
    assert res.counts.get("yt_yearly_minutes") == 1


def test_only_limits_collectors(monkeypatch):
    ran = []
    mods = [(n, SimpleNamespace(collect=lambda ctx, s, e, n=n: ran.append(n) or {})) for n in ("channel_daily", "live")]
    monkeypatch.setattr(runner, "COLLECTORS", mods)
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: "x")
    monkeypatch.setattr(runner, "load_channels", lambda: {"a2p": SimpleNamespace(is_live=True)})
    runner.run_collect(["a2p"], dry_run=True, today=TODAY, only=["live"])
    assert ran == ["live"]
    import pytest
    with pytest.raises(ValueError):
        runner.run_collect(["a2p"], dry_run=True, today=TODAY, only=["nope"])


def test_playlists_are_replaced_per_channel(monkeypatch):
    monkeypatch.setattr(runner, "COLLECTORS", [("playlists", SimpleNamespace(
        collect=lambda ctx, s, e: {"yt_playlist": [], "yt_playlist_item": []}))])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: "x")
    monkeypatch.setattr(runner, "load_channels", lambda: {"a2p": "A"})
    calls = []
    monkeypatch.setattr(runner.store, "upsert", lambda conn, t, rows, pk, keep=(): calls.append(("upsert", t)) or len(rows))
    monkeypatch.setattr(runner.store, "replace_channel",
                        lambda conn, t, key, rows, pk: calls.append(("replace", t, key)) or len(rows))
    runner.run_collect(["a2p"], dry_run=False, conn=object(), today=TODAY)
    assert ("replace", "yt_playlist", "a2p") in calls and ("replace", "yt_playlist_item", "a2p") in calls


def test_run_log_records_channels(monkeypatch):
    _setup(monkeypatch, bad=("soombi",))
    logged = []
    monkeypatch.setattr(runner.store, "upsert", lambda conn, t, rows, pk, keep=(): logged.extend(rows) if t == "yt_run_log" else None)
    runner.run_collect(["soombi", "a2p"], dry_run=False, conn=object(), today=TODAY)
    assert logged[0]["channels"].obj == ["soombi", "a2p"]


def test_run_log_records_collectors(monkeypatch):
    mods = [(n, SimpleNamespace(collect=lambda ctx, s, e: {})) for n in ("channel_daily", "live")]
    monkeypatch.setattr(runner, "COLLECTORS", mods)
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: "x")
    monkeypatch.setattr(runner, "load_channels", lambda: {"a2p": SimpleNamespace(is_live=True)})
    logged = []
    monkeypatch.setattr(runner.store, "upsert", lambda conn, t, rows, pk, keep=(): logged.extend(rows) if t == "yt_run_log" else None)
    runner.run_collect(["a2p"], dry_run=False, conn=object(), today=TODAY, only=["live"])
    runner.run_collect(["a2p"], dry_run=False, conn=object(), today=TODAY)
    assert logged[0]["collectors"].obj == ["live"]
    assert logged[1]["collectors"].obj == ["channel_daily", "live"]


def test_live_only_run_skips_non_live_channels(monkeypatch):
    built = []
    mods = [(n, SimpleNamespace(collect=lambda ctx, s, e: {})) for n in ("channel_daily", "live", "schedule")]
    monkeypatch.setattr(runner, "COLLECTORS", mods)
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: built.append(("analytics", k)) or "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: built.append(("data", k)) or "x")
    monkeypatch.setattr(runner, "load_channels", lambda: {
        "soombi": SimpleNamespace(is_live=True), "a2p": SimpleNamespace(is_live=False)})
    logged = []
    monkeypatch.setattr(runner.store, "upsert", lambda conn, t, rows, pk, keep=(): logged.extend(rows) if t == "yt_run_log" else None)
    runner.run_collect(["soombi", "a2p"], dry_run=False, conn=object(), today=TODAY, only=["live"])
    assert built == [("analytics", "soombi"), ("data", "soombi")]
    assert logged[-1]["channels"].obj == ["soombi"]
    # a mixed run (live is not the only collector) and a full run still visit every channel
    built.clear()
    runner.run_collect(["soombi", "a2p"], dry_run=True, today=TODAY, only=["live", "schedule"])
    runner.run_collect(["soombi", "a2p"], dry_run=True, today=TODAY)
    assert sorted({k for _, k in built}) == ["a2p", "soombi"] and len(built) == 8


def _two_project_setup(monkeypatch, projects, limit):
    """Fake clients whose every call goes through the project meter (one call per collector run)."""
    from ytops import data
    from ytops.registry import Project
    ran = []
    metered = {}

    def fake_data(key, meter=None):
        metered[key] = meter
        return SimpleNamespace(key=key, meter=meter)

    def collect(ctx, start, end, with_yearly=True):
        ran.append(ctx.key)
        for _ in range(limit):
            ctx.data.meter.spend() if ctx.data.meter else None
        return {}

    monkeypatch.setattr(runner, "COLLECTORS", [("channel_daily", SimpleNamespace(collect=collect))])
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "ok")
    monkeypatch.setattr(runner, "data_for_key", fake_data)
    monkeypatch.setattr(runner, "load_channels", lambda: {k: k for k in ("soombi", "a2p", "pliwav", "other")})
    monkeypatch.setattr(runner, "load_projects", lambda: [Project(*p) for p in projects])
    monkeypatch.setattr(runner, "CallMeter", lambda label="": data.CallMeter(limit=limit, label=label))
    return ran, metered


def test_exhausted_project_skips_remaining_channels(monkeypatch):
    ran, metered = _two_project_setup(monkeypatch, [("p1", "P1", ["soombi", "a2p"])], limit=3)
    res = runner.run_collect(["soombi", "a2p"], dry_run=True, today=TODAY)
    assert ran == ["soombi"]  # a2p never got a context nor collectors
    assert "a2p" not in metered
    assert [(e["channel"], e["stage"], e["error"]) for e in res.errors] == [
        ("a2p", "budget", "ProjectBudgetExceeded")]


def test_projects_do_not_share_a_meter(monkeypatch):
    ran, metered = _two_project_setup(
        monkeypatch, [("p1", "P1", ["soombi"]), ("p2", "P2", ["pliwav"])], limit=3)
    res = runner.run_collect(["soombi", "pliwav"], dry_run=True, today=TODAY)
    assert ran == ["soombi", "pliwav"] and res.errors == []
    assert metered["soombi"] is not metered["pliwav"]


def test_channel_outside_projects_has_no_meter(monkeypatch):
    ran, metered = _two_project_setup(monkeypatch, [("p1", "P1", ["soombi"])], limit=3)
    runner.run_collect(["other"], dry_run=True, today=TODAY)
    assert ran == ["other"] and metered["other"] is None
