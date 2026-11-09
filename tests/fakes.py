"""Fake Google API service: records kwargs, returns queued responses."""
from __future__ import annotations

import json
from pathlib import Path

import httplib2
from googleapiclient.errors import HttpError

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def http_error(status: int, reason: str | None = None) -> HttpError:
    body = {"error": {"errors": [{"reason": reason}]}} if reason else {}
    return HttpError(httplib2.Response({"status": status}), json.dumps(body).encode())


class _Request:
    def __init__(self, queue: list):
        self._queue = queue

    def execute(self):
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _Resource:
    def __init__(self, svc: "FakeService", name: str):
        self._svc, self._name = svc, name

    def __getattr__(self, method: str):
        def call(**kwargs):
            path = f"{self._name}.{method}"
            if path not in self._svc.queues and any(q.startswith(path + ".") for q in self._svc.queues):
                return _Resource(self._svc, path)  # intermediate resource such as jobs().reports()
            self._svc.calls.append((path, kwargs))
            return _Request(self._svc.queues[path])
        return call


class FakeService:
    def __init__(self, **queues: list):
        # keys like reports__query -> "reports.query"; jobs__reports__list -> jobs().reports().list()
        self.queues = {k.replace("__", "."): list(v) for k, v in queues.items()}
        self.calls: list[tuple[str, dict]] = []

    def __getattr__(self, name: str):
        return lambda: _Resource(self, name)

    def kwargs(self, path: str) -> list[dict]:
        return [kw for p, kw in self.calls if p == path]
