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
