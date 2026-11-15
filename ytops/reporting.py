"""Thin read-only client for the YouTube Reporting API (v1): bulk report files, not queries."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable, Iterator, TypeVar

from googleapiclient.errors import HttpError

from ytops.data import MAX_PAGES, PagingAborted

REACH_TYPE = "channel_reach_basic_a1"  # thumbnail impressions + CTR per (date, channel, video)
DOWNLOAD_TIMEOUT = 60  # seconds; requests has no default and a hung download would stall the whole run
# The free quota is 60 requests a minute per project (measured 2026-11-15) and a download counts as two (302 + 200).
RATE_WAITS = (20, 40)  # 429: a full minute in total, so the per-minute window has rolled over by the last try
ERROR_WAITS = (1, 2)   # 5xx: a brief server hiccup

T = TypeVar("T")


def _wait_for(status: int, attempt: int) -> float | None:
    """Seconds to wait before retry number `attempt` (0-based) of a call answered with `status`; None = give up."""
    if status == 429:
        waits = RATE_WAITS
    elif status >= 500:
        waits = ERROR_WAITS
    else:
        return None
    return waits[attempt] if attempt < len(waits) else None


class ReportDownloadError(RuntimeError):
    """A report file download answered something other than 200."""

    def __init__(self, status: int):
        super().__init__(f"report download failed: HTTP {status}")  # no URL: keep it out of logs
        self.status = status


def _rfc3339_utc(moment: datetime) -> str:
    """UTC RFC 3339 with milliseconds, e.g. 2026-11-10T03:04:05.678Z (a naive datetime counts as UTC)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ReportingClient:
    def __init__(self, service, session, sleep: Callable[[float], None] = time.sleep):
        self._service = service
        self._session = session  # authorized requests session, used to download report files
        self._sleep = sleep

    def _retrying(self, call: Callable[[], T]) -> T:
        """Run call(), waiting and retrying while the answer is 429 or 5xx (see _wait_for)."""
        attempt = 0
        while True:
            try:
                return call()
            except (HttpError, ReportDownloadError) as err:
                status = err.status if isinstance(err, ReportDownloadError) else getattr(err.resp, "status", 0)
                wait = _wait_for(status, attempt)
                if wait is None:
                    raise
                self._sleep(wait)
                attempt += 1

    def _pages(self, make_request, items_key: str) -> Iterator[dict]:
        """Response pages of a paged list; make_request(page_token) builds one request.

        Stops on a missing or already seen nextPageToken (an API can hand the same token back
        forever, see data.DataClient._pages) and on an empty page; MAX_PAGES with a token left raises.
        """
        token = None
        seen: set[str] = set()
        for _ in range(MAX_PAGES):
            page = self._retrying(make_request(token).execute)
            yield page
            token = page.get("nextPageToken")
            if not token or token in seen or not page.get(items_key):
                return
            seen.add(token)
        raise PagingAborted(f"paging stopped after {MAX_PAGES} pages with a next page token left")

    def reach_job_id(self) -> str | None:
        """Id of the channel's reach job; None while the job has not been created yet."""
        def request(token):
            return self._service.jobs().list(**({"pageToken": token} if token else {}))

        for page in self._pages(request, "jobs"):
            for job in page.get("jobs") or []:
                if job.get("reportTypeId") == REACH_TYPE:
                    return job["id"]
        return None

    def reports(self, job_id: str, created_after: datetime) -> list[dict]:
        """Every report of the job created after `created_after` (each has id, createTime, downloadUrl ...)."""
        def request(token):
            kwargs = {"jobId": job_id, "createdAfter": _rfc3339_utc(created_after)}
            if token:
                kwargs["pageToken"] = token
            return self._service.jobs().reports().list(**kwargs)

        return [r for page in self._pages(request, "reports") for r in page.get("reports") or []]

    def download(self, url: str) -> str:
        """Body of one report file (CSV text)."""
        def fetch():
            resp = self._session.get(url, timeout=DOWNLOAD_TIMEOUT)
            if resp.status_code != 200:
                raise ReportDownloadError(resp.status_code)
            return resp

        resp = self._retrying(fetch)
        # decode the raw bytes: `.text` guesses ISO-8859-1 for text/csv without a charset, which breaks a BOM
        return resp.content.decode("utf-8-sig")


def for_key(key: str) -> ReportingClient:
    from google.auth.transport.requests import AuthorizedSession
    from googleapiclient.discovery import build

    from ytops.auth import credentials
    from ytops.registry import resolve_key

    creds = credentials(resolve_key(key))
    service = build("youtubereporting", "v1", credentials=creds, cache_discovery=False)
    return ReportingClient(service, AuthorizedSession(creds))
