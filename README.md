# yt-ops

숨비네 YouTube 8채널을 한 화면에서 보는 읽기 전용 운영 대시보드(Python 패키지 `ytops`).

## 구조

GitHub Actions(매일 KST 09:30) → 수집 → Supabase(Postgres) → 암호화한 JSON → GitHub Pages(비밀번호로 열림)

- 스코프는 `youtube.readonly` · `yt-analytics.readonly` 만 쓴다. 업로드·수정·삭제는 하지 않는다.
- 채널 목록과 계획은 `config/channels.toml`, 채널 ID는 `~/.config/yt-channels/channels.toml`(또는 `$YT_CHANNELS_HOME`)에서 읽는다.
- 토큰·DB 주소는 저장소에 두지 않는다. `.env` 는 git 에서 제외된다.
- 배포되는 데이터는 `site/data.enc`(암호화)뿐이다.

## 쓰는 법

설정 · 수동 실행 · 비밀번호 교체 · CLI 예시는 [docs/runbook.md](docs/runbook.md).
설계와 작업 계획은 `.claude/plans/2026-11-07-yt-ops-dashboard/`.

    python -m ytops --help

## 테스트

    uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
    .venv/bin/python -m pytest tests -q

테스트는 네트워크 · DB 를 쓰지 않는다.
