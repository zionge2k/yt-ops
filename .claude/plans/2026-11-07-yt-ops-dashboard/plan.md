# yt-ops — 8채널 통합 상황판 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 하루 한 번 GitHub Actions 가 8개 유튜브 채널을 수집해 Supabase 에 쌓고, 비밀번호로 잠긴 정적 상황판을 GitHub Pages 에 올리며, 꼬비가 같은 패키지를 CLI 로 써서 세부를 뽑는다.

**Architecture:** 순수 수집 함수(API 응답 → 표 행) · 얇은 API 클라이언트 · psycopg upsert 저장소 · DB → `data.json` 렌더러 · AES-GCM 암호화 정적 페이지. 프레임워크 없음. 수집기는 채널 하나 실패해도 계속 돌고 오류를 `yt_run_log` 에 남긴다.

**Tech Stack:** Python 3.12+, google-api-python-client, google-auth, psycopg[binary] 3, python-dotenv, cryptography(AES-GCM), pytest. 프런트는 바닐라 JS + WebCrypto + inline SVG.

**Spec:** `/Users/zion/.claude/plans/resilient-shimmying-lark.md` (승인된 설계, 2026-11-07). 실측 근거와 사용자 결정은 그 문서의 Context 절.

## Global Constraints

- 읽기 전용: 스코프 `youtube.readonly` + `yt-analytics.readonly` 만. 업로드 · 수정 · 삭제 API 호출 금지.
- 토큰 · DB URL · 비밀번호는 로그 · 화면 · 저장소에 절대 찍지 않는다. `.env` 는 `.gitignore`.
- 내부 채널 키는 Mac 키 8개: `soombi urachacha backthen a2p pliwav groovewav soombicafe justsoombi`. 별칭 `chalna→soombi`, `morrow→urachacha` 는 입력에서만 받고 저장은 내부 키로.
- 토큰 경로 우선순위: `$YT_CHANNELS_HOME/channels/<key>/analytics.json` → PC `C:/Users/PC/.config/yt-analytics/<pc_name>.json` → Mac `~/.config/yt-channels/channels/<key>/analytics.json`. PC 이름은 별칭의 역(soombi→chalna, urachacha→morrow).
- 다른 저장소(`yt-auto-live` · `yt-postflow` · `chalna` · `soombi` · 허브 `scripts/yt_analytics.py`)는 수정하지 않는다.
- Analytics 는 3일 늦는다. "최신 집계일" 은 API 가 실제로 돌려준 마지막 `day` 로 정하고 가정하지 않는다.
- SQL 은 멱등(`create table if not exists`, `on conflict ... do update`). 스키마 정본 `db/schema.sql`, 마이그레이션 `db/migrations/YYYY-MM-DD-<topic>.sql`.
- 시간대 표시는 Asia/Seoul. 저장은 UTC ISO 8601 또는 `date`.
- 화면 글: 한국어, 본문 18px 이상, 숫자 28px 이상, 모바일 1열, 애니메이션 없음.
- 신뢰도 표시 4종: 🔵실측 / ⏳집계 / ➗계산 / ≈근사. 숫자 0 과 데이터 없음(`null`)을 구별한다.
- 커밋: 한국어 conventional commits(type/scope 영어), 코드 주석 영어, 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- 테스트: `uv run --with pytest --with "psycopg[binary]" --with google-api-python-client --with google-auth --with python-dotenv --with cryptography pytest tests -q` 또는 `.venv/bin/python -m pytest tests -q`. 네트워크 · DB 는 테스트에서 쓰지 않는다(fixture 와 가짜 객체).

## Review Focus

1. 채널 하나의 토큰이 없거나 만료됐을 때: 나머지 7채널은 수집되고, 그 채널은 `errors` 에 이름 · 오류 종류만(토큰 내용 없이) 남으며 화면은 ⚪. → Task 5 테스트 `test_collect_all_continues_after_channel_error`.
2. Analytics 가 빈 `rows` 를 돌려줄 때(신생 채널 · 기간 밖): 0 행 upsert 로 끝나고 `latest_day` 는 `None`. → Task 2 `test_query_empty_rows`, Task 6 `test_period_summary_with_no_days`.
3. 구독자 1,000 넘는 순간: API 값은 반올림, 정확값은 기준점 + 누적으로 이어진다. → Task 3 `test_exact_subscribers_after_rounding`.
4. 예약 영상이 없고 계획도 없는 채널: 부족 경고를 내지 않는다(⚪ 아님, "계획 없음"). → Task 6 `test_shortage_no_plan_no_warning`.
5. 틀린 비밀번호: 페이지가 "비밀번호가 맞지 않아요" 를 보이고 localStorage 의 잘못된 값을 지운다. → Task 7 Playwright 확인 단계.

---

## Phase 0 — 형아 체크리스트 (코드와 무관, 병행)

- [ ] GCP 프로젝트 543780518761 에서 YouTube Reporting API 켜기 (켜지면 꼬비가 `reportTypes.list` 확인)
- [ ] `~/kkobi/yt-channels-vault/scripts/backup.sh` 재실행 → `analytics.json` 8개 포함 금고 push
- [ ] GitHub 공개 저장소 `zionge2k/yt-ops` 생성, Secrets: `VAULT_SSH_KEY` `AGE_KEY` `SUPABASE_DB_URL` `DASH_PASSWORD`, Pages Source = GitHub Actions
- [ ] Supabase 스키마 적용 승인 (Task 5 끝에 꼬비가 요청)

---

### Task 1: 저장소 뼈대 · 채널 레지스트리 · 인증 경로

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `.gitignore`, `README.md`, `config/channels.toml`, `ytops/__init__.py`, `ytops/__main__.py`, `ytops/registry.py`, `ytops/auth.py`
- Test: `tests/test_registry.py`, `tests/test_auth.py`

**Interfaces:**
- Produces: `registry.Channel` dataclass `(key: str, display: str, channel_id: str | None, is_live: bool, plan_long_per_week: int, plan_shorts_per_day: int, pc_name: str)`; `registry.load_channels(config_path: Path | None = None) -> dict[str, Channel]`; `registry.resolve_key(name: str) -> str` (별칭 → 내부 키, 모르면 `KeyError`); `registry.KEYS: tuple[str, ...]` 8개; `registry.ALIAS: dict[str, str]`.
- Produces: `auth.yt_channels_home() -> Path | None`; `auth.token_path(key: str) -> Path`; `auth.credentials(key: str) -> google.oauth2.credentials.Credentials` (만료면 refresh, 파일 재기록은 `$YT_CHANNELS_HOME` 아래가 아닐 때만).

- [ ] **Step 1: 뼈대 파일**
  - `pyproject.toml`: 패키지 `ytops`, `[project.scripts] ytops = "ytops.cli:main"`, deps 위 Tech Stack, `[project.optional-dependencies] dev = ["pytest"]`. `requirements.txt` 는 같은 deps 핀 없이.
  - `.gitignore`: `.env`, `.venv/`, `__pycache__/`, `site/data.json`, `site/data.enc`, `.superpowers/`, `.claude/*` 단 `!.claude/plans/`.
  - `config/channels.toml`: `[channels.<key>]` 8개에 `display`(숨비찰나 · MORROW · BACK THEN · Adagio to Presto · pli.wav · groove.wav · 숨비카페 · JustSoombi), `is_live`(soombi · backthen · justsoombi 만 true), `plan_long_per_week = 0`, `plan_shorts_per_day = 0`(계획은 숨비가 나중에 채움), 그리고 `[thresholds] up_pct = 5.0, down_pct = -5.0, shortage_days = 3`.
- [ ] **Step 2: 실패 테스트** `tests/test_registry.py`
  ```python
  def test_resolve_alias(): assert resolve_key("chalna") == "soombi"; assert resolve_key("morrow") == "urachacha"; assert resolve_key("pliwav") == "pliwav"
  def test_resolve_unknown(): with pytest.raises(KeyError): resolve_key("nope")
  def test_load_channels_reads_toml(tmp_path): # TOML 에 2채널 쓰고 load → key·display·is_live·plan·pc_name 확인, pc_name of soombi == "chalna"
  def test_load_channels_merges_channel_id(tmp_path, monkeypatch): # monkeypatch YT_CHANNELS_HOME 에 channels.toml 두고 channel_id 가 붙는지
  ```
  `tests/test_auth.py`
  ```python
  def test_token_path_prefers_env_home(tmp_path, monkeypatch): # YT_CHANNELS_HOME 설정 → <home>/channels/soombi/analytics.json
  def test_token_path_pc_fallback(tmp_path, monkeypatch): # env 없음, PC 폴더(monkeypatch 된 상수)에 chalna.json 존재 → 그 경로
  def test_token_path_mac_fallback(tmp_path, monkeypatch): # 둘 다 없음 → ~/.config/yt-channels/channels/soombi/analytics.json
  ```
- [ ] **Step 3: 실행해 실패 확인** `pytest tests -q` → ImportError
- [ ] **Step 4: 구현** `registry.py`(tomllib), `auth.py`(`scripts/yt_analytics.py` 의 `token_path`/`secret_path` 를 이식하되 PC 폴더 상수는 모듈 변수 `PC_KEYS` 로 두어 테스트에서 바꿀 수 있게)
- [ ] **Step 5: 테스트 통과 확인**
- [ ] **Step 6: 커밋** `feat(core): 패키지 뼈대 · 채널 레지스트리 · 토큰 경로`

### Task 2: Analytics · Data API 얇은 클라이언트

**Files:**
- Create: `ytops/analytics.py`, `ytops/data.py`
- Test: `tests/test_analytics.py`, `tests/test_data.py`, `tests/fixtures/*.json`

**Interfaces:**
- Consumes: `auth.credentials`.
- Produces: `analytics.AnalyticsClient(service)` 와 `analytics.for_key(key) -> AnalyticsClient`; `AnalyticsClient.query(start: date, end: date, dims: str, metrics: str, filters: str | None = None, sort: str | None = None, max_results: int = 200) -> list[dict]` — 행 키는 columnHeaders 이름, `INTEGER`/`FLOAT` 열은 숫자로 변환, `rows` 없으면 `[]`, 결과가 `max_results` 와 같으면 `startIndex` 로 다음 페이지를 이어 받는다(상한 5,000행), 429/5xx 는 지수 백오프 3회(`time.sleep` 은 주입 가능).
- Produces: `data.DataClient(service)` 와 `data.for_key(key)`; `channel_stats() -> dict` (`channels.list(part="snippet,statistics,contentDetails,status", mine=True)` 의 item); `uploads(max_items: int | None = None) -> list[dict]` (uploads 재생목록 전체를 50개씩 `videos.list(part="snippet,contentDetails,status,liveStreamingDetails")` 로 받은 item 목록); `active_broadcasts() -> list[dict]` (`liveBroadcasts.list(part="snippet,contentDetails,status", broadcastStatus="active")` — `mine` 넣지 않음); `videos(ids: list[str]) -> list[dict]`; `stream_health(stream_id: str) -> dict` (`liveStreams.list(part="status", id=...)` 의 status).

- [ ] **Step 1: fixture** 실제 응답 모양을 익명화해 `tests/fixtures/analytics_day_contenttype.json`(columnHeaders+rows, 2일×3유형), `analytics_empty.json`(rows 없음), `videos_list.json`(예약 private+publishAt 1개, 쇼츠 PT17S 1개, 라이브 보관 1개, 롱폼 PT2H 1개), `broadcasts_active.json`, `livestreams_status.json`.
- [ ] **Step 2: 실패 테스트** 가짜 service 객체(`execute()` 가 fixture 반환, 호출 인자 기록)로:
  `test_query_converts_types`, `test_query_empty_rows`, `test_query_paginates_with_start_index`(1쪽 200행 → 2쪽 요청에 `startIndex=201`), `test_query_retries_on_503`(2회 실패 후 성공, sleep 호출 2회), `test_uploads_batches_50`, `test_active_broadcasts_has_no_mine_param`.
- [ ] **Step 3: 실패 확인** → **Step 4: 구현** → **Step 5: 통과 확인**
- [ ] **Step 6: 커밋** `feat(api): Analytics · Data API 클라이언트`

### Task 3: 수집기 ① 채널 일별 · 구독자 스냅샷 · 정확 구독자

**Files:**
- Create: `ytops/collect/__init__.py`, `ytops/collect/context.py`, `ytops/collect/channel_daily.py`, `ytops/collect/subs.py`, `ytops/subscribers.py`
- Test: `tests/test_channel_daily.py`, `tests/test_subs.py`, `tests/test_subscribers.py`

**Interfaces:**
- Consumes: Task 2 클라이언트.
- Produces: `context.CollectContext(key: str, channel: Channel, analytics: AnalyticsClient, data: DataClient, today: date, collected_at: datetime)`; 각 수집기 모듈은 `collect(ctx, start: date, end: date) -> dict[str, list[dict]]` (표 이름 → 행). `collect/__init__.py` 의 `COLLECTORS: list[tuple[str, module]]` 순서 `channel_daily, subs, video, video_daily, schedule, live`(뒤 둘은 Task 4 에서 추가).
- Produces 행 모양 `yt_channel_daily`: `channel_key, day, views, min_shorts, min_live, min_vod, min_unspec, min_lol_live, min_lol_ondemand, subs_gained, subs_lost, views_shorts, engaged_views_shorts, subs_gained_shorts, collected_at`. 세 쿼리(스펙 "수집 쿼리" 1 · 2 · 3) 결과를 `day` 로 합친다. 어떤 쿼리에 없는 날은 그 열이 `None`(0 아님).
- Produces 행 `yt_subs_snapshot`: `channel_key, taken_on, api_subscribers, exact_subscribers(None 가능), monetized`.
- Produces `subscribers.exact_subscribers(baseline: tuple[date, int] | None, daily: list[tuple[date, int, int]], latest_day: date | None, api_now: int) -> int | None`: 기준점(1,000 미만일 때 저장한 정확값과 날짜)이 있으면 기준일 다음날부터 `latest_day` 까지 (gained−lost) 누적, 그 뒤 날짜는 모름 → 그대로 돌려줌. 기준점이 없고 `api_now < 1000` 이면 `api_now`(정확). 기준점 없고 ≥1000 이면 `None`.
- Produces `channel_daily.yearly_minutes(ctx) -> dict` (스펙 쿼리 5: 최근 365일 `dims=month,creatorContentType` → `{"min_live":…, "min_vod":…, "min_shorts":…, "start":…, "end":…}`), `yt_channel_meta` 가 아니라 render 가 쓰도록 `yt_channel_daily` 와 별개로 `yt_yearly_minutes` 표 행 1개(`channel_key, as_of, min_live, min_vod, min_shorts, start_day, end_day`) 를 `channel_daily.collect` 결과에 포함한다.

- [ ] **Step 1: 실패 테스트** `test_channel_daily_merges_three_queries`(fixture 3개 → 2행, 열 값 검증), `test_channel_daily_missing_query_leaves_none`, `test_subs_snapshot_row`, `test_exact_subscribers_after_rounding`(기준점 (11-01, 998), daily 11-02 +5/−1, 11-03 +3/0, latest 11-03, api_now 1000 → 1005), `test_exact_subscribers_no_baseline_under_1000`, `test_exact_subscribers_no_baseline_over_1000_is_none`.
- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 통과**
- [ ] **Step 5: 커밋** `feat(collect): 채널 일별 · 구독자 스냅샷 · 정확 구독자 계산`

### Task 4: 수집기 ② 영상 · 영상 일별 · 예약 · 라이브

**Files:**
- Create: `ytops/collect/video.py`, `ytops/collect/video_daily.py`, `ytops/collect/schedule.py`, `ytops/collect/live.py`, `ytops/videos.py`
- Modify: `ytops/collect/__init__.py` (COLLECTORS 에 등록)
- Test: `tests/test_video.py`, `tests/test_video_daily.py`, `tests/test_schedule.py`, `tests/test_live.py`

**Interfaces:**
- Produces `videos.content_kind(item: dict) -> str`: `liveStreamingDetails` 있으면 `live_archive`, 아니면 ISO 8601 duration ≤ 180초 → `short`, 그 외 `long`, duration 파싱 실패 → `unknown`. `videos.duration_seconds(iso: str) -> int | None`.
- Produces 행 `yt_video`: `video_id, channel_key, title, published_at, publish_at, privacy, duration_s, content_kind, thumbnail_url(snippet.thumbnails.medium.url), last_seen_at` (first_seen_at 은 DB 에서 `on conflict` 때 유지).
- Produces 행 `yt_video_daily`: `video_id, channel_key, day, views, engaged_views, minutes, avd_s, avp, subs_gained, subs_lost` (스펙 쿼리 4, `dims=video,day`).
- Produces 행 `yt_schedule`(예약 즉석 표이자 저장용): `channel_key, video_id, title, publish_at, content_kind, seen_at` — `privacy == "private"` 이고 `publish_at` 이 있는 영상만.
- Produces 행 `yt_live_snapshot`: `channel_key, taken_at, broadcast_id, life_cycle, concurrent(int|None), health, stream_status, actual_start, title`. 활성 방송이 없으면 `broadcast_id=None, life_cycle="none"` 1행. 동시접속 키가 없으면 `None`(0 아님).

- [ ] **Step 1: 실패 테스트** `test_content_kind_short_long_live_unknown`, `test_video_rows_from_fixture`, `test_video_daily_rows`, `test_schedule_only_private_with_publish_at`, `test_live_none_row_when_no_broadcast`, `test_live_concurrent_none_not_zero`.
- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 통과**
- [ ] **Step 5: 커밋** `feat(collect): 영상 · 예약 · 라이브 수집기`

### Task 5: 스키마 · 저장소 · CLI(collect / backfill / status)

**Files:**
- Create: `db/schema.sql`, `db/migrations/2026-11-07-initial.sql`(schema 와 같은 내용), `ytops/store.py`, `ytops/runner.py`, `ytops/cli.py`
- Modify: `ytops/__main__.py` (→ `cli.main()`)
- Test: `tests/test_store.py`, `tests/test_runner.py`, `tests/test_cli.py`

**Interfaces:**
- Produces 표(스펙 "Supabase 스키마" 7개 + `yt_schedule` + `yt_yearly_minutes`), 모두 `enable row level security`, 정책 없음. PK: `yt_channel_daily(channel_key, day)`, `yt_subs_snapshot(channel_key, taken_on)`, `yt_video(video_id)`, `yt_video_daily(video_id, day)`, `yt_live_snapshot(channel_key, taken_at)`, `yt_schedule(channel_key, video_id)`, `yt_yearly_minutes(channel_key, as_of)`, `yt_manual(channel_key, field)`, `yt_run_log(run_id)`.
- Produces `store.connect()` (`.env` 의 `SUPABASE_DB_URL`, psycopg autocommit — `music_supabase.py` 패턴), `store.upsert(conn, table: str, rows: list[dict], pk: list[str], keep: tuple[str, ...] = ()) -> int` (`keep` 열은 `on conflict` 때 기존값 유지, 예: `first_seen_at`), `store.fetch(conn, sql: str, params=()) -> list[dict]`, `store.apply_schema(conn, path)`.
- Produces `runner.run_collect(keys: list[str], *, days: int = 10, video_days: int = 10, dry_run: bool, conn=None, today=None) -> RunResult(run_id, started_at, latest_day, errors: list[dict], counts: dict[str, int])`: 채널마다 ctx 를 만들고 COLLECTORS 를 돌리며, 한 채널의 예외는 `errors` 에 `{"channel": key, "stage": name, "error": type(e).__name__, "message": str(e)[:200]}` 로 남기고 계속. `dry_run` 이면 표별 행 수와 표본 2행을 stdout 에 찍고 DB 는 만지지 않음. 끝에 `yt_run_log` 1행. `backfill` 은 `days=90, video_days=28`.
- Produces CLI: `ytops collect [--channel K|--all] [--days N] [--dry-run]`, `ytops backfill [--days 90] [--channel|--all]`, `ytops status`(표별 행 수 · 마지막 run), `ytops schema --apply`(승인 뒤 실행용, 실행 전 확인 문구 출력).

- [ ] **Step 1: 실패 테스트** `test_upsert_sql_has_on_conflict_and_keep`(가짜 cursor 로 생성된 SQL 문자열 검사), `test_collect_all_continues_after_channel_error`(두 채널 중 하나의 analytics 가 raise → errors 1개, 다른 채널 counts > 0), `test_dry_run_touches_no_db`(conn 이 None 인데도 끝남), `test_cli_resolves_alias`(`--channel chalna` → runner 에 `soombi`).
- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 통과**
- [ ] **Step 5: 실제 dry-run** `.venv/bin/python -m ytops collect --all --dry-run --days 3` 를 Mac 에서 돌려 8채널 × 표별 행 수가 찍히는지 확인하고 출력 머리 20줄을 보고서에 적는다(토큰 없음).
- [ ] **Step 6: 커밋** `feat(store): 스키마 · upsert 저장소 · collect/backfill CLI`

### Task 6: 렌더러 (DB → data.json)

**Files:**
- Create: `ytops/render.py`, `ytops/periods.py`
- Modify: `ytops/cli.py` (`ytops render --out PATH [--today YYYY-MM-DD]`)
- Test: `tests/test_periods.py`, `tests/test_render.py`

**Interfaces:**
- Consumes: `store.fetch`, `registry.load_channels`, `[thresholds]`.
- Produces `periods.window(latest_day: date, days: int) -> tuple[date, date]` (끝 = latest_day), `periods.previous(window) -> tuple[date, date]`, `periods.pct_change(cur: float | None, prev: float | None) -> float | None` (prev 0 또는 None → None), `periods.status_of(pct: float | None, up: float, down: float) -> "green" | "yellow" | "red" | "grey"`.
- Produces `render.shortage(plan_long_per_week: int, plan_shorts_per_day: int, scheduled: list[dict], today: date, days: int = 3) -> dict` → `{"long": {"need": n, "have": m, "status": "ok|short|none"}, "shorts": {...}}` — 계획 0 이면 `none`(경고 아님). need = 앞 `days` 일 기준 계획 수(롱폼 `ceil(plan_long_per_week * days / 7)`, 쇼츠 `plan_shorts_per_day * days`), have = 그 창 안 publish_at 개수.
- Produces `render.build(conn, *, today: date, config) -> dict` 와 `data.json` 모양:
  ```
  {"generated_at", "latest_day", "lag_days", "trust": {"subscribers":"live","watch":"lagged",...},
   "channels": [{"key","display","is_live","subscribers": {"api","exact"}, "errors": [...]}],
   "periods": {"7": {"start","end","prev_start","prev_end",
                     "channels": {"<key>": {"views": {"cur","prev","pct","status","spark":[...]},
                                             "subs_net": {...}, "watch_hours": {...}}}},
               "28": ..., "90": ...},
   "live": {"<key>": {"days_with_live","hours_live","hours_ondemand","last_snapshot": {...}}},
   "schedule": {"<key>": {"long": n, "shorts": n, "next_long", "next_shorts", "next7": [{"date","long","shorts"}], "shortage": {...}}},
   "monetization": {"<key>": {"subs_exact","subs_pct","hours_approx","hours_pct","official": {"value","as_of"} | null}},
   "shorts": {"<key>": {"views","engaged_ratio","subs_per_1k"}},
   "errors": [...]}
  ```
  스파크라인은 창 안 일별 값 목록(없는 날 `null`). `watch_hours = (min_live + min_vod) / 60`, `subs_net = gained − lost`. `hours_approx` 는 `yt_yearly_minutes` 최신 행의 `(min_live + min_vod)/60`.

- [ ] **Step 1: 실패 테스트** `test_window_and_previous`, `test_pct_change_none_when_prev_zero`, `test_status_thresholds`(+5→green, 0→yellow, −6→red, None→grey), `test_period_summary_with_no_days`(행 없음 → cur None, status grey, spark 빈 목록), `test_shortage_no_plan_no_warning`, `test_shortage_short_when_under_plan`, `test_build_shape_from_fake_rows`(가짜 fetch 로 키 존재 확인).
- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 통과**
- [ ] **Step 5: 커밋** `feat(render): 기간 비교 · 부족 판정 · data.json 렌더러`

### Task 7: 암호화 · 정적 페이지

**Files:**
- Create: `ytops/crypt.py`, `site/index.html`, `site/app.js`, `site/crypt.js`, `site/style.css`, `site/sample.json`(렌더 모양의 예시 데이터, 가짜 숫자)
- Modify: `ytops/cli.py` (`ytops encrypt IN OUT` — 비밀번호는 `DASH_PASSWORD` 환경변수만, 인자로 받지 않음)
- Test: `tests/test_crypt.py`, Playwright 확인(서브에이전트가 MCP 브라우저로 직접)

**Interfaces:**
- Produces `crypt.encrypt(plaintext: bytes, password: str) -> bytes` — JSON `{"v":1,"kdf":"pbkdf2-sha256","iter":200000,"salt":b64,"iv":b64,"ct":b64}`; `crypt.decrypt(blob: bytes, password: str) -> bytes`. AES-256-GCM, salt 16B, iv 12B. `site/crypt.js` 는 같은 형식을 WebCrypto 로 푼다(`deriveKey PBKDF2` → `AES-GCM decrypt`).
- 페이지: 상단 고정 줄(기준일 · 지연 일수 · 생성 시각 · 신뢰도 범례), 기간 토글 7/28/90, 구역 ①~⑤ 는 스펙 "화면" 절 그대로. 비밀번호 입력 → 성공 시 localStorage `ytops_pw` 저장(try/catch), 실패 시 "비밀번호가 맞지 않아요" + 저장값 삭제. `data.enc` 가 없으면 `sample.json` 을 읽어 "예시 데이터" 띠를 보인다(개발용).

- [ ] **Step 1: 실패 테스트** `test_roundtrip`, `test_wrong_password_raises`, `test_envelope_fields`.
- [ ] **Step 2: 실패 확인** → **Step 3: crypt.py 구현** → **Step 4: 통과**
- [ ] **Step 5: 페이지 구현** (`sample.json` 로 먼저)
- [ ] **Step 6: 브라우저 확인** `cd site && python -m http.server 8765` 뒤 Playwright 로 375px · 1280px 에서 ① 성적표 8행 · ② 라이브 3채널 · ③ 달력 7열 · ④ 진행 막대 · ⑤ 쇼츠 표가 보이는지, 틀린 비밀번호 문구가 뜨는지 확인하고 스크린샷 2장을 `.superpowers/` 가 아닌 `docs/screens/` 에 저장.
- [ ] **Step 7: 커밋** `feat(site): 비밀번호 잠금 정적 상황판`

### Task 8: GitHub Actions 워크플로 · 문서

**Files:**
- Create: `.github/workflows/daily.yml`, `docs/runbook.md`
- Modify: `README.md`

**Interfaces:**
- 워크플로: 스펙 "워크플로 daily.yml" 절 그대로. 금고 단계는 `/Users/zion/kkobi/yt-auto-live/.github/workflows/control.yml` 37~52행을 복사(저장소 `zionge2k/yt-channels-vault`, `VAULT_SSH_KEY`, `AGE_KEY`, `YT_CHANNELS_HOME`). 입력 `backfill_days`(기본 0; >0 이면 `ytops backfill --days N` 을 collect 대신). 단계 순서: checkout → 금고 → setup-python 3.12 + `pip install -r requirements.txt` → `python -m ytops collect --all` → `python -m ytops render --out "$RUNNER_TEMP/data.json"` → `DASH_PASSWORD=… python -m ytops encrypt "$RUNNER_TEMP/data.json" site/data.enc` → `actions/upload-pages-artifact(path: site)` → `actions/deploy-pages`. `permissions: contents: read, pages: write, id-token: write`. `concurrency: {group: daily, cancel-in-progress: false}`, `timeout-minutes: 20`. collect 가 errors 를 남기면 마지막 단계에서 `exit 1`(배포는 그 전에 끝나게 순서 유지).
- `docs/runbook.md`: 형아 Phase 0 체크리스트, 비밀번호 교체 절차, 수동 실행법, 꼬비 CLI 예시(스펙 "꼬비 CLI" 절), PC 에서 쓰는 법.

- [ ] **Step 1: 워크플로 작성** → `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/daily.yml'))"` 로 문법 확인
- [ ] **Step 2: 문서 작성**
- [ ] **Step 3: 커밋** `ci: 하루 1회 수집 · 암호화 배포 워크플로 · 런북`

### Task 9: 요청 시 CLI (live · shorts · schedule · query · manual)

**Files:**
- Modify: `ytops/cli.py`
- Create: `ytops/reports.py`
- Test: `tests/test_reports.py`

**Interfaces:**
- `ytops live --channel K|all [--save]`: 채널별 `yt_live_snapshot` 행을 즉석 표로(🔴 bad / 🟢 good, 동시접속 `-` 는 None). `--save` 면 DB 에 추가.
- `ytops shorts --channel K --days 28 --top 20`: `dims=video` + `filters=creatorContentType==shorts` 로 영상별 views · engagedViews · 비율 · subs/1k · 제목(yt_video 또는 Data API 로 보강).
- `ytops schedule --channel K|all`: 예약 표 즉석(저장 없음).
- `ytops query --channel K|--channels all --dims … --metrics … [--filters] [--days|--start/--end] [--sort] [--max]`: `yt_analytics.py query` 의 상위호환, 여러 채널이면 `channel` 열을 앞에 붙여 하나의 TSV.
- `ytops manual set K FIELD VALUE --as-of DATE [--note]` / `ytops manual list`.
- `reports.tsv(rows: list[dict], cols: list[str]) -> str`, `reports.table(rows, cols) -> str`(한글 폭 맞춘 텍스트 표).

- [ ] **Step 1: 실패 테스트** `test_tsv_and_table_with_korean_width`, `test_query_multi_channel_prefixes_column`, `test_live_table_marks_bad`.
- [ ] **Step 2: 실패 확인** → **Step 3: 구현** → **Step 4: 통과**
- [ ] **Step 5: 실제 실행** `.venv/bin/python -m ytops live --channel all`, `… schedule --channel all` 을 Mac 에서 돌려 출력 머리를 보고서에.
- [ ] **Step 6: 커밋** `feat(cli): 라이브 · 쇼츠 · 예약 · 질의 · 손입력 명령`

### Task 10: 통합 검증 (형아 Phase 0 완료 뒤, 컨트롤러가 직접)

- [ ] `ytops schema --apply` (승인 뒤) → `ytops status`
- [ ] `ytops backfill --days 90 --all` → `collect --all` 2회 → 표별 행 수 동일(멱등)
- [ ] `ytops render --out /tmp/d.json` → 스펙 "검증" 절 대조값(BACK THEN 쇼츠 순증 +40 · liveStream 133.6h, pli.wav 쇼츠 +120, 11/1~2) 과 ±3%
- [ ] GitHub 저장소 push → `workflow_dispatch(backfill_days=90)` → 로그에 토큰 없음 → Pages 열림 → 숨비 폰 확인
- [ ] 허브 `map.md` · `CHANGES.md` 한 줄, `ai-learnings.md`, 플랜 `INDEX.md` 완료 처리, 메모리 갱신
