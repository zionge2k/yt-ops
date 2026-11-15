from tests.fakes import http_error
from ytops import cli, runner


def _capture(monkeypatch):
    got = {}

    def fake(keys, **kw):
        got["keys"], got["kw"] = keys, kw
        return runner.RunResult("r", None, None, [], {})

    monkeypatch.setattr(cli.runner, "run_collect", fake)
    monkeypatch.setattr(cli.store, "connect", lambda: "conn")
    return got


def test_cli_resolves_alias(monkeypatch):
    got = _capture(monkeypatch)
    assert cli.main(["collect", "--channel", "chalna", "--dry-run"]) == 0
    assert got["keys"] == ["soombi"]
    assert got["kw"]["dry_run"] is True and got["kw"]["days"] == 10 and got["kw"]["conn"] is None


def test_cli_all_and_backfill_defaults(monkeypatch):
    got = _capture(monkeypatch)
    cli.main(["backfill", "--all"])
    assert len(got["keys"]) == 8
    assert got["kw"]["days"] == 185 and got["kw"]["video_days"] == 28 and got["kw"]["conn"] == "conn"


def test_cli_only_passes_collector_names(monkeypatch):
    got = _capture(monkeypatch)
    assert cli.main(["collect", "--all", "--only", "live", "--dry-run"]) == 0
    assert got["kw"]["only"] == ["live"]
    cli.main(["collect", "--all", "--only", "live, subs", "--dry-run"])
    assert got["kw"]["only"] == ["live", "subs"]
    cli.main(["collect", "--all", "--dry-run"])
    assert got["kw"]["only"] is None


def test_only_empty_is_error(monkeypatch):
    import pytest
    got = _capture(monkeypatch)
    for bad in ("", "  ", " , "):
        with pytest.raises(SystemExit):
            cli.main(["collect", "--all", "--only", bad, "--dry-run"])
    assert "keys" not in got


def test_cli_requires_target(monkeypatch):
    import pytest
    _capture(monkeypatch)
    with pytest.raises(SystemExit):
        cli.main(["collect"])


def test_cli_render_writes_json(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.store, "connect", lambda: "conn")
    monkeypatch.setattr(cli.render, "build", lambda conn, *, today, config, quota=None: {"latest_day": today, "lag_days": 3, "k": "한글"})
    out = tmp_path / "sub" / "data.json"
    assert cli.main(["render", "--out", str(out), "--today", "2026-11-07"]) == 0
    assert '"latest_day": "2026-11-07"' in out.read_text(encoding="utf-8") and "한글" in out.read_text(encoding="utf-8")


def _run_with_errors(monkeypatch, errors):
    monkeypatch.setattr(cli.runner, "run_collect",
                        lambda keys, **kw: runner.RunResult("r", None, None, errors, {}))
    monkeypatch.setattr(cli.store, "connect", lambda: "conn")
    return cli.main(["collect", "--all", "--only", "live"])


def test_quota_exhausted_line_when_every_error_is_a_403_quota(monkeypatch, capsys):
    errs = [runner._error(k, "live", http_error(403, "quotaExceeded")) for k in ("soombi", "a2p")]
    assert _run_with_errors(monkeypatch, errs) == 1
    assert "quota_exhausted=1" in capsys.readouterr().out


def test_no_quota_line_when_some_error_is_something_else(monkeypatch, capsys):
    errs = [runner._error("soombi", "live", http_error(403, "quotaExceeded")),
            runner._error("a2p", "live", RuntimeError("boom")),
            runner._error("pliwav", "live", http_error(403, "forbidden"))]
    assert _run_with_errors(monkeypatch, errs) == 1
    assert "quota_exhausted" not in capsys.readouterr().out


def test_no_quota_line_without_errors(monkeypatch, capsys):
    assert _run_with_errors(monkeypatch, []) == 0
    assert "quota_exhausted" not in capsys.readouterr().out


def _info(pid, used=10):
    return {"project": pid, "label": "L" + pid, "channels": [], "used": used, "limit": 10000, "hours": {},
            "by_credential": {}, "top_methods": [], "analytics_used": None,
            "reset_at": "2026-11-08T17:00:00+09:00", "as_of": "2026-11-08T14:02:00+09:00"}


def test_quota_json_dumps_collected_dict(monkeypatch, capsys):
    import json
    seen = []
    monkeypatch.setattr(cli.commands.quota, "collect_project", lambda mon, p, now: seen.append(p.id) or _info(p.id))
    assert cli.main(["quota", "--json"]) == 0
    assert [i["project"] for i in json.loads(capsys.readouterr().out)] == seen == [
        "shorts-factory-492813", "nowbrd-release"]


def test_quota_project_filter_and_text_report(monkeypatch, capsys):
    monkeypatch.setattr(cli.commands.quota, "collect_project", lambda mon, p, now: _info(p.id, 8500))
    assert cli.main(["quota", "--project", "nowbrd-release", "--account", "a@x.com"]) == 0
    out = capsys.readouterr().out
    assert "nowbrd-release" in out and "shorts-factory" not in out and "⚠ Data API  8,500 / 10,000" in out


def test_quota_unknown_project(monkeypatch, capsys):
    assert cli.main(["quota", "--project", "nope"]) == 2


def test_quota_continues_after_failure_and_fails_only_if_all_fail(monkeypatch, capsys):
    def collect(mon, p, now):
        if p.id == "shorts-factory-492813":
            raise cli.commands.quota.QuotaAccessError("shorts-factory-492813: 읽을 수 있는 계정이 없어요.")
        return _info(p.id)

    monkeypatch.setattr(cli.commands.quota, "collect_project", collect)
    assert cli.main(["quota"]) == 0
    out = capsys.readouterr().out
    assert "읽지 못했어요" in out and "Lnowbrd-release" in out

    def all_fail(mon, p, now):
        raise cli.commands.quota.QuotaAccessError("x")

    monkeypatch.setattr(cli.commands.quota, "collect_project", all_fail)
    assert cli.main(["quota"]) == 1


def test_quota_out_writes_file_and_keeps_failed_projects(monkeypatch, capsys, tmp_path):
    import json

    def collect(mon, p, now):
        if p.id == "nowbrd-release":
            raise cli.commands.quota.QuotaAccessError("nowbrd-release: 읽을 수 있는 계정이 없어요.")
        return _info(p.id)

    monkeypatch.setattr(cli.commands.quota, "collect_project", collect)
    out = tmp_path / "sub" / "quota.json"
    assert cli.main(["quota", "--json", "--out", str(out)]) == 0
    assert capsys.readouterr().out == ""
    rows = json.loads(out.read_text(encoding="utf-8"))
    assert [r["project"] for r in rows] == ["shorts-factory-492813", "nowbrd-release"]
    assert rows[0]["used"] == 10
    assert rows[1]["used"] is None and "읽을 수 있는 계정이 없어요" in rows[1]["error"]


def test_quota_out_exit_1_when_nothing_read_but_file_still_written(monkeypatch, tmp_path):
    import json

    def fail(mon, p, now):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli.commands.quota, "collect_project", fail)
    out = tmp_path / "q.json"
    assert cli.main(["quota", "--json", "--out", str(out)]) == 1
    assert all(r["used"] is None and r["error"] for r in json.loads(out.read_text(encoding="utf-8")))


def _render_args(tmp_path, *extra):
    return ["render", "--out", str(tmp_path / "d.json"), "--today", "2026-11-07", *extra]


def test_render_passes_quota_block(monkeypatch, tmp_path):
    import json
    got = {}
    monkeypatch.setattr(cli.store, "connect", lambda: "conn")
    monkeypatch.setattr(cli.render, "build", lambda conn, *, today, config, quota=None:
                        got.update(quota=quota) or {"latest_day": today, "lag_days": 0})
    f = tmp_path / "q.json"
    f.write_text(json.dumps([_info("proj-a", 1830)]), encoding="utf-8")
    assert cli.main(_render_args(tmp_path, "--quota", str(f))) == 0
    assert got["quota"]["projects"][0]["used"] == 1830 and got["quota"]["projects"][0]["pct"] == 18


def test_render_missing_quota_file_gives_null_and_does_not_fail(monkeypatch, tmp_path, capsys):
    got = {}
    monkeypatch.setattr(cli.store, "connect", lambda: "conn")
    monkeypatch.setattr(cli.render, "build", lambda conn, *, today, config, quota=None:
                        got.update(quota=quota) or {"latest_day": today, "lag_days": 0})
    assert cli.main(_render_args(tmp_path, "--quota", str(tmp_path / "missing.json"))) == 0
    assert got["quota"] is None and "경고" in capsys.readouterr().out
    cli.main(_render_args(tmp_path))
    assert got["quota"] is None


def test_cli_reach_reread_days_is_passed_through(monkeypatch):
    got = _capture(monkeypatch)
    cli.main(["collect", "--channel", "chalna", "--only", "reach", "--reach-reread-days", "30", "--dry-run"])
    assert got["kw"]["reach_reread_days"] == 30
    cli.main(["collect", "--all", "--dry-run"])
    assert got["kw"]["reach_reread_days"] is None
    cli.main(["backfill", "--all", "--dry-run"])
    assert got["kw"]["reach_reread_days"] is None


# ---- discover ----

class _DiscoverData:
    def __init__(self, shortfall, pages, videos):
        self.uploads_shortfall, self.pages, self.video_map = shortfall, list(pages), videos
        self.tokens, self.asked = [], []

    def uploads(self):
        return [{"id": "have1"}]

    def search_mine_page(self, token=None):
        self.tokens.append(token)
        return self.pages.pop(0)

    def videos(self, ids):
        self.asked.append(list(ids))
        return [self.video_map[i] for i in ids if i in self.video_map]


def _sp(*ids, token=None):
    page = {"items": [{"id": {"kind": "youtube#video", "videoId": i}} for i in ids]}
    if token:
        page["nextPageToken"] = token
    return page


def _discover(monkeypatch, data, *args):
    upserts = []
    monkeypatch.setattr(cli.commands, "connect", lambda: "conn")
    monkeypatch.setattr(cli.commands.runner, "known_video_ids", lambda conn, key: ["k1"])
    monkeypatch.setattr(cli.commands, "data_for_key", lambda key, meter=None, known_ids=(): data)
    monkeypatch.setattr(cli.commands.store, "upsert", lambda conn, t, rows, pk, keep=(): upserts.append((t, rows, pk, keep)) or len(rows))
    return cli.main(["discover", "--channel", "chalna", *args]), upserts


def _video(vid):
    return {"id": vid, "snippet": {"title": f"title {vid}", "publishedAt": "2026-04-03T01:00:00Z"},
            "status": {"privacyStatus": "private"}, "contentDetails": {"duration": "PT30S"}}


def test_discover_does_not_search_when_nothing_is_missing(monkeypatch, capsys):
    data = _DiscoverData(0, [], {})
    rc, upserts = _discover(monkeypatch, data)
    assert rc == 0 and data.tokens == [] and upserts == []
    assert "모자란 영상 없음" in capsys.readouterr().out


def test_discover_pages_until_the_missing_videos_are_found(monkeypatch, capsys):
    data = _DiscoverData(2, [_sp("have1", "n1", token="t1"), _sp("n2", "x", token="t2"), _sp("never")],
                         {"n1": _video("n1"), "n2": _video("n2")})
    rc, upserts = _discover(monkeypatch, data)
    assert rc == 0
    assert data.tokens == [None, "t1"]  # two missing, both found on page 2: no third page
    assert data.asked == [["n1", "n2", "x"]]  # the whole page is asked; "x" does not exist
    (table, rows, pk, keep), = upserts
    assert table == "yt_video" and pk == ["video_id"] and keep == ("first_seen_at",)
    assert [r["video_id"] for r in rows] == ["n1", "n2"] and rows[0]["channel_key"] == "soombi"
    assert rows[0]["privacy"] == "private" and rows[0]["first_seen_at"] == rows[0]["last_seen_at"]
    out = capsys.readouterr().out
    assert "title n1" in out and "200" in out  # 2 pages x 100 units


def test_discover_stops_at_max_pages_and_says_what_is_still_missing(monkeypatch, capsys):
    data = _DiscoverData(5, [_sp("a", token="t1"), _sp("b", token="t2"), _sp("c", token="t3")],
                         {i: _video(i) for i in "abc"})
    rc, upserts = _discover(monkeypatch, data, "--max-pages", "2")
    assert data.tokens == [None, "t1"] and len(upserts[0][1]) == 2
    assert "3편" in capsys.readouterr().out  # 5 missing, 2 found


def test_discover_stops_when_the_search_has_no_next_page(monkeypatch):
    data = _DiscoverData(3, [_sp("a")], {"a": _video("a")})
    _discover(monkeypatch, data)
    assert data.tokens == [None]


def test_discover_max_pages_defaults_to_12():
    assert cli.commands.DISCOVER_MAX_PAGES == 12
