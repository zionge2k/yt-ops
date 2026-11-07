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
    assert got["kw"]["days"] == 90 and got["kw"]["video_days"] == 28 and got["kw"]["conn"] == "conn"


def test_cli_requires_target(monkeypatch):
    import pytest
    _capture(monkeypatch)
    with pytest.raises(SystemExit):
        cli.main(["collect"])
