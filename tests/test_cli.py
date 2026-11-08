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
    monkeypatch.setattr(cli.render, "build", lambda conn, *, today, config: {"latest_day": today, "lag_days": 3, "k": "한글"})
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
