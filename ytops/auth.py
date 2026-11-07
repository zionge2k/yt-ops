"""Token paths and read-only credentials for the YouTube APIs."""
from __future__ import annotations

import os
from pathlib import Path

from ytops.registry import resolve_key, ALIAS

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]
PC_KEYS = Path("C:/Users/PC/.config/yt-analytics")  # PC token folder, <pc_name>.json
MAC_CH = Path("~/.config/yt-channels/channels").expanduser()
_PC_NAME = {v: k for k, v in ALIAS.items()}


def yt_channels_home() -> Path | None:
    home = os.environ.get("YT_CHANNELS_HOME")
    return Path(home) if home else None


def token_path(key: str) -> Path:
    """Priority: $YT_CHANNELS_HOME, PC folder, then Mac config dir."""
    key = resolve_key(key)
    home = yt_channels_home()
    if home is not None:
        return home / "channels" / key / "analytics.json"
    pc = PC_KEYS / f"{_PC_NAME.get(key, key)}.json"
    if pc.exists():
        return pc
    return MAC_CH / key / "analytics.json"


def should_rewrite(path: Path) -> bool:
    """Refreshed tokens are written back only when outside $YT_CHANNELS_HOME."""
    home = yt_channels_home()
    return home is None or not path.resolve().is_relative_to(home.resolve())


def write_private(path: Path, text: str) -> None:
    """Write a token file readable by the owner only (0600, parent 0700).

    Opens with the mode so a new file is never world-readable even briefly;
    chmod afterwards tightens a file that already existed with looser bits.
    No-op on Windows, where these bits are not enforced.
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(path, 0o600)


def credentials(key: str):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    path = token_path(key)
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        if should_rewrite(path):
            write_private(path, creds.to_json())
    return creds
