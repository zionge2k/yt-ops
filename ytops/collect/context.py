"""Shared per-channel context passed to every collector."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ytops.analytics import AnalyticsClient
from ytops.data import DataClient
from ytops.registry import Channel


@dataclass
class CollectContext:
    key: str
    channel: Channel
    analytics: AnalyticsClient
    data: DataClient
    today: date
    collected_at: datetime
