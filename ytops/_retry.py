"""Shared retry helper for Google API requests."""
from __future__ import annotations

import time
from typing import Callable

from googleapiclient.errors import HttpError

DELAYS = (1, 2, 4)
ATTEMPTS = 3


def _retryable(err: HttpError) -> bool:
    status = getattr(err.resp, "status", 0)
    return status == 429 or status >= 500


def execute(request, sleep: Callable[[float], None] = time.sleep):
    """Run request.execute(), retrying 429/5xx with exponential backoff."""
    for attempt in range(ATTEMPTS):
        try:
            return request.execute()
        except HttpError as err:
            if not _retryable(err) or attempt == ATTEMPTS - 1:
                raise
            sleep(DELAYS[attempt])
