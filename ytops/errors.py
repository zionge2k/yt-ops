"""Plain-Korean error text for the dashboard (the only reader is not an engineer)."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
PACIFIC = ZoneInfo("America/Los_Angeles")


def last_quota_reset(now: datetime) -> datetime:
    """The most recent midnight in Pacific time (<= now), returned in KST."""
    local = now.astimezone(PACIFIC)
    # Build the wall-clock midnight from date parts so DST shifts never skew it.
    midnight = datetime(local.year, local.month, local.day, tzinfo=PACIFIC)
    return midnight.astimezone(KST)


def next_quota_reset(now: datetime) -> datetime:
    """The next Pacific midnight after `now` (when the YouTube Data API daily quota resets), in KST."""
    local = now.astimezone(PACIFIC)
    nxt = datetime(local.year, local.month, local.day, tzinfo=PACIFIC) + timedelta(days=1)
    return datetime(nxt.year, nxt.month, nxt.day, tzinfo=PACIFIC).astimezone(KST)


def human_error(err: dict, now: datetime) -> str:
    status = err.get("status")
    reason = err.get("reason")
    name = err.get("error")
    message = err.get("message")
    low = (reason or "").lower()
    if err.get("stage") == "render":
        return f"화면 만들 때 {err.get('table') or '표'} 를 읽지 못했어요 ({name})"
    if status == 403 and ("quota" in low or "dailylimit" in low):
        return f"API 하루 한도 소진 · {next_quota_reset(now):%H:%M} 에 다시 열림"
    if status == 403:
        return f"API 접근 거부 ({reason})" if reason else "API 접근 거부"
    if status == 401 or name == "RefreshError" or "invalid_grant" in (message or ""):
        return "열쇠 만료 · 다시 로그인 필요"
    if name == "PagingAborted":
        return "목록이 끝나지 않아 중단 (기존 데이터 유지)"
    if name == "CallBudgetExceeded":
        return "호출 예산 초과로 중단"
    if name == "ProjectBudgetExceeded":
        return "프로젝트 호출 예산 초과 · 같은 프로젝트의 다른 채널을 지키려고 중단"
    if status is not None:
        return f"API 오류 {status}" + (f" ({reason})" if reason else "")
    return f"{name or '오류'}" + (f": {message[:60]}" if message else "")
