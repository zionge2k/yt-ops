from datetime import datetime, timezone

import pytest

from ytops.errors import human_error, next_quota_reset

UTC = timezone.utc
NOW = datetime(2026, 11, 8, 5, 0, tzinfo=UTC)


def _hm(dt):
    return dt.strftime("%m/%d %H:%M")


def test_reset_winter_same_day():
    # 05:00Z is 21:00 PST on 11/07; next Pacific midnight is 08:00Z = 17:00 KST on 11/08.
    assert _hm(next_quota_reset(datetime(2026, 11, 8, 5, 0, tzinfo=UTC))) == "11/08 17:00"


def test_reset_winter_next_day():
    # 09:00Z is already past the 08:00Z reset, so the next one is a day later.
    assert _hm(next_quota_reset(datetime(2026, 11, 8, 9, 0, tzinfo=UTC))) == "11/09 17:00"


def test_reset_summer():
    assert _hm(next_quota_reset(datetime(2026, 7, 1, 0, 0, tzinfo=UTC))) == "07/01 16:00"


def test_reset_is_in_kst():
    assert str(next_quota_reset(NOW).tzinfo) == "Asia/Seoul"


@pytest.mark.parametrize("err,text", [
    ({"status": 403, "reason": "quotaExceeded"}, "API 하루 한도 소진 · 17:00 에 다시 열림"),
    ({"status": 403, "reason": "dailyLimitExceeded"}, "API 하루 한도 소진 · 17:00 에 다시 열림"),
    ({"status": 403, "reason": "forbidden"}, "API 접근 거부 (forbidden)"),
    ({"status": 401}, "열쇠 만료 · 다시 로그인 필요"),
    ({"error": "RefreshError"}, "열쇠 만료 · 다시 로그인 필요"),
    ({"error": "Exception", "message": "x invalid_grant y"}, "열쇠 만료 · 다시 로그인 필요"),
    ({"error": "PagingAborted"}, "목록이 끝나지 않아 중단 (기존 데이터 유지)"),
    ({"error": "CallBudgetExceeded"}, "호출 예산 초과로 중단"),
    ({"error": "HttpError", "status": 500, "reason": "backendError"}, "API 오류 500 (backendError)"),
    ({"error": "HttpError", "status": 404}, "API 오류 404"),
    ({"error": "TokenExpired", "message": "refresh token 만료"}, "TokenExpired: refresh token 만료"),
    ({"error": "OperationalError"}, "OperationalError"),
])
def test_human_error(err, text):
    assert human_error(err, NOW) == text


def test_other_message_is_cut_at_60():
    assert human_error({"error": "E", "message": "a" * 100}, NOW) == "E: " + "a" * 60


def test_403_without_reason():
    assert human_error({"status": 403}, NOW) == "API 접근 거부"


def test_render_stage_error_names_the_table():
    e = {"channel": None, "stage": "render", "error": "UndefinedTable", "table": "yt_audience"}
    assert human_error(e, NOW) == "화면 만들 때 yt_audience 를 읽지 못했어요 (UndefinedTable)"
    assert "표" in human_error({"stage": "render", "error": "X"}, NOW)


def test_project_budget_exceeded_text():
    err = {"error": "ProjectBudgetExceeded", "stage": "budget"}
    assert human_error(err, NOW) == "프로젝트 호출 예산 초과 · 같은 프로젝트의 다른 채널을 지키려고 중단"
