"""YouTube Data API daily quota report from Cloud Monitoring (pure parsing + a thin REST client)."""
from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import urlencode

from ytops.errors import KST, last_quota_reset, next_quota_reset
from ytops.registry import Project

DEFAULT_LIMIT = 10000
ANALYTICS_LIMIT = 100000
TOP_METHODS = 5
DATA_SERVICE = "youtube.googleapis.com"
ANALYTICS_SERVICE = "youtubeanalytics.googleapis.com"
USAGE_TYPE = "serviceruntime.googleapis.com/quota/rate/net_usage"
LIMIT_TYPE = "serviceruntime.googleapis.com/quota/limit"
REQUEST_TYPE = "serviceruntime.googleapis.com/api/request_count"
BASE = "https://monitoring.googleapis.com/v3/projects"
RFC3339 = "%Y-%m-%dT%H:%M:%SZ"


class QuotaAccessError(RuntimeError):
    """No logged-in gcloud account can read a project's Monitoring data."""


# ---------- pure parsing ----------

def reset_window(now: datetime) -> tuple[datetime, datetime]:
    """[last Pacific midnight, now] in UTC: the span the Data API daily quota has been counting."""
    return last_quota_reset(now).astimezone(timezone.utc), now.astimezone(timezone.utc)


def _points(series):
    for ts in series:
        for p in ts.get("points", []):
            yield ts, p, int(p["value"].get("int64Value", 0))


def _hour_key(point, tz) -> str:
    end = datetime.fromisoformat(point["interval"]["endTime"].replace("Z", "+00:00"))
    return end.astimezone(tz).strftime("%m/%d %H시")


def sum_usage(series: list[dict]) -> int:
    return sum(v for _, _, v in _points(series))


def hourly(series: list[dict], tz=KST) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for _, p, v in _points(series):
        out[_hour_key(p, tz)] += v
    return dict(sorted(out.items()))


def requests_by(series: list[dict]) -> list[tuple[str, str, str, str, int]]:
    """(hour, method, credential tail, response code, count) for every non-empty bucket."""
    rows: dict[tuple, int] = defaultdict(int)
    for ts, p, v in _points(series):
        labels = {**ts.get("resource", {}).get("labels", {}), **ts.get("metric", {}).get("labels", {})}
        key = (_hour_key(p, KST), labels.get("method", "?").replace("youtube.api.v3.", ""),
               labels.get("credential_id", "?")[-14:], labels.get("response_code", "?"))
        rows[key] += v
    return [(*k, v) for k, v in sorted(rows.items()) if v]


def limit_from(series: list[dict], default: int = DEFAULT_LIMIT) -> int:
    values = [v for _, _, v in _points(series)]
    return max(values) if values else default


def _hours_text(hours: dict[str, int]) -> str:
    parts, prev_date = [], None
    for key, n in sorted(hours.items()):
        if not n:
            continue
        date, hour = key.split(" ")
        parts.append(f"{hour} {n:,}" if date == prev_date else f"{key} {n:,}")
        prev_date = date
    return " · ".join(parts)


def format_report(project: Project, used: int, limit: int, reset_at_kst: datetime, hours: dict,
                  by_credential: dict[str, int], top_methods: list[tuple[str, int]],
                  analytics_used: int | None, as_of: datetime) -> str:
    pct = used * 100 // limit if limit else 0
    tail = f"· {reset_at_kst:%H:%M} 에 0 으로 돌아감 · {as_of.astimezone(KST):%m/%d %H:%M} 기준"
    if used >= limit:
        head = f"  ⛔ 소진  {used:,} / {limit:,}  ({pct}%)  {tail}"
    else:
        warn = "⚠ " if used * 100 >= 80 * limit else ""
        head = f"  {warn}Data API  {used:,} / {limit:,}  ({pct}%)  {tail}"
    lines = [f"{project.label} ({project.id})", head]
    if _hours_text(hours):
        lines.append(f"  시간대별  {_hours_text(hours)}")
    if by_credential:
        lines.append("  어디서    " + " · ".join(f"…{c} {n:,}" for c, n in by_credential.items()))
    if top_methods:
        lines.append("  메서드    " + " · ".join(f"{m} {n:,}" for m, n in top_methods))
    if analytics_used is not None:
        lines.append(f"  Analytics {analytics_used:,} / {ANALYTICS_LIMIT:,}")
    return "\n".join(lines)


# ---------- Monitoring REST ----------

def default_fetch(url: str, headers: dict) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as resp:
        return json.load(resp)


class Monitoring:
    def __init__(self, token_for: Callable[[str], str], fetch: Callable[[str, dict], dict] = default_fetch):
        self._token_for, self._fetch = token_for, fetch

    def series(self, project: str, metric_filter: str, start: datetime, end: datetime, period_s: int,
               aligner: str, group_by: list[str]) -> list[dict]:
        query = {
            "filter": metric_filter,
            "interval.startTime": start.strftime(RFC3339),
            "interval.endTime": end.strftime(RFC3339),
            "aggregation.alignmentPeriod": f"{period_s}s",
            "aggregation.perSeriesAligner": aligner,
            "aggregation.crossSeriesReducer": "REDUCE_SUM",
            "aggregation.groupByFields": group_by,
        }
        url = f"{BASE}/{project}/timeSeries?{urlencode(query, doseq=True)}"
        data = self._fetch(url, {"Authorization": f"Bearer {self._token_for(project)}"})
        return data.get("timeSeries", [])


_TOKEN_CACHE: dict[str, str] = {}


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)


def _probe(project: str, token: str) -> bool:
    """True when the token can read the project's Monitoring data (cheap descriptor listing)."""
    url = f"{BASE}/{project}/metricDescriptors?pageSize=1"
    try:
        default_fetch(url, {"Authorization": f"Bearer {token}"})
        return True
    except (urllib.error.URLError, OSError):
        return False


def gcloud_token_for(project: str, accounts: list[str] | None, run=_run, probe=_probe) -> str:
    """Access token from the first logged-in gcloud account that can read `project` (cached)."""
    if project in _TOKEN_CACHE:
        return _TOKEN_CACHE[project]
    tried = accounts or []
    if not tried:
        try:
            tried = [a for a in run(["gcloud", "auth", "list", "--format=value(account)"]).split() if a]
        except (OSError, subprocess.CalledProcessError) as e:
            raise QuotaAccessError(f"{project}: gcloud 를 실행하지 못했어요 ({type(e).__name__}). gcloud 로그인부터 확인해 주세요.")
    for account in tried:
        try:
            token = run(["gcloud", "auth", "print-access-token", f"--account={account}"]).strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        if token and probe(project, token):
            _TOKEN_CACHE[project] = token
            return token
    names = ", ".join(tried) or "(로그인된 계정 없음)"
    raise QuotaAccessError(f"{project}: 읽을 수 있는 계정이 없어요. 시도한 계정: {names}")


# ---------- collection ----------

def _flt(metric_type: str, service: str) -> str:
    return f'metric.type="{metric_type}" AND resource.labels.service="{service}"'


def collect_project(mon, project: Project, now: datetime) -> dict:
    """Today's Data API usage for one project as a JSON-safe dict (raises when usage itself cannot be read)."""
    start, end = reset_window(now)
    window_s = max(int((end - start).total_seconds()), 60)
    svc = ["resource.labels.service"]
    usage = mon.series(project.id, _flt(USAGE_TYPE, DATA_SERVICE), start, end, 3600, "ALIGN_SUM", svc)
    try:
        limit = limit_from(mon.series(project.id, _flt(LIMIT_TYPE, DATA_SERVICE), start, end, window_s,
                                      "ALIGN_MAX", svc))
    except Exception:
        limit = DEFAULT_LIMIT
    reqs = requests_by(mon.series(
        project.id, _flt(REQUEST_TYPE, DATA_SERVICE), start, end, 3600, "ALIGN_SUM",
        ["resource.labels.method", "resource.labels.credential_id", "metric.labels.response_code"]))
    try:
        analytics = sum_usage(mon.series(project.id, _flt(USAGE_TYPE, ANALYTICS_SERVICE), start, end,
                                         window_s, "ALIGN_SUM", svc))
    except Exception:
        analytics = None
    by_cred: dict[str, int] = defaultdict(int)
    by_method: dict[str, int] = defaultdict(int)
    for _, method, cred, _, n in reqs:
        by_cred[cred] += n
        by_method[method] += n
    return {
        "project": project.id, "label": project.label, "channels": project.channels,
        "used": sum_usage(usage), "limit": limit, "hours": hourly(usage),
        "by_credential": dict(sorted(by_cred.items(), key=lambda kv: -kv[1])),
        "top_methods": sorted(by_method.items(), key=lambda kv: -kv[1])[:TOP_METHODS],
        "analytics_used": analytics,
        "reset_at": next_quota_reset(now).isoformat(), "as_of": now.astimezone(KST).isoformat(),
    }


def report_from(info: dict) -> str:
    project = Project(info["project"], info["label"], info.get("channels", []))
    return format_report(project, info["used"], info["limit"], datetime.fromisoformat(info["reset_at"]),
                         info["hours"], info["by_credential"], [tuple(m) for m in info["top_methods"]],
                         info["analytics_used"], datetime.fromisoformat(info["as_of"]))
