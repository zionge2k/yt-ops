from pathlib import Path

from ytops import auth


def test_token_path_prefers_env_home(tmp_path, monkeypatch):
    monkeypatch.setenv("YT_CHANNELS_HOME", str(tmp_path))
    assert auth.token_path("soombi") == tmp_path / "channels" / "soombi" / "analytics.json"


def test_token_path_pc_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("YT_CHANNELS_HOME", raising=False)
    pc = tmp_path / "pc"
    pc.mkdir()
    (pc / "chalna.json").write_text("{}")
    monkeypatch.setattr(auth, "PC_KEYS", pc)
    monkeypatch.setattr(auth, "MAC_CH", tmp_path / "mac")
    assert auth.token_path("soombi") == pc / "chalna.json"


def test_token_path_mac_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("YT_CHANNELS_HOME", raising=False)
    mac = tmp_path / "mac"
    monkeypatch.setattr(auth, "PC_KEYS", tmp_path / "no-pc")
    monkeypatch.setattr(auth, "MAC_CH", mac)
    assert auth.token_path("soombi") == mac / "soombi" / "analytics.json"


def test_token_path_accepts_pc_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("YT_CHANNELS_HOME", str(tmp_path))
    assert auth.token_path("morrow") == tmp_path / "channels" / "urachacha" / "analytics.json"


def test_should_rewrite_only_outside_env_home(tmp_path, monkeypatch):
    monkeypatch.setenv("YT_CHANNELS_HOME", str(tmp_path / "home"))
    assert not auth.should_rewrite(tmp_path / "home" / "channels" / "soombi" / "analytics.json")
    assert auth.should_rewrite(tmp_path / "other" / "analytics.json")
    monkeypatch.delenv("YT_CHANNELS_HOME")
    assert auth.should_rewrite(Path("/anywhere/analytics.json"))


def test_write_private_makes_token_owner_only(tmp_path):
    path = tmp_path / "keys" / "soombi" / "analytics.json"
    auth.write_private(path, '{"token": "x"}')
    assert path.read_text(encoding="utf-8") == '{"token": "x"}'
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_write_private_tightens_existing_file(tmp_path):
    path = tmp_path / "analytics.json"
    path.write_text("old", encoding="utf-8")
    path.chmod(0o644)
    auth.write_private(path, "new")
    assert path.read_text(encoding="utf-8") == "new"
    assert path.stat().st_mode & 0o777 == 0o600
