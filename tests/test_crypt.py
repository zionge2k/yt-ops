import base64
import json

import pytest
from cryptography.exceptions import InvalidTag

from ytops import cli, crypt


def test_roundtrip():
    blob = crypt.encrypt("안녕 데이터".encode(), "pw1234")
    assert crypt.decrypt(blob, "pw1234") == "안녕 데이터".encode()


def test_wrong_password_raises():
    blob = crypt.encrypt(b"secret", "right")
    with pytest.raises(InvalidTag):
        crypt.decrypt(blob, "wrong")


def test_envelope_fields():
    env = json.loads(crypt.encrypt(b"x", "pw"))
    assert set(env) == {"v", "kdf", "iter", "salt", "iv", "ct"}
    assert env["v"] == 1 and env["kdf"] == "pbkdf2-sha256" and env["iter"] == 200000
    assert len(base64.b64decode(env["salt"])) == 16
    assert len(base64.b64decode(env["iv"])) == 12


def test_encrypt_is_randomized():
    assert crypt.encrypt(b"x", "pw") != crypt.encrypt(b"x", "pw")


def test_cli_encrypt_requires_env(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("DASH_PASSWORD", raising=False)
    src = tmp_path / "in.json"
    src.write_text("{}")
    assert cli.main(["encrypt", str(src), str(tmp_path / "out.enc")]) == 2
    assert "DASH_PASSWORD" in capsys.readouterr().out


def test_cli_encrypt_writes_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DASH_PASSWORD", "s3cret-pw")
    src = tmp_path / "in.json"
    src.write_text('{"a": 1}')
    out = tmp_path / "out.enc"
    assert cli.main(["encrypt", str(src), str(out)]) == 0
    assert crypt.decrypt(out.read_bytes(), "s3cret-pw") == b'{"a": 1}'
    assert "s3cret-pw" not in capsys.readouterr().out
