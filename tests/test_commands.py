from datetime import date, datetime, timezone

from ytops import cli, commands


class FakeAnalytics:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def query(self, start, end, dims, metrics, filters=None, sort=None, max_results=200, paginate=True):
        assert paginate is False  # top-N requests must not page past the limit
        self.calls.append((start, end, dims, metrics, filters, sort, max_results))
        return self.rows


class FakeData:
    def __init__(self, videos=(), broadcasts=()):
        self._videos, self._broadcasts = list(videos), list(broadcasts)

    def videos(self, ids):
        return [v for v in self._videos if v["id"] in ids]

    def active_broadcasts(self):
        return self._broadcasts

    def stream_health(self, sid):
        return {"healthStatus": {"status": "bad"}, "streamStatus": "active"}

    def uploads(self):
        return self._videos


def _patch(monkeypatch, analytics=None, data=None, conn="conn"):
    monkeypatch.setattr(commands, "analytics_for_key", lambda k: analytics)
    monkeypatch.setattr(commands, "data_for_key", lambda k: data)
    monkeypatch.setattr(commands, "connect", lambda: conn)
    monkeypatch.setattr(commands, "today", lambda: date(2026, 11, 7))


def test_query_multi_channel_prefixes_column(monkeypatch, capsys):
    fake = FakeAnalytics([{"country": "KR", "views": 5}])
    _patch(monkeypatch, analytics=fake)
    assert cli.main(["query", "--channels", "all", "--dims", "country", "--metrics", "views"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("# ") and "전체" in out[0]
    assert out[1] == "channel\tcountry\tviews"
    assert out[2] == "soombi\tKR\t5" and len(out) == 2 + 8
    assert fake.calls[0][:2] == (date(2026, 10, 10), date(2026, 11, 6))
    assert fake.calls[0][5] == "-views" and fake.calls[0][6] == 25


def test_query_single_channel_alias_no_prefix(monkeypatch, capsys):
    _patch(monkeypatch, analytics=FakeAnalytics([{"country": "KR", "views": None}]))
    cli.main(["query", "--channel", "chalna", "--metrics", "views", "--filters", "a==b", "--start", "2026-11-01", "--end", "2026-11-02"])
    out = capsys.readouterr().out.splitlines()
    assert "soombi" in out[0] and "2026-11-01 ~ 2026-11-02" in out[0] and "a==b" in out[0]
    assert out[1].startswith("country\t") and out[2] == "KR\t-"


def test_live_table_marks_bad(monkeypatch, capsys):
    data = FakeData(
        videos=[{"id": "b1", "snippet": {}, "liveStreamingDetails": {}}],
        broadcasts=[{"id": "b1", "status": {"lifeCycleStatus": "live"},
                     "contentDetails": {"boundStreamId": "s"}, "snippet": {"title": "밤 판"}}],
    )
    saved = {}
    _patch(monkeypatch, data=data)
    monkeypatch.setattr(commands.store, "upsert", lambda conn, t, rows, pk: saved.update(t=t, rows=rows, pk=pk) or len(rows))
    assert cli.main(["live", "--channel", "backthen", "--save"]) == 0
    out = capsys.readouterr().out
    assert "🔴" in out and "밤 판" in out and "concurrent" in out
    assert saved["t"] == "yt_live_snapshot" and saved["pk"] == ["channel_key", "taken_at"]
    assert saved["rows"][0]["concurrent"] is None


def test_live_error_per_channel_continues(monkeypatch, capsys):
    def boom(k):
        if k == "soombi":
            raise RuntimeError("secret")
        return FakeData()
    _patch(monkeypatch)
    monkeypatch.setattr(commands, "data_for_key", boom)
    cli.main(["live", "--channel", "all"])
    out = capsys.readouterr().out
    assert "⚪ " in out and "RuntimeError" in out and "secret" not in out
    assert out.count("none") == 7


def test_shorts_ratios(monkeypatch, capsys):
    rows = [{"video": "v1", "views": 200, "engagedViews": 50, "estimatedMinutesWatched": 1,
             "subscribersGained": 3, "subscribersLost": 0},
            {"video": "v2", "views": 0, "engagedViews": 0, "estimatedMinutesWatched": 0,
             "subscribersGained": 0, "subscribersLost": 0}]
    an = FakeAnalytics(rows)
    _patch(monkeypatch, analytics=an, data=FakeData(videos=[{"id": "v1", "snippet": {"title": "제목" * 30}}]))
    cli.main(["shorts", "--channel", "backthen", "--days", "7", "--top", "5"])
    out = capsys.readouterr().out
    assert "25.0" in out and "15.0" in out
    assert an.calls[0][4] == "creatorContentType==shorts" and an.calls[0][6] == 5
    assert "제목" * 20 in out and "제목" * 21 not in out
    v2 = [l for l in out.splitlines() if l.startswith("v2")][0]
    assert v2.split()[-1] == "-" and v2.split()[-2] == "-"


def test_schedule_sorted_kst(monkeypatch, capsys):
    def v(i, ts):
        return {"id": i, "snippet": {"title": f"t{i}"}, "status": {"privacyStatus": "private", "publishAt": ts},
                "contentDetails": {"duration": "PT30S"}}
    _patch(monkeypatch, data=FakeData(videos=[v("a", "2026-11-09T00:00:00Z"), v("b", "2026-11-08T15:30:00Z")]))
    cli.main(["schedule", "--channel", "a2p"])
    lines = capsys.readouterr().out.splitlines()
    assert "11/09 00:30" in lines[2] and "11/09 09:00" in lines[3]


def test_manual_set_and_list(monkeypatch, capsys):
    got = {}
    _patch(monkeypatch)
    monkeypatch.setattr(commands.store, "upsert", lambda conn, t, rows, pk: got.update(t=t, rows=rows, pk=pk) or 1)
    cli.main(["manual", "set", "chalna", "official_watch_hours_365", "3164", "--as-of", "2026-11-03", "--note", "n"])
    assert got["t"] == "yt_manual" and got["pk"] == ["channel_key", "field"]
    assert got["rows"] == [{"channel_key": "soombi", "field": "official_watch_hours_365", "value": 3164,
                            "as_of": date(2026, 11, 3), "note": "n"}]
    monkeypatch.setattr(commands.store, "fetch", lambda conn, sql, *a: [dict(got["rows"][0], note=None)])
    cli.main(["manual", "list"])
    out = capsys.readouterr().out
    assert "official_watch_hours_365" in out and "3164" in out
