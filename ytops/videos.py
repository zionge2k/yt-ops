"""Video helpers: ISO 8601 duration parsing and content-kind classification."""
from __future__ import annotations

import re
from datetime import datetime

SHORT_MAX_SECONDS = 180

_DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def duration_seconds(iso: str) -> int | None:
    """Parse an ISO 8601 duration such as PT1H2M3S; P0D is 0; unparsable is None."""
    m = _DURATION.match(iso or "")
    if not m or not any(m.groups()):
        # "P0D" has a day group so it passes; bare "P" / "PT" / "" do not.
        return None
    d, h, mi, s = (int(g or 0) for g in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def content_kind(item: dict) -> str:
    """live_archive when liveStreamingDetails exists, else short (<=180s) / long / unknown."""
    if item.get("liveStreamingDetails"):
        return "live_archive"
    seconds = duration_seconds(item.get("contentDetails", {}).get("duration"))
    if seconds is None:
        return "unknown"
    return "short" if seconds <= SHORT_MAX_SECONDS else "long"


def parse_ts(value: str | None) -> datetime | None:
    """Parse an API ISO timestamp (Z suffix) to an aware datetime; None when absent."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
