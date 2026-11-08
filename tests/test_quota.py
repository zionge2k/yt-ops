import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ytops import quota
from ytops.registry import Project

UTC = timezone.utc
FIX = Path(__file__).parent / "fixtures"
PROJECT = Project("proj-a", "숨비네", ["soombi"])


def _series(name):
    return json.loads((FIX / f"monitoring_{name}.json").read_text(encoding="utf-8"))["timeSeries"]


def test_reset_window_winter():
    # 2026-11-08 05:00Z is 21:00 PST on 11/07 -> window opens at 11/07 08:00Z.
    start, end = quota.reset_window(datetime(2026, 11, 8, 5, 0, tzinfo=UTC))
    assert start == datetime(2026, 11, 7, 8, 0, tzinfo=UTC) and end == datetime(2026, 11, 8, 5, 0, tzinfo=UTC)
    assert start.tzinfo == UTC


def test_reset_window_summer():
    # PDT is UTC-7, so the window opens at 07:00Z.
    start, _ = quota.reset_window(datetime(2026, 7, 1, 20, 0, tzinfo=UTC))
    assert start == datetime(2026, 7, 1, 7, 0, tzinfo=UTC)


def test_sum_usage():
    assert quota.sum_usage(_series("usage")) == 438
    assert quota.sum_usage([]) == 0


def test_hourly_keys_in_kst():
    h = quota.hourly(_series("usage"))
    assert h == {"11/08 08시": 0, "11/08 09시": 420, "11/08 12시": 12, "11/08 14시": 6}


def test_requests_by():
    rows = quota.requests_by(_series("requests"))
    assert ("11/08 09시", "playlistItems.list", "abcdefgh…", "200", 300) in rows
    assert {r[1] for r in rows} == {"playlistItems.list", "videos.list"}
    assert ("11/08 12시", "videos.list", "ijklmnop…", "403", 5) in rows


def test_limit_from():
    assert quota.limit_from(_series("limit")) == 10000  # per-minute series (1.8M, 180k) are ignored
    assert quota.limit_from(_series("limit")[1:]) == 10000  # none left for the day limit -> default
    unlabeled = [{"metric": {"labels": {}}, "points": [{"value": {"int64Value": "7"}}, {"value": {"int64Value": "9"}}]}]
    assert quota.limit_from(unlabeled) == 9  # max, never a sum
    assert quota.limit_from([]) == 10000
    assert quota.limit_from([], default=5) == 5


KST = quota.KST
AS_OF = datetime(2026, 11, 8, 14, 2, tzinfo=KST)
RESET = datetime(2026, 11, 8, 17, 0, tzinfo=KST)


def _report(used, limit=10000, analytics=3120):
    return quota.format_report(
        PROJECT, used, limit, RESET,
        {"11/08 09시": 420, "11/08 11시": 12, "11/08 13시": 0, "11/09 01시": 6},
        {"abcdefgh…": 1790, "ijklmnop…": 40},
        [("playlistItems.list", 1200), ("videos.list", 400)], analytics, AS_OF)


def test_report_layout():
    lines = _report(1830).splitlines()
    assert lines[0] == "숨비네 (proj-a)"
    assert lines[1] == "  Data API  1,830 / 10,000  (18%)  · 17:00 에 0 으로 돌아감 · 11/08 14:02 기준"
    assert lines[2] == "  시간대별  11/08 09시 420 · 11시 12 · 11/09 01시 6"
    assert lines[3] == "  어디서    abcdefgh… 1,790 · ijklmnop… 40"
    assert lines[4] == "  메서드    playlistItems.list 1,200 · videos.list 400"
    assert lines[5] == "  Analytics 3,120 / 100,000"


def test_report_without_analytics_or_detail():
    out = quota.format_report(PROJECT, 5, 10000, RESET, {}, {}, [], None, AS_OF)
    assert out.splitlines()[1:] == ["  Data API  5 / 10,000  (0%)  · 17:00 에 0 으로 돌아감 · 11/08 14:02 기준"]


@pytest.mark.parametrize("used,prefix", [(7999, "  Data API"), (8000, "  ⚠ Data API"), (9999, "  ⚠ Data API")])
def test_report_warns_from_80_percent(used, prefix):
    assert _report(used).splitlines()[1].startswith(prefix)


def test_report_exhausted():
    line = _report(10000).splitlines()[1]
    assert "⛔ 소진" in line and "⚠" not in line


class FakeMon:
    def __init__(self, fail_limit=False, fail_analytics=False):
        self.calls, self.fail_limit, self.fail_analytics = [], fail_limit, fail_analytics

    def series(self, project, metric_filter, start, end, period_s, aligner, group_by):
        self.calls.append(dict(project=project, filter=metric_filter, start=start, end=end,
                               period_s=period_s, aligner=aligner, group_by=group_by))
        if "youtubeanalytics" in metric_filter:
            if self.fail_analytics:
                raise RuntimeError("boom")
            return _series("usage")[:1]
        if "quota/limit" in metric_filter:
            if self.fail_limit:
                raise RuntimeError("boom")
            return _series("limit")
        if "net_usage" in metric_filter:
            return _series("usage")
        return _series("requests")


NOW = datetime(2026, 11, 8, 5, 0, tzinfo=UTC)


def test_collect_project_queries_and_result():
    mon = FakeMon()
    got = quota.collect_project(mon, PROJECT, NOW)
    by_type = {c["filter"].split('"')[1].rsplit("/", 1)[-1] + ("A" if "analytics" in c["filter"] else ""): c
               for c in mon.calls}
    assert set(by_type) == {"net_usage", "limit", "request_count", "net_usageA"}
    for t in ("net_usage", "limit", "request_count"):
        assert 'resource.labels.service="youtube.googleapis.com"' in by_type[t]["filter"]
    assert 'metric.labels.limit_name="defaultPerDayPerProject"' in by_type["limit"]["filter"]
    assert 'resource.labels.service="youtubeanalytics.googleapis.com"' in by_type["net_usageA"]["filter"]
    assert all(c["project"] == "proj-a" for c in mon.calls)
    assert by_type["net_usage"]["period_s"] == 3600 and by_type["net_usage"]["aligner"] == "ALIGN_SUM"
    assert by_type["limit"]["aligner"] == "ALIGN_MAX"
    assert by_type["limit"]["period_s"] == int((NOW - datetime(2026, 11, 7, 8, 0, tzinfo=UTC)).total_seconds())
    assert by_type["request_count"]["group_by"] == [
        "resource.labels.method", "resource.labels.credential_id", "metric.labels.response_code"]
    assert got["used"] == 438 and got["limit"] == 10000 and got["analytics_used"] == 438
    assert got["project"] == "proj-a" and got["label"] == "숨비네"
    assert got["hours"]["11/08 09시"] == 420
    assert tuple(got["top_methods"][0]) == ("playlistItems.list", 302)
    assert json.dumps(got)  # JSON-safe for `--json`


def test_collect_project_falls_back_silently():
    got = quota.collect_project(FakeMon(fail_limit=True, fail_analytics=True), PROJECT, NOW)
    assert got["limit"] == 10000 and got["analytics_used"] is None


def test_monitoring_builds_url_like_the_prototype():
    seen = {}

    def fetch(url, headers):
        seen["url"], seen["headers"] = url, headers
        return {"timeSeries": [{"x": 1}]}

    mon = quota.Monitoring(lambda p: "TOK", fetch)
    out = mon.series("proj-a", 'metric.type="m"', datetime(2026, 11, 7, 8, tzinfo=UTC), NOW, 3600,
                     "ALIGN_SUM", ["resource.labels.service", "metric.labels.response_code"])
    assert out == [{"x": 1}] and seen["headers"] == {"Authorization": "Bearer TOK"}
    url = seen["url"]
    assert url.startswith("https://monitoring.googleapis.com/v3/projects/proj-a/timeSeries?")
    assert url.count("aggregation.groupByFields=") == 2
    assert "interval.startTime=2026-11-07T08%3A00%3A00Z" in url
    assert "aggregation.alignmentPeriod=3600s" in url
    assert "aggregation.crossSeriesReducer=REDUCE_SUM" in url


def test_gcloud_token_for_picks_first_account_that_can_read(monkeypatch):
    calls = []

    def run(cmd):
        calls.append(cmd)
        if cmd[:3] == ["gcloud", "auth", "list"]:
            return "a@x.com\nb@x.com\n"
        return "tok-" + cmd[-1].split("=", 1)[1] + "\n"

    def probe(project, token):
        return token == "tok-b@x.com"

    quota._TOKEN_CACHE.clear()
    assert quota.gcloud_token_for("p1", None, run=run, probe=probe) == "tok-b@x.com"
    n = len(calls)
    assert quota.gcloud_token_for("p1", None, run=run, probe=probe) == "tok-b@x.com"
    assert len(calls) == n  # cached per project


def test_gcloud_token_for_error_lists_accounts_without_tokens():
    quota._TOKEN_CACHE.clear()
    with pytest.raises(quota.QuotaAccessError) as e:
        quota.gcloud_token_for("p2", ["a@x.com"], run=lambda cmd: "SECRET\n", probe=lambda p, t: False)
    assert "a@x.com" in str(e.value) and "SECRET" not in str(e.value) and "p2" in str(e.value)


def test_credential_short():
    cid = "oauth2:543780518761-abcdefgh" + "x" * 24 + ".apps.googleusercontent.com"
    assert quota.credential_short(cid) == "abcdefgh…"
    assert quota.credential_short("abcdefghijkl") == "abcdefgh…"
    assert quota.credential_short("") == "(없음)" and quota.credential_short("?") == "(없음)"


@pytest.mark.parametrize("label,short", [
    ("youtube.api.v3.V3DataPlaylistItemService.List", "playlistItems.list"),
    ("youtube.api.v3.V3DataVideoService.List", "videos.list"),
    ("youtube.api.v3.V3DataChannelService.List", "channels.list"),
    ("youtube.api.v3.V3DataLiveBroadcastService.List", "liveBroadcasts.list"),
    ("youtube.api.v3.V3DataLiveStreamService.List", "liveStreams.list"),
    ("youtube.api.v3.V3DataPlaylistService.List", "playlists.list"),
    ("youtube.api.v3.Other.Thing", "Other.Thing"),
])
def test_method_short(label, short):
    assert quota.method_short(label) == short


class _FakeCreds:
    token = None

    def refresh(self, request):
        self.token = "adc-tok"


def _reset_tokens():
    quota._TOKEN_CACHE.clear()
    quota._ADC_TOKEN.clear()


def test_token_for_prefers_adc_and_skips_gcloud(monkeypatch):
    _reset_tokens()
    monkeypatch.setattr(quota.google.auth, "default", lambda scopes=None: (_FakeCreds(), "p"))
    monkeypatch.setattr(quota, "gcloud_token_for", lambda *a, **k: pytest.fail("gcloud must not be called"))
    assert quota.token_for("p1", None) == "adc-tok"
    assert quota.token_for("p2", None) == "adc-tok"  # one cached token for every project


def test_adc_asks_for_monitoring_read_scope(monkeypatch):
    _reset_tokens()
    seen = {}
    monkeypatch.setattr(quota.google.auth, "default", lambda scopes=None: seen.update(scopes=scopes) or (_FakeCreds(), "p"))
    quota.adc_token()
    assert seen["scopes"] == ["https://www.googleapis.com/auth/monitoring.read"]


def test_token_for_falls_back_to_gcloud_without_adc(monkeypatch):
    _reset_tokens()

    def no_adc(scopes=None):
        raise quota.google.auth.exceptions.DefaultCredentialsError("none")

    monkeypatch.setattr(quota.google.auth, "default", no_adc)
    monkeypatch.setattr(quota, "gcloud_token_for", lambda project, accounts: f"gcloud-{project}-{accounts}")
    assert quota.token_for("p1", ["a@x.com"]) == "gcloud-p1-['a@x.com']"


def test_token_for_falls_back_when_refresh_fails(monkeypatch):
    _reset_tokens()

    class Bad(_FakeCreds):
        def refresh(self, request):
            raise quota.google.auth.exceptions.RefreshError("denied")

    monkeypatch.setattr(quota.google.auth, "default", lambda scopes=None: (Bad(), "p"))
    monkeypatch.setattr(quota, "gcloud_token_for", lambda project, accounts: "g")
    assert quota.token_for("p1", None) == "g"
