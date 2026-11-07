"""Thin read-only client for the YouTube Data API (v3)."""
from __future__ import annotations

import time
from typing import Callable

from ytops._retry import execute

BATCH = 50


class DataClient:
    def __init__(self, service, sleep: Callable[[float], None] = time.sleep):
        self._service = service
        self._sleep = sleep

    def _run(self, request):
        return execute(request, self._sleep)

    def channel_stats(self) -> dict:
        resp = self._run(self._service.channels().list(
            part="snippet,statistics,contentDetails,status", mine=True))
        items = resp.get("items") or []
        return items[0] if items else {}

    def uploads(self, max_items: int | None = None) -> list[dict]:
        resp = self._run(self._service.channels().list(part="contentDetails", mine=True))
        items = resp.get("items") or []
        if not items:
            return []
        playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        ids: list[str] = []
        token = None
        while max_items is None or len(ids) < max_items:
            kwargs = dict(part="contentDetails", playlistId=playlist, maxResults=BATCH)
            if token:
                kwargs["pageToken"] = token
            page = self._run(self._service.playlistItems().list(**kwargs))
            ids.extend(i["contentDetails"]["videoId"] for i in page.get("items", []))
            token = page.get("nextPageToken")
            if not token:
                break
        ids = list(dict.fromkeys(ids))  # a playlist may list a video more than once
        if max_items is not None:
            ids = ids[:max_items]
        return self.videos(ids)

    def videos(self, ids: list[str]) -> list[dict]:
        ids = list(dict.fromkeys(ids))
        out: list[dict] = []
        seen: set[str] = set()
        for i in range(0, len(ids), BATCH):
            resp = self._run(self._service.videos().list(
                part="snippet,contentDetails,status,liveStreamingDetails",
                id=",".join(ids[i:i + BATCH])))
            for item in resp.get("items", []):
                if item.get("id") not in seen:
                    seen.add(item.get("id"))
                    out.append(item)
        return out

    def active_broadcasts(self) -> list[dict]:
        # `mine` must not be combined with broadcastStatus.
        resp = self._run(self._service.liveBroadcasts().list(
            part="snippet,contentDetails,status", broadcastStatus="active", maxResults=5))
        return resp.get("items", [])

    def stream_health(self, stream_id: str) -> dict:
        resp = self._run(self._service.liveStreams().list(part="status", id=stream_id))
        items = resp.get("items") or []
        return items[0].get("status", {}) if items else {}


def for_key(key: str) -> DataClient:
    from googleapiclient.discovery import build

    from ytops.auth import credentials
    from ytops.registry import resolve_key

    creds = credentials(resolve_key(key))
    return DataClient(build("youtube", "v3", credentials=creds, cache_discovery=False))
