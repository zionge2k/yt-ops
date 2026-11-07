"""Thin read-only client for the YouTube Data API (v3)."""
from __future__ import annotations

import time
from typing import Callable

from ytops._retry import execute

BATCH = 50
# 2026-11-07 incident: one playlist paged forever (same nextPageToken again and again) and
# burned the day's Data API quota in ten minutes. Two guards, both per client (= per channel per run):
MAX_PAGES = 100        # a list longer than 5,000 items is a bug, not a channel
CALL_BUDGET = 600      # quota units a normal run never approaches (uploads ~40, playlists ~60)


class CallBudgetExceeded(RuntimeError):
    """Raised when one client has made more Data API calls than a sane run needs."""


class DataClient:
    def __init__(self, service, sleep: Callable[[float], None] = time.sleep,
                 call_budget: int = CALL_BUDGET):
        self._service = service
        self._sleep = sleep
        self.calls = 0
        self._budget = call_budget

    def _run(self, request):
        if self.calls >= self._budget:
            raise CallBudgetExceeded(f"Data API call budget ({self._budget}) spent in this run")
        self.calls += 1
        return execute(request, self._sleep)

    def channel_stats(self) -> dict:
        resp = self._run(self._service.channels().list(
            part="snippet,statistics,contentDetails,status", mine=True))
        items = resp.get("items") or []
        return items[0] if items else {}

    def uploads(self, max_items: int | None = None) -> list[dict]:
        # Three collectors (video, video_daily, schedule) read the same list in one run:
        # fetch it once per client to spare the Data API quota (shared with uploads elsewhere).
        if max_items is None and getattr(self, "_uploads_cache", None) is not None:
            return self._uploads_cache
        items = self._uploads(max_items)
        if max_items is None:
            self._uploads_cache = items
        return items

    def _uploads(self, max_items: int | None) -> list[dict]:
        resp = self._run(self._service.channels().list(part="contentDetails", mine=True))
        items = resp.get("items") or []
        if not items:
            return []
        playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        def req(token):
            kwargs = dict(part="contentDetails", playlistId=playlist, maxResults=BATCH)
            if token:
                kwargs["pageToken"] = token
            return self._service.playlistItems().list(**kwargs)

        ids = [i["contentDetails"]["videoId"]
               for i in self._pages(req, max_items=max_items)]
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
                part="snippet,contentDetails,status,liveStreamingDetails,statistics",
                id=",".join(ids[i:i + BATCH])))
            for item in resp.get("items", []):
                if item.get("id") not in seen:
                    seen.add(item.get("id"))
                    out.append(item)
        return out

    def _pages(self, make_request, max_items: int | None = None) -> list[dict]:
        """All items of a paged list; make_request(page_token) builds one request.

        Stops on a missing token, a token already seen (the API can hand the same
        nextPageToken back forever), MAX_PAGES, or max_items.
        """
        items: list[dict] = []
        token = None
        seen_tokens: set[str] = set()
        for _ in range(MAX_PAGES):
            page = self._run(make_request(token))
            items.extend(page.get("items", []))
            token = page.get("nextPageToken")
            if not token or token in seen_tokens or (max_items is not None and len(items) >= max_items):
                return items
            seen_tokens.add(token)
        return items

    def playlists(self) -> list[dict]:
        """Every playlist of the channel (snippet + contentDetails)."""
        def req(token):
            kwargs = dict(part="snippet,contentDetails", mine=True, maxResults=BATCH)
            if token:
                kwargs["pageToken"] = token
            return self._service.playlists().list(**kwargs)
        return self._pages(req)

    def playlist_items(self, playlist_id: str) -> list[dict]:
        """Every item of one playlist (contentDetails only)."""
        def req(token):
            kwargs = dict(part="contentDetails", playlistId=playlist_id, maxResults=BATCH)
            if token:
                kwargs["pageToken"] = token
            return self._service.playlistItems().list(**kwargs)
        return self._pages(req)

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
