from datetime import datetime, timedelta, timezone

import pytest

from fakes import FakeService, http_error
from ytops import reporting
from ytops.data import PagingAborted
from ytops.reporting import REACH_TYPE, ReportDownloadError, ReportingClient

NOW = datetime(2026, 11, 10, 3, 4, 5, 678000, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code, self.text = status_code, text


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.gets = []

    def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return self.responses.pop(0)


def client(svc=None, session=None, sleeps=None):
    return ReportingClient(svc, session, sleep=(sleeps.append if sleeps is not None else lambda s: None))


def test_reach_job_id_picks_the_reach_job():
    svc = FakeService(jobs__list=[{"jobs": [
        {"id": "j-other", "reportTypeId": "channel_basic_a3"},
        {"id": "j-reach", "reportTypeId": REACH_TYPE, "name": "yt-ops reach soombi"}]}])
    assert client(svc).reach_job_id() == "j-reach"
    assert REACH_TYPE == "channel_reach_basic_a1"
    assert svc.kwargs("jobs.list") == [{}]


def test_reach_job_id_none_when_no_job_exists_yet():
    assert client(FakeService(jobs__list=[{}])).reach_job_id() is None
    assert client(FakeService(jobs__list=[{"jobs": [{"id": "x", "reportTypeId": "channel_basic_a3"}]}])).reach_job_id() is None


def test_reach_job_id_follows_next_page_token():
    svc = FakeService(jobs__list=[
        {"jobs": [{"id": "a", "reportTypeId": "channel_basic_a3"}], "nextPageToken": "t1"},
        {"jobs": [{"id": "b", "reportTypeId": REACH_TYPE}]}])
    assert client(svc).reach_job_id() == "b"
    assert [kw.get("pageToken") for kw in svc.kwargs("jobs.list")] == [None, "t1"]


def test_reports_lists_all_pages_with_created_after_in_utc_rfc3339():
    svc = FakeService(jobs__reports__list=[
        {"reports": [{"id": "r1", "downloadUrl": "u1"}], "nextPageToken": "t1"},
        {"reports": [{"id": "r2", "downloadUrl": "u2"}]}])
    got = client(svc).reports("job1", NOW)
    assert [r["id"] for r in got] == ["r1", "r2"]
    first, second = svc.kwargs("jobs.reports.list")
    assert first == {"jobId": "job1", "createdAfter": "2026-11-10T03:04:05.678Z"}
    assert second == {"jobId": "job1", "createdAfter": "2026-11-10T03:04:05.678Z", "pageToken": "t1"}


def test_reports_converts_non_utc_and_treats_naive_as_utc():
    kst = timezone(timedelta(hours=9))
    svc = FakeService(jobs__reports__list=[{}, {}])
    c = client(svc)
    c.reports("j", datetime(2026, 11, 10, 12, 0, tzinfo=kst))
    c.reports("j", datetime(2026, 11, 10, 3, 0))
    assert [kw["createdAfter"] for kw in svc.kwargs("jobs.reports.list")] == [
        "2026-11-10T03:00:00.000Z", "2026-11-10T03:00:00.000Z"]


def test_reports_empty_when_no_report_exists_yet():
    assert client(FakeService(jobs__reports__list=[{}])).reports("j", NOW) == []


def test_paging_stops_on_a_repeated_token_and_aborts_when_endless(monkeypatch):
    # the 2026-11-07 incident: an API handed the same nextPageToken back forever
    same = {"reports": [{"id": "r"}], "nextPageToken": "t"}
    svc = FakeService(jobs__reports__list=[same, same, same])
    assert [r["id"] for r in client(svc).reports("j", NOW)] == ["r", "r"]
    assert len(svc.kwargs("jobs.reports.list")) == 2
    monkeypatch.setattr(reporting, "MAX_PAGES", 3)
    pages = [{"reports": [{"id": str(i)}], "nextPageToken": f"t{i}"} for i in range(10)]
    with pytest.raises(PagingAborted):
        client(FakeService(jobs__reports__list=pages)).reports("j", NOW)


def test_api_calls_retry_transient_errors():
    sleeps = []
    svc = FakeService(jobs__list=[http_error(503), {"jobs": [{"id": "j", "reportTypeId": REACH_TYPE}]}])
    assert client(svc, sleeps=sleeps).reach_job_id() == "j"
    assert sleeps == [1]
    with pytest.raises(Exception) as e:
        client(FakeService(jobs__list=[http_error(403, "forbidden")])).reach_job_id()
    assert e.value.resp.status == 403


def test_download_returns_text_and_uses_a_timeout():
    session = FakeSession(FakeResponse(200, "date,video_id\n"))
    assert client(session=session).download("https://example/report") == "date,video_id\n"
    url, kwargs = session.gets[0]
    assert url == "https://example/report" and kwargs["timeout"] == reporting.DOWNLOAD_TIMEOUT


def test_download_raises_on_non_200_without_echoing_the_url():
    session = FakeSession(FakeResponse(404, "nope"))
    with pytest.raises(ReportDownloadError) as e:
        client(session=session).download("https://example/report?secret=1")
    assert e.value.status == 404 and "404" in str(e.value) and "secret" not in str(e.value)
