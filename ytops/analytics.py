"""Thin read-only client for the YouTube Analytics API (v2)."""
from __future__ import annotations

import time
from datetime import date
from typing import Callable

from ytops._retry import execute

MAX_ROWS = 5000
_CASTS = {"INTEGER": int, "FLOAT": float}


class AnalyticsClient:
    def __init__(self, service, sleep: Callable[[float], None] = time.sleep):
        self._service = service
        self._sleep = sleep

    def query(
        self,
        start: date,
        end: date,
        dims: str,
        metrics: str,
        filters: str | None = None,
        sort: str | None = None,
        max_results: int = 200,
        paginate: bool = True,
    ) -> list[dict]:
        out: list[dict] = []
        start_index = 1
        while len(out) < MAX_ROWS:
            kwargs = dict(
                ids="channel==MINE",
                startDate=start.isoformat(),
                endDate=end.isoformat(),
                metrics=metrics,
                dimensions=dims,
                maxResults=max_results,
                startIndex=start_index,
            )
            if sort:
                kwargs["sort"] = sort
            if filters:
                kwargs["filters"] = filters
            resp = execute(self._service.reports().query(**kwargs), self._sleep)
            page = self._rows(resp)
            out.extend(page)
            if not paginate or len(page) < max_results:
                break
            start_index += max_results
        return out[:MAX_ROWS]

    @staticmethod
    def _rows(resp: dict) -> list[dict]:
        headers = resp.get("columnHeaders", [])
        casts = [_CASTS.get(h.get("dataType"), str) for h in headers]
        names = [h["name"] for h in headers]
        return [
            {n: c(v) for n, c, v in zip(names, casts, row)}
            for row in resp.get("rows") or []
        ]


def for_key(key: str) -> AnalyticsClient:
    from googleapiclient.discovery import build

    from ytops.auth import credentials
    from ytops.registry import resolve_key

    creds = credentials(resolve_key(key))
    return AnalyticsClient(build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False))
