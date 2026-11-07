# yt-ops

숨비네 YouTube 8채널을 한 화면에서 보는 읽기 전용 운영 대시보드(Python 패키지 `ytops`).

- 스코프는 `youtube.readonly` · `yt-analytics.readonly` 만 쓴다. 업로드·수정·삭제는 하지 않는다.
- 채널 목록과 계획은 `config/channels.toml`, 채널 ID는 `~/.config/yt-channels/channels.toml`(또는 `$YT_CHANNELS_HOME`)에서 읽는다.
- 토큰·DB 주소는 저장소에 두지 않는다. `.env` 는 git 에서 제외된다.

테스트 실행:

    uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
    .venv/bin/python -m pytest tests -q
