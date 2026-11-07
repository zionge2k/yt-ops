from datetime import date

import pytest

from fakes import FakeService, fixture, http_error
from ytops.analytics import AnalyticsClient

D1, D2 = date(2026, 11, 1), date(2026, 11, 2)


def client(svc, sleeps=None):
    return AnalyticsClient(svc, sleep=(sleeps.append if sleeps is not None else lambda s: None))


def test_query_converts_types():
    svc = FakeService(reports__query=[fixture("analytics_day_contenttype.json")])
    rows = client(svc).query(D1, D2, "day,creatorContentType", "views,estimatedMinutesWatched,averageViewPercentage",
                             sort="day", filters="video==vid00001")
    assert len(rows) == 6
    first = rows[0]
    assert first == {"day": "2026-11-01", "creatorContentType": "shorts", "views": 4673,
                     "estimatedMinutesWatched": 572, "averageViewPercentage": 81.25}
    assert type(first["views"]) is int and type(first["averageViewPercentage"]) is float
    kw = svc.kwargs("reports.query")[0]
    assert kw == dict(ids="channel==MINE", startDate="2026-11-01", endDate="2026-11-02",
                      metrics="views,estimatedMinutesWatched,averageViewPercentage",
                      dimensions="day,creatorContentType", maxResults=200, startIndex=1,
                      sort="day", filters="video==vid00001")


def test_query_omits_optional_params():
    svc = FakeService(reports__query=[fixture("analytics_empty.json")])
    client(svc).query(D1, D2, "day", "views")
    kw = svc.kwargs("reports.query")[0]
    assert "sort" not in kw and "filters" not in kw


def test_query_empty_rows():
    svc = FakeService(reports__query=[fixture("analytics_empty.json")])
    assert client(svc).query(D1, D2, "day", "views") == []
    assert len(svc.calls) == 1


def _page(n, offset=0):
    resp = fixture("analytics_day_contenttype.json")
    resp["rows"] = [["2026-11-01", "shorts", offset + i, 1, 1.5] for i in range(n)]
    return resp


def test_query_paginates_with_start_index():
    svc = FakeService(reports__query=[_page(200), _page(50, 200)])
    rows = client(svc).query(D1, D2, "day", "views", max_results=200)
    assert len(rows) == 250
    assert [kw["startIndex"] for kw in svc.kwargs("reports.query")] == [1, 201]
    assert rows[-1]["views"] == 249


def test_query_caps_at_5000_rows():
    svc = FakeService(reports__query=[_page(1000, i * 1000) for i in range(6)])
    rows = client(svc).query(D1, D2, "day", "views", max_results=1000)
    assert len(rows) == 5000
    assert len(svc.calls) == 5


def test_query_retries_on_503():
    ok = fixture("analytics_day_contenttype.json")
    svc = FakeService(reports__query=[http_error(503), http_error(429), ok])
    sleeps = []
    rows = client(svc, sleeps).query(D1, D2, "day", "views")
    assert len(rows) == 6 and sleeps == [1, 2]


def test_query_does_not_retry_client_error():
    svc = FakeService(reports__query=[http_error(403)])
    sleeps = []
    with pytest.raises(Exception):
        client(svc, sleeps).query(D1, D2, "day", "views")
    assert sleeps == [] and len(svc.calls) == 1


def test_query_gives_up_after_three_attempts():
    svc = FakeService(reports__query=[http_error(500)] * 3)
    sleeps = []
    with pytest.raises(Exception):
        client(svc, sleeps).query(D1, D2, "day", "views")
    assert svc.queues["reports.query"] == [] and sleeps == [1, 2]
