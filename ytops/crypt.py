"""Password envelope for data.enc: PBKDF2-SHA256 -> AES-256-GCM (WebCrypto compatible)."""
from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITERATIONS = 200_000


def _key(password: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(password.encode("utf-8"))


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def encrypt(plaintext: bytes, password: str) -> bytes:
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(_key(password, salt, ITERATIONS)).encrypt(iv, plaintext, None)
    env = {"v": 1, "kdf": "pbkdf2-sha256", "iter": ITERATIONS,
           "salt": _b64(salt), "iv": _b64(iv), "ct": _b64(ct)}
    return json.dumps(env).encode("utf-8")


def decrypt(blob: bytes, password: str) -> bytes:
    """Raises cryptography.exceptions.InvalidTag on a wrong password."""
    env = json.loads(blob.decode("utf-8"))
    salt, iv, ct = (base64.b64decode(env[k]) for k in ("salt", "iv", "ct"))
    return AESGCM(_key(password, salt, int(env["iter"]))).decrypt(iv, ct, None)
