# yt-ops 런북

## ① 형아 Phase 0 체크리스트 (한 번만)

- [ ] GCP 프로젝트 `543780518761` 에서 **YouTube Reporting API** 켜기.
- [ ] `~/kkobi/yt-channels-vault/scripts/backup.sh` 재실행 → analytics.json 이 들어간 금고 갱신 + push.
- [ ] GitHub **공개** 저장소 `zionge2k/yt-ops` 만들고 push.
- [ ] Settings → Secrets and variables → Actions 에 4개 등록.
  - `VAULT_SSH_KEY` — 금고 저장소(`zionge2k/yt-channels-vault`) 읽기용 deploy key 의 비공개 키
  - `AGE_KEY` — 금고 복호화용 age 비공개 키
  - `SUPABASE_DB_URL` — Supabase Session pooler 연결 문자열
  - `DASH_PASSWORD` — 대시보드 비밀번호 (숨비에게 전달)
  - `DASH_PASSWORD` 는 길고 무작위로(예: 20자 이상) — `data.enc` 는 누구나 내려받아 오프라인 대입을 시도할 수 있다.
- [ ] Settings → Pages → Source = **GitHub Actions**.
- [ ] Supabase 스키마 적용: `.env` 에 `SUPABASE_DB_URL` 넣고 `python -m ytops schema --apply`.

공개 저장소라 코드는 누구나 보지만, 데이터는 `site/data.enc`(AES 암호화)로만 올라간다. 비밀번호 없이는 숫자를 볼 수 없다.

## ② 수동 실행

Actions 탭 → **daily** → Run workflow.

- 평소: `backfill_days` 0 → `collect --all` (최근 10일).
- 첫 실행: `backfill_days` = **365** → 과거 1년 채움(구독자 365일 그래프용; channel_daily 는 180일씩 잘라 모은다).
- 자동 실행: 매일 KST 09:30. 라이브 스냅샷은 **live** 워크플로가 20분마다 따로 모아 화면을 다시 만든다(같은 `pages` group 이라 배포는 차례로).
- 수집에 오류가 있어도 화면은 먼저 배포되고, 마지막 단계가 빨갛게 실패한다. 로그의 `errors=` 줄을 본다.

## ③ 비밀번호 교체

1. Secrets 의 `DASH_PASSWORD` 를 새 값으로 바꾼다.
2. Actions → daily → Run workflow (새 비밀번호로 다시 암호화·배포됨).
3. 숨비 브라우저: 옛 비밀번호는 틀렸다는 안내가 뜬다 → 새 비밀번호를 다시 입력.

## ③-2 운영: 「갱신되지 않았어요」 띠

- 화면 맨 위에 「상황판이 N일째 갱신되지 않았어요 — 꼬비에게 알려 주세요」 띠가 뜨면, 화면 생성 시각이 48시간보다 오래됐다는 뜻이다(N = 지난 일수).
- GitHub 은 저장소에 60일간 커밋이 없으면 예약(schedule) 실행을 끈다. daily 워크플로는 매 실행 끝에서 스스로 `enable` 을 호출해 다시 켜므로 보통 자동으로 유지된다.
- 그래도 띠가 뜨면 실행 자체가 멈춘 것이다. Actions 탭에서 daily 가 꺼졌는지(Enable workflow 버튼), 최근 실행이 실패했는지 확인하고 Run workflow 로 한 번 돌린다.

## ④ 꼬비 CLI 예시

```
ytops live --channel all [--save]
ytops shorts --channel backthen --days 28 --top 20
ytops schedule --channel all
ytops query --channels all --dims insightTrafficSourceDetail --filters "insightTrafficSourceType==YT_SEARCH;creatorContentType==videoOnDemand" --days 28
ytops query --channel soombicafe --dims ageGroup,gender --metrics viewerPercentage --filters "subscribedStatus==SUBSCRIBED"
ytops manual set soombi official_watch_hours_365 3164 --as-of 2026-11-03
ytops collect --channel pliwav --dry-run
```

3판(2026-11-07) 추가:

```
# 시청 시간대(손입력): value 는 무시, --note 의 글이 화면에 그대로 보인다
ytops manual set soombi peak_hours 0 --as-of 2026-11-07 --note "평일 저녁 8~11시"
ytops manual set soombi peak_hours_viewers 0 --as-of 2026-11-07 --note "주말 오전"
# 라이브 스냅샷만(20분 워크플로 live.yml 이 쓰는 명령)
ytops collect --all --only live
# 1년 백필: channel_daily 는 180일씩 잘라 수집된다(쿼리 1,000행 상한), video_daily 는 28일 그대로
ytops backfill --all --days 365
# 새 표 적용(멱등) — 맏이만: db/migrations/2026-11-07-v3.sql 과 같은 정의가 schema.sql 에 있다
ytops schema --apply
```

- PC 에서는 `ytops` 대신 `python -m ytops ...`.

## ⑤ PC(Windows)에서 쓰는 법

- 저장소 위치 `C:\kkobi\yt-ops`, 실행은 `python -m ytops ...` (`ytops` 단독 명령은 없다).
- 열쇠는 `C:/Users/PC/.config/yt-analytics/<채널>.json` 을 자동으로 찾는다(별칭 이름: chalna, morrow 등).
- DB 주소는 `.env` 의 `SUPABASE_DB_URL`. `.env` 는 git 에 올라가지 않는다.

## ⑥ 데이터 신뢰도 4종

| 표시 | 뜻 |
|---|---|
| 🔵 실측 | API 가 직접 돌려준 값 |
| ⏳ 집계 | 아직 모이는 중인 값(최근 며칠은 나중에 바뀔 수 있다) |
| ➗ 계산 | 실측 값끼리 계산해 만든 값 |
| ≈ 근사 | 정확하지 않은 추정 |

- 0 과 "데이터 없음"은 다르다. 없음은 빈칸으로 보인다.
- Analytics 는 **약 3일 늦는다**. "최신 집계일"은 API 가 실제로 준 마지막 날짜이고, 오늘이 아니다.
