import pytest

from ytops.registry import KEYS, load_channels, load_projects, resolve_key


def test_resolve_alias():
    assert resolve_key("chalna") == "soombi"
    assert resolve_key("morrow") == "urachacha"
    assert resolve_key("pliwav") == "pliwav"


def test_resolve_unknown():
    with pytest.raises(KeyError):
        resolve_key("nope")


def test_keys_are_eight():
    assert len(KEYS) == 8


def test_load_channels_reads_toml(tmp_path, monkeypatch):
    monkeypatch.setenv("YT_CHANNELS_HOME", str(tmp_path / "empty"))
    cfg = tmp_path / "channels.toml"
    cfg.write_text(
        '[channels.soombi]\ndisplay = "A"\nis_live = true\n'
        "plan_long_per_week = 2\nplan_shorts_per_day = 3\n"
        '[channels.pliwav]\ndisplay = "B"\nis_live = false\n'
        "plan_long_per_week = 0\nplan_shorts_per_day = 1\n",
        encoding="utf-8",
    )
    ch = load_channels(cfg)
    assert list(ch) == ["soombi", "pliwav"]
    s = ch["soombi"]
    assert (s.display, s.is_live, s.plan_long_per_week, s.plan_shorts_per_day) == ("A", True, 2, 3)
    assert s.pc_name == "chalna"
    assert s.channel_id is None
    assert ch["pliwav"].pc_name == "pliwav"


def test_load_channels_merges_channel_id(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / "channels.toml").write_text(
        '[soombi]\ndisplay = "x"\nchannel_id = "UCfake1"\nused_by = ["chalna"]\n', encoding="utf-8"
    )
    monkeypatch.setenv("YT_CHANNELS_HOME", str(home))
    cfg = tmp_path / "channels.toml"
    cfg.write_text(
        '[channels.soombi]\ndisplay = "A"\nis_live = true\n'
        "plan_long_per_week = 0\nplan_shorts_per_day = 0\n"
        '[channels.pliwav]\ndisplay = "B"\nis_live = false\n'
        "plan_long_per_week = 0\nplan_shorts_per_day = 0\n",
        encoding="utf-8",
    )
    ch = load_channels(cfg)
    assert ch["soombi"].channel_id == "UCfake1"
    assert ch["pliwav"].channel_id is None


def test_load_projects(tmp_path):
    cfg = tmp_path / "channels.toml"
    cfg.write_text(
        '[channels.soombi]\ndisplay = "A"\n'
        '[projects.p1]\nlabel = "하나"\nchannels = ["soombi", "a2p"]\n'
        '[projects.p2]\nlabel = "둘"\nchannels = ["pliwav"]\n',
        encoding="utf-8",
    )
    projects = load_projects(cfg)
    assert [(p.id, p.label, p.channels) for p in projects] == [
        ("p1", "하나", ["soombi", "a2p"]), ("p2", "둘", ["pliwav"])]
    assert list(load_channels(cfg)) == ["soombi"]  # the new table does not leak into channels


def test_repo_projects_cover_all_channels_once():
    projects = load_projects()
    assert len(projects) == 2
    chans = [c for p in projects for c in p.channels]
    assert len(chans) == 8 and sorted(chans) == sorted(KEYS)
