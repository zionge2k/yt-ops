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
- 첫 실행: `backfill_days` = **180** → 과거 180일 채움(90일 비교에 이전 90일이 필요해서).
- 자동 실행: 매일 KST 09:30.
- 수집에 오류가 있어도 화면은 먼저 배포되고, 마지막 단계가 빨갛게 실패한다. 로그의 `errors=` 줄을 본다.

## ③ 비밀번호 교체

1. Secrets 의 `DASH_PASSWORD` 를 새 값으로 바꾼다.
2. Actions → daily → Run workflow (새 비밀번호로 다시 암호화·배포됨).
3. 숨비 브라우저: 옛 비밀번호는 틀렸다는 안내가 뜬다 → 새 비밀번호를 다시 입력.

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
