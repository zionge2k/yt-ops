"""YouTube Data API daily quota report from Cloud Monitoring (pure parsing + a thin REST client)."""
from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from urllib.parse import urlencode

import google.auth
import google.auth.exceptions
import google.auth.transport.requests

from ytops.errors import KST, last_quota_reset, next_quota_reset
from ytops.registry import Project

DEFAULT_LIMIT = 10000
DAY_LIMIT = "defaultPerDayPerProject"
ANALYTICS_LIMIT = 100000
TOP_METHODS = 5
DATA_SERVICE = "youtube.googleapis.com"
ANALYTICS_SERVICE = "youtubeanalytics.googleapis.com"
USAGE_TYPE = "serviceruntime.googleapis.com/quota/rate/net_usage"
LIMIT_TYPE = "serviceruntime.googleapis.com/quota/limit"
REQUEST_TYPE = "serviceruntime.googleapis.com/api/request_count"
BASE = "https://monitoring.googleapis.com/v3/projects"
RFC3339 = "%Y-%m-%dT%H:%M:%SZ"
MONITORING_SCOPE = "https://www.googleapis.com/auth/monitoring.read"


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


def credential_short(cid: str) -> str:
    """Short, stable label for an OAuth client id: first 8 chars after the project-number prefix."""
    if not cid or cid == "?":
        return "(없음)"
    cid = cid.split(":", 1)[-1].removesuffix(".apps.googleusercontent.com")
    cid = re.sub(r"^\d+-", "", cid)
    return cid[:8] + "…"


_METHOD_RE = re.compile(r"V3Data(\w+?)Service\.(\w+)")


def method_short(label: str) -> str:
    m = _METHOD_RE.search(label)
    if not m:
        return label.replace("youtube.api.v3.", "")
    name, method = m.groups()
    return f"{name[0].lower()}{name[1:]}s.{method.lower()}"


def requests_by(series: list[dict]) -> list[tuple[str, str, str, str, int]]:
    """(hour, method, credential tail, response code, count) for every non-empty bucket."""
    rows: dict[tuple, int] = defaultdict(int)
    for ts, p, v in _points(series):
        labels = {**ts.get("resource", {}).get("labels", {}), **ts.get("metric", {}).get("labels", {})}
        key = (_hour_key(p, KST), method_short(labels.get("method", "?")),
               credential_short(labels.get("credential_id", "?")), labels.get("response_code", "?"))
        rows[key] += v
    return [(*k, v) for k, v in sorted(rows.items()) if v]


def limit_from(series: list[dict], default: int = DEFAULT_LIMIT) -> int:
    # quota/limit holds several limits per service (per day / per minute ...); only the daily one counts.
    values = [v for ts, _, v in _points(series)
              if ts.get("metric", {}).get("labels", {}).get("limit_name", DAY_LIMIT) == DAY_LIMIT]
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
        lines.append("  어디서    " + " · ".join(f"{c} {n:,}" for c, n in by_credential.items()))
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


_ADC_TOKEN: list[str] = []


def adc_token() -> str | None:
    """Access token from Application Default Credentials (Workload Identity Federation on Actions), or None.

    One token serves every project (the service account has monitoring.viewer on all of them), so it is cached.
    """
    if _ADC_TOKEN:
        return _ADC_TOKEN[0]
    try:
        creds, _ = google.auth.default(scopes=[MONITORING_SCOPE])
        creds.refresh(google.auth.transport.requests.Request())
    except google.auth.exceptions.GoogleAuthError:
        return None
    if not creds.token:
        return None
    _ADC_TOKEN.append(creds.token)
    return creds.token


def token_for(project: str, accounts: list[str] | None) -> str:
    """ADC first (keyless, used on Actions), the logged-in gcloud accounts second (a developer's Mac)."""
    return adc_token() or gcloud_token_for(project, accounts)


# ---------- collection ----------

def _flt(metric_type: str, service: str, extra: str = "") -> str:
    return f'metric.type="{metric_type}" AND resource.labels.service="{service}"' + (f" AND {extra}" if extra else "")


def collect_project(mon, project: Project, now: datetime) -> dict:
    """Today's Data API usage for one project as a JSON-safe dict (raises when usage itself cannot be read)."""
    start, end = reset_window(now)
    window_s = max(int((end - start).total_seconds()), 60)
    svc = ["resource.labels.service"]
    usage = mon.series(project.id, _flt(USAGE_TYPE, DATA_SERVICE), start, end, 3600, "ALIGN_SUM", svc)
    try:
        limit = limit_from(mon.series(project.id, _flt(LIMIT_TYPE, DATA_SERVICE, f'metric.labels.limit_name="{DAY_LIMIT}"'), start, end, window_s,
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
        "error": None,
    }


def failed_info(project: Project, now: datetime, message: str) -> dict:
    """Placeholder entry for a project whose usage could not be read (keeps every project in the JSON)."""
    return {"project": project.id, "label": project.label, "channels": project.channels, "used": None,
            "limit": None, "hours": {}, "by_credential": {}, "top_methods": [], "analytics_used": None,
            "reset_at": next_quota_reset(now).isoformat(), "as_of": now.astimezone(KST).isoformat(),
            "error": message}


def report_from(info: dict) -> str:
    project = Project(info["project"], info["label"], info.get("channels", []))
    return format_report(project, info["used"], info["limit"], datetime.fromisoformat(info["reset_at"]),
                         info["hours"], info["by_credential"], [tuple(m) for m in info["top_methods"]],
                         info["analytics_used"], datetime.fromisoformat(info["as_of"]))


# ---------- dashboard shaping ----------

def quota_status(used: int | None, limit: int | None) -> str:
    """ok < 50 %, warn < 80 %, bad < 100 %, out >= 100 %; unknown when usage is not known."""
    if used is None or not limit:
        return "unknown"
    if used >= limit:
        return "out"
    if used * 100 >= 80 * limit:
        return "bad"
    return "warn" if used * 100 >= 50 * limit else "ok"


def _sorted_hours(hours: dict[str, int]) -> list[dict]:
    """Chronological [{h, n}] with zero hours dropped (keys are 'MM/DD HH시'; Dec -> Jan wraps the year)."""
    months = {int(k[:2]) for k in hours}
    wraps = 12 in months and 1 in months

    def order(key: str) -> tuple[int, str]:
        month = int(key[:2])
        return (month + 12 if wraps and month == 1 else month, key[3:])

    return [{"h": k, "n": hours[k]} for k in sorted(hours, key=order) if hours[k]]


def _site_project(info: dict, names: dict[str, str]) -> dict:
    used, limit = info.get("used"), info.get("limit")
    error = info.get("error")
    known = used is not None and not error
    apps = []
    for key, n in sorted((info.get("by_credential") or {}).items(), key=lambda kv: -kv[1]):
        code = key.rstrip("…")
        apps.append({"name": names.get(code, code), "code": code, "n": n})
    return {
        "id": info["project"], "label": info.get("label", info["project"]), "channels": info.get("channels", []),
        "used": used if known else None, "limit": limit,
        "pct": used * 100 // limit if known and limit else None,
        "status": quota_status(used, limit) if known else "unknown",
        "reset_at": info.get("reset_at"),
        "hours": _sorted_hours(info.get("hours") or {}),
        "apps": apps,
        "methods": [{"name": m, "n": n} for m, n in (info.get("top_methods") or [])][:TOP_METHODS],
        "analytics_used": info.get("analytics_used"), "analytics_limit": ANALYTICS_LIMIT,
        "error": error,
    }


def quota_for_site(raw: list | dict, names: dict[str, str]) -> dict:
    """The `quota` block of data.json from `ytops quota --json` output (a list of per-project dicts)."""
    infos = raw.get("projects", []) if isinstance(raw, dict) else raw
    as_of = max((i["as_of"] for i in infos if i.get("as_of")), default=None)
    return {"as_of": as_of, "projects": [_site_project(i, names) for i in infos]}


def load_for_site(path, names: dict[str, str]) -> dict | None:
    """quota_for_site of a quota JSON file; None (with one warning line) when it is missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            return quota_for_site(json.load(f), names)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        print(f"경고: API 사용량 파일을 읽지 못해 건너뜀 ({type(e).__name__})")
        return None
