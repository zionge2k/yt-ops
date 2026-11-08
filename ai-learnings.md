# ai-learnings — yt-ops

다음에 같은 일을 더 빨리 하기 위한 발견. 날짜는 실측일.

## YouTube Analytics API (2026-11-07 실측)

- **데이터는 3일 늦는다.** 11/07 에 최신 `day` 가 11/04. "어제까지" 를 가정하지 말고 API 가 돌려준 마지막 날을 기준일로 쓴다.
- **`startIndex` 페이지 넘김은 믿을 수 없다.** 같은 질의를 `maxResults=200` 한 번에 받으면 109행, 50씩 넘기면 58행. `country` 보고서는 2쪽에서 500. → 한 번에 크게(1000) 받고, 꽉 차면 `TruncationError` 로 실패를 드러낸다(조용한 절단 금지).
- **`dims=video,day` 는 `filters=video==<id,…>` 가 필수.** 필터 없이는 400 "query not supported". id 50개까지 OK, 100개는 500. 창 길이에 맞춰 `min(50, 999 // 일수)` 개씩 묶는다(꼭 1000행이면 상한에 닿아 TruncationError).
- **`month` 차원은 시작·끝이 월 경계여야 한다.** 아니면 400 "does not align". 365일 합계는 날짜 차원 없이 `creatorContentType` 만으로 받는다.
- **데이터 없는 날은 행이 아예 없다.** 90일 창에 61행이 정상일 수 있다(채널이 어리거나 조회 0). 빈 날은 0 이 아니라 `null` 로 둔다.
- 되는 조합: `day,creatorContentType`(+engagedViews·subscribersGained), `day,liveOrOnDemand`, `ageGroup,gender` + `subscribedStatus==SUBSCRIBED`, `insightTrafficSourceDetail` + `insightTrafficSourceType==YT_SEARCH;creatorContentType==videoOnDemand`.
- `creatorContentTypeUnspecified` 행에 채널 페이지 직접 구독 증감이 따로 잡힌다. 쇼츠+롱폼+라이브 합이 전체와 안 맞는 이유.
- `liveOrOnDemand` 로 라이브 중 시청과 다시보기가 정확히 갈린다. BACK THEN 11/1~2 는 라이브 중 40h, 다시보기 106h.
- 정렬 기본값 `-views` 는 views 가 metrics 에 없으면 400. 기본 정렬은 `-<첫 metric>`.

## YouTube Data API

- `liveBroadcasts.list(broadcastStatus=active)` 에 `mine=true` 를 같이 주면 400. 열쇠가 채널을 가리키니 생략.
- 라이브를 켠 적 없는 채널은 `liveBroadcasts.list` 가 403 → "방송 없음" 으로 처리하고, `is_live=False` 채널은 아예 호출하지 않는다.
- `concurrentViewers` 는 0 이면 키 자체가 없다. 없음 = `None`, "0" = 0 으로 구별.
- 예약 영상은 업로드 재생목록에 `privacyStatus=private` + `status.publishAt` 으로 섞여 나온다. 같은 호출로 예약 캘린더와 공개 목록을 둘 다 만든다.
- `subscriberCount` 는 1,000 이상이면 3자리 반올림. 1,000 미만일 때 값을 기준점으로 적어 두고 Analytics 일별 증감을 더해 정확값을 잇는다.
- Reporting API(노출수·CTR)는 GCP 프로젝트에서 따로 켜야 한다(403 "not enabled"). 켜기 전엔 보고서 유형 실존도 못 본다.
- (11/07 밤 켬) 채널 열쇠는 GCP 프로젝트 둘에 나뉘고 주인 계정도 다르다: `shorts-factory-492813`(543780518761, soombi·backthen·a2p·urachacha) = bono3815, `nowbrd-release`(240395376214, justsoombi·soombicafe·pliwav·groovewav) = zion.geek.nak. `gcloud services enable youtubereporting.googleapis.com --project=… --account=…` 로 켰다. Mac 에 gcloud 설치됨(brew cask `gcloud-cli`).
- 켠 직후 바로 `reportTypes.list` 가 8채널 모두 20종을 돌려줬다(전파 대기 없음). **`channel_reach_basic_a1` · `channel_reach_combined_a1` 실존** — 노출수·CTR 은 여기서. 보고서는 `jobs.create` 한 다음 날부터 쌓이므로 CTR 을 원하면 job 을 먼저 만들어 둬야 한다.

## 공정

- 설계 전에 열쇠로 찔러 보는 게 문서보다 빨랐다. ChatGPT 검증표의 "쇼츠 제외 필터 없음" · "다차원 조합 불가" 는 실측으로 뒤집혔다.
- 단위 테스트가 다 통과해도 실제 dry-run 한 번이 두 가지 400/403 을 잡았다. 수집기 작업 끝엔 꼭 `collect --all --dry-run --days 3`.
- GitHub Actions 비밀값은 `env:` 로만 넘기고 `run:` 안에 `${{ inputs.* }}` 를 넣지 않는다(표현식 주입).

## 2026-11-07 밤 — 재생목록 페이지 무한 반복으로 Data API 하루 한도 소진
- 22:14 KST 꼬비(숨비 PC)가 Actions 에 건 `daily backfill_days=365` 가 새 `playlists` 수집기에서 **playlistItems.list 8,684회/10분**(같은 nextPageToken 이 계속 돌아옴) → shorts-factory 통장 10,000 소진 → 찰나·백댄·모로우·A2P 의 subs·video·live 수집 403.
- 고침: `DataClient._pages` 가 같은 토큰 반복 · MAX_PAGES(100) 에서 멈춤 · 클라이언트당 CALL_BUDGET(600) 넘으면 예외. `uploads()` 도 같은 길. 새 수집기는 **먼저 dry-run 으로 호출 수를 센 뒤** Actions 에 건다.

## 2026-11-08 — Monitoring 으로 한도 알림 걸기
- YouTube 하루 한도 소진은 `serviceruntime.googleapis.com/quota/exceeded`(resource `consumer_quota`, `metric.label.limit_name="defaultPerDayPerProject"`, `quota_metric="youtube.googleapis.com/default"`) 에 BOOL 로 찍힌다. 11/07 사고가 시간당 수십 점으로 남아 있었다. 사용량은 `quota/rate/net_usage`(DELTA) 합, 한도는 `quota/limit`(10,000 / 분당 1,800,000 / 사용자 분당 180,000).
- 알림 정책은 `alertPolicies` REST 로 만들면 gcloud alpha/beta 컴포넌트가 필요 없다. 필터 안에서는 `resource.label.x` · `metric.label.x`(단수), 시계열 조회 groupBy 에서는 `resource.labels.x`(복수) — 둘이 다르다. alignmentPeriod 86400s 도 정책에서 받아들여졌다.
- `documentation.subject` 를 주면 메일 제목이 그 글이 된다. 숨비가 받을 메일은 제목에 한국어로 무슨 일인지 적는다.
