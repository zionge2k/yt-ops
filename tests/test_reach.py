from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from ytops import render, runner
from ytops.collect import COLLECTORS, reach
from ytops.collect.context import CollectContext
from ytops.registry import Channel

CH = Channel("soombi", "soombi", "UC1", True, 0, 0, "chalna")
TODAY = date(2026, 11, 10)
NOW = datetime(2026, 11, 10, 1, 0, tzinfo=timezone.utc)
HEADER = "date,channel_id,video_id,video_thumbnail_impressions,video_thumbnail_impressions_ctr"


def _row(day, video, impressions, ctr, channel="UC1"):
    return f"{day},{channel},{video},{impressions},{ctr}"


def _csv(*rows, header=HEADER):
    return "\n".join([header, *rows]) + "\n"


def _parse(text):
    return reach.parse_report(text, "soombi", NOW)


def test_parse_report_builds_table_rows():
    rows = _parse(_csv(_row("20261107", "vidA", 1200, "0.051"), _row("20261107", "vidB", 30, "0.1")))
    assert rows == [
        {"channel_key": "soombi", "day": date(2026, 11, 7), "video_id": "vidA",
         "impressions": 1200, "ctr": 0.051, "collected_at": NOW},
        {"channel_key": "soombi", "day": date(2026, 11, 7), "video_id": "vidB",
         "impressions": 30, "ctr": 0.1, "collected_at": NOW},
    ]
    assert type(rows[0]["impressions"]) is int


def test_parse_report_accepts_both_date_formats():
    rows = _parse(_csv(_row("20261107", "a", 1, "0.1"), _row("2026-11-08", "b", 1, "0.1")))
    assert [r["day"] for r in rows] == [date(2026, 11, 7), date(2026, 11, 8)]


def test_parse_report_ctr_over_one_is_a_percent():
    rows = _parse(_csv(_row("20261107", "ratio", 100, "0.052"), _row("20261107", "pct", 100, "5.2"),
                       _row("20261107", "one", 100, "1"), _row("20261107", "zero", 100, "0")))
    assert {r["video_id"]: r["ctr"] for r in rows} == {"ratio": 0.052, "pct": 0.052, "one": 1.0, "zero": 0.0}


def test_parse_report_is_header_driven_and_skips_blank_lines():
    header = "video_thumbnail_impressions_ctr,video_id,channel_id,video_thumbnail_impressions,date"
    text = f"{header}\n0.07,vidA,UC1,500,20261107\n\n   \n,,,,\n0.02,vidB,UC1,10,20261107\n\n"
    rows = _parse(text)
    assert [(r["video_id"], r["impressions"], r["ctr"]) for r in rows] == [("vidA", 500, 0.07), ("vidB", 10, 0.02)]


def test_parse_report_tolerates_bom_crlf_and_float_counts():
    text = "﻿" + HEADER + "\r\n" + _row("20261107", "a", "1200.0", "0.05") + "\r\n"
    assert _parse(text)[0]["impressions"] == 1200


def test_parse_report_empty_metric_cells_become_none():
    rows = _parse(_csv(_row("20261107", "a", "", ""), _row("20261107", "b", 5, "")))
    assert (rows[0]["impressions"], rows[0]["ctr"]) == (None, None)
    assert (rows[1]["impressions"], rows[1]["ctr"]) == (5, None)


def test_parse_report_nothing_to_read():
    assert _parse("") == [] and _parse("\n\n") == [] and _parse(_csv()) == []


def test_parse_report_missing_column_is_loud():
    with pytest.raises(ValueError, match="video_thumbnail_impressions_ctr"):
        _parse("date,channel_id,video_id,video_thumbnail_impressions\n20261107,UC1,a,5\n")


class FakeReporting:
    def __init__(self, job, reports, files):
        self.job, self.report_list, self.files = job, reports, files
        self.calls, self.downloads = [], []

    def reach_job_id(self):
        self.calls.append("job")
        return self.job

    def reports(self, job_id, created_after):
        self.calls.append(("reports", job_id, created_after))
        return self.report_list

    def download(self, url):
        self.downloads.append(url)
        return self.files[url]


def _ctx(reporting):
    return CollectContext("soombi", CH, None, None, TODAY, NOW, reporting=reporting)


def _report(rid, created):
    return {"id": rid, "createTime": created, "downloadUrl": f"https://dl/{rid}"}


def test_collect_reads_recent_reports_and_the_later_report_wins_an_overlap():
    old = _csv(_row("20261107", "vidA", 100, "0.04"), _row("20261107", "vidB", 50, "0.02"))
    new = _csv(_row("20261107", "vidA", 130, "0.05"), _row("20261108", "vidA", 90, "0.06"))
    fake = FakeReporting(
        "job1",
        # listed newest first on purpose: the winner is decided by createTime, not by list order
        [_report("r2", "2026-11-10T00:30:00.123Z"), _report("r1", "2026-11-09T00:30:00.456Z")],
        {"https://dl/r1": old, "https://dl/r2": new})
    out = reach.collect(_ctx(fake), TODAY - timedelta(days=10), TODAY - timedelta(days=1))
    assert set(out) == {"yt_reach_daily"}
    got = {(r["day"], r["video_id"]): (r["impressions"], r["ctr"]) for r in out["yt_reach_daily"]}
    assert got == {(date(2026, 11, 7), "vidA"): (130, 0.05),   # r2 replaces r1 for the overlapping day
                   (date(2026, 11, 7), "vidB"): (50, 0.02),    # only r1 has it: kept
                   (date(2026, 11, 8), "vidA"): (90, 0.06)}
    assert len(out["yt_reach_daily"]) == 3  # one row per (day, video): the table key stays unique
    assert all(r["channel_key"] == "soombi" and r["collected_at"] == NOW for r in out["yt_reach_daily"])
    assert fake.downloads == ["https://dl/r1", "https://dl/r2"]


def test_collect_asks_only_for_reports_created_in_the_last_week():
    fake = FakeReporting("job1", [], {})
    out = reach.collect(_ctx(fake), TODAY, TODAY)
    assert reach.LOOKBACK_DAYS == 7
    assert fake.calls == ["job", ("reports", "job1", NOW - timedelta(days=7))]
    assert out == {"yt_reach_daily": []}


def test_collect_without_a_job_is_not_an_error_and_downloads_nothing():
    fake = FakeReporting(None, [_report("r1", "2026-11-09T00:00:00Z")], {})
    out = reach.collect(_ctx(fake), TODAY, TODAY)
    assert out == {"yt_reach_daily": []}
    assert fake.calls == ["job"] and fake.downloads == []  # the report list is not even asked for


def test_collect_skips_a_report_without_download_url():
    fake = FakeReporting("job1", [{"id": "r1", "createTime": "2026-11-09T00:00:00Z"}], {})
    assert reach.collect(_ctx(fake), TODAY, TODAY) == {"yt_reach_daily": []}
    assert fake.downloads == []


def test_collect_download_failure_propagates():
    class Broken(FakeReporting):
        def download(self, url):
            raise RuntimeError("HTTP 500")

    fake = Broken("job1", [_report("r1", "2026-11-09T00:00:00Z")], {})
    with pytest.raises(RuntimeError):
        reach.collect(_ctx(fake), TODAY, TODAY)


def test_reach_is_the_last_collector_and_never_fails_the_card():
    assert COLLECTORS[-1][0] == "reach" and COLLECTORS[-1][1] is reach
    assert "reach" not in render.FAILED_STAGES and "store:yt_reach_daily" not in render.FAILED_STAGES
    assert not render._failed("reach") and not render._failed("store:yt_reach_daily")


# ---- runner wiring ----

def _runner_setup(monkeypatch, collectors, channels=("a2p",)):
    built = []
    monkeypatch.setattr(runner, "COLLECTORS", collectors)
    monkeypatch.setattr(runner, "analytics_for_key", lambda k: "x")
    monkeypatch.setattr(runner, "data_for_key", lambda k, meter=None: "x")
    monkeypatch.setattr(runner, "reporting_for_key", lambda k: built.append(k) or f"reporting-{k}")
    monkeypatch.setattr(runner, "load_channels", lambda: {k: SimpleNamespace(is_live=True) for k in channels})
    return built


def test_runner_builds_a_reporting_client_per_channel(monkeypatch):
    seen = {}
    mods = [("channel_daily", SimpleNamespace(collect=lambda ctx, s, e, **kw: {})),
            ("reach", SimpleNamespace(collect=lambda ctx, s, e: seen.setdefault(ctx.key, ctx.reporting) and {}))]
    built = _runner_setup(monkeypatch, mods, channels=("soombi", "a2p"))
    res = runner.run_collect(["soombi", "a2p"], dry_run=True, today=TODAY)
    assert built == ["soombi", "a2p"] and res.errors == []
    assert seen == {"soombi": "reporting-soombi", "a2p": "reporting-a2p"}


def test_runner_skips_the_reporting_client_when_reach_does_not_run(monkeypatch):
    # a live-only run must not refresh credentials for a client it never uses
    mods = [("live", SimpleNamespace(collect=lambda ctx, s, e: {})),
            ("reach", SimpleNamespace(collect=lambda ctx, s, e: {}))]
    built = _runner_setup(monkeypatch, mods)
    runner.run_collect(["a2p"], dry_run=True, today=TODAY, only=["live"])
    assert built == []


def test_reporting_client_failure_is_a_reach_error_not_a_client_error(monkeypatch):
    ran = []
    mods = [("channel_daily", SimpleNamespace(collect=lambda ctx, s, e, **kw: ran.append("daily") or {})),
            ("reach", SimpleNamespace(collect=lambda ctx, s, e: ran.append("reach") or {}))]
    _runner_setup(monkeypatch, mods)

    def boom(key):
        raise RuntimeError("discovery failed")

    monkeypatch.setattr(runner, "reporting_for_key", boom)
    res = runner.run_collect(["a2p"], dry_run=True, today=TODAY)
    assert [(e["channel"], e["stage"], e["error"]) for e in res.errors] == [("a2p", "reach", "RuntimeError")]
    assert ran == ["daily"]  # the other collectors still run; reach is skipped, not retried without a client


def test_reach_rows_reach_the_store_and_a_reach_error_does_not_stop_other_collectors(monkeypatch):
    def failing(ctx, s, e):
        raise RuntimeError("report download failed: HTTP 500")

    mods = [("reach", SimpleNamespace(collect=failing)),
            ("channel_daily", SimpleNamespace(collect=lambda ctx, s, e, **kw: {"yt_channel_daily": [
                {"channel_key": ctx.key, "day": date(2026, 11, 3), "views": 1}]}))]
    _runner_setup(monkeypatch, mods)
    res = runner.run_collect(["a2p"], dry_run=True, today=TODAY)
    assert [(e["stage"], e["error"]) for e in res.errors] == [("reach", "RuntimeError")]
    assert res.counts == {"yt_channel_daily": 1}
