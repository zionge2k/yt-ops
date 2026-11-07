"""Channel registry: internal keys, aliases and per-channel config."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

KEYS: tuple[str, ...] = (
    "soombi", "urachacha", "backthen", "a2p",
    "pliwav", "groovewav", "soombicafe", "justsoombi",
)
# PC-side names accepted as input; stored data always uses the internal key.
ALIAS: dict[str, str] = {"chalna": "soombi", "morrow": "urachacha"}
_PC_NAME: dict[str, str] = {v: k for k, v in ALIAS.items()}

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "channels.toml"


@dataclass(frozen=True)
class Channel:
    key: str
    display: str
    channel_id: str | None
    is_live: bool
    plan_long_per_week: int
    plan_shorts_per_day: int
    pc_name: str


def resolve_key(name: str) -> str:
    key = ALIAS.get(name, name)
    if key not in KEYS:
        raise KeyError(name)
    return key


def _external_ids() -> dict[str, str]:
    """channel_id per key from the out-of-repo channels.toml, if present."""
    home = os.environ.get("YT_CHANNELS_HOME")
    base = Path(home) if home else Path("~/.config/yt-channels").expanduser()
    path = base / "channels.toml"
    if not path.exists():
        return {}
    with path.open("rb") as f:
        data = tomllib.load(f)
    return {k: v["channel_id"] for k, v in data.items() if isinstance(v, dict) and "channel_id" in v}


def load_channels(config_path: Path | None = None) -> dict[str, Channel]:
    with (config_path or DEFAULT_CONFIG).open("rb") as f:
        cfg = tomllib.load(f)
    ids = _external_ids()
    return {
        key: Channel(
            key=key,
            display=row["display"],
            channel_id=ids.get(key),
            is_live=bool(row.get("is_live", False)),
            plan_long_per_week=int(row.get("plan_long_per_week", 0)),
            plan_shorts_per_day=int(row.get("plan_shorts_per_day", 0)),
            pc_name=_PC_NAME.get(key, key),
        )
        for key, row in cfg["channels"].items()
    }
