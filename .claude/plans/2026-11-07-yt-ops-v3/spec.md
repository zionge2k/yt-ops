# yt-ops 화면 3판 — 숨비 요구 (2026-11-07 밤)

사장님(숨비) 지시. 쇼츠는 **구독 유입에서만** 센다. 다른 모든 실적(시청시간 · 상위 영상 · 추이)은 쇼츠를 뺀다.
"유효 시청시간" = `min_live + min_vod` (분 → 시간). 화면에는 설명 문장을 두지 않는다 — 숫자 · 그림 · 짧은 라벨만.

## 색 (전 화면 공통)

| 뜻 | 색 이름 | 값 |
|---|---|---|
| 좋음 · 우상향 | red | `--red: #D9243C` |
| 중간 · 유지 | purple | `--purple: #7A4FD6` |
| 우려 · 우하향 | blue | `--blue: #2F6FE0` |
| 자료 없음 | grey | `--off` |

- **추세 색**(`status`): 창을 반으로 갈라 뒤 절반 합 ÷ 앞 절반 합 → pct. `pct >= up_pct(5)` red · `<= down_pct(-5)` blue · 사이 purple · 계산 불가 grey. (`periods.half_trend(values) -> pct|None`, `periods.color_of(pct, up, down) -> "red"|"purple"|"blue"|"grey"`.)
- **체력 색**(`health`): `monetized` 가 true 면 red. 아니면 `score = min(subs_pct, hours_pct)`: `>= 70` red · `< 30` blue · 사이 purple · 둘 중 하나라도 None 이면 grey.
- 옛 green/yellow 는 없앤다(`status_of` 는 남겨도 되지만 render 는 쓰지 않는다).

## 채널 순서 (모든 화면 고정)

`soombi(숨비찰나) · backthen(BACK THEN) · urachacha(MORROW) · a2p(Adagio to Presto) · justsoombi(JustSoombi) · soombicafe(숨비카페) · groovewav(groove.wav) · pliwav(pli.wav)` — `render.ORDER` 상수, `data.json.order` 로도 내보낸다.

## 화면 (hash 라우트 · 한 페이지 앱 · 상단 탭 3개 + 채널 심화)

PC 우선. 그리드: ≥1200px 4열 · 800~1199 2열 · 폰 1열. 글자 18px↑, 숫자 28px↑. 애니메이션 없음. 폰트 Pretendard 유지.

### `#board` 현황판 (기본)
8칸(위4 아래4). 칸마다:
- 채널명 + 심화 버튼(→ `#ch/<key>`)
- **구독자** 지금 수(➗ exact 우선, 없으면 api)
- **48시간 유효시청시간**: 최근 집계된 2일(`latest_day-1 ~ latest_day`) 합(시간, 소수 1). 옆에 직전 2일 대비 % 와 추세 색.
- **라이브**: `is_live` 채널만. 방송 중/꺼짐 · 듀얼(활성 방송 2개↑) · 보는 중 N명 · 조회수 · 찍은 시각. 꺼졌으면 한 줄 "꺼짐". `is_live` 아니면 "라이브 없음" 작게.
- 칸 테두리/띠 색 = 체력 색(`health`).

### `#subs` 구독자 증감
8칸. 칸마다 그래프 2개: **365일**(창 안 첫 자료일부터 latest_day 까지) · **14일**. 선 = 날짜별 구독자 수(복원값: `지금 구독자 − 그 날 이후 순증 누적`), 아래 작은 막대 = 일별 순증(gained−lost). 선 색 = 추세 색(순증 기준 half_trend). 창 합계 순증 숫자 하나.

### `#watch` 유효 시청시간
8칸. 창 토글 **365 / 28 / 7**(한 번에 하나, 페이지 공통). 막대(일별 시간) + 창 합계 숫자 + 추세 색.

### `#ch/<key>` 채널 심화 (칸 순서대로 세로)
1. **수익창출**: 막대 2개(구독자/1,000 · 시청시간/4,000). 막대 색 = 체력 색. 띠/설명 없음. `monetized` 면 "수익창출 중" 라벨.
2. **구독자 현황**(subscribedStatus==SUBSCRIBED): 성별·나이(가로 막대, 큰 순) · 지역 Top 5(시청시간 순) · **시청 시간대**(손입력, 비어 있으면 "—" · `yt_manual` field `peak_hours`, `note` 열에 글).
3. **시청자 현황**(UNSUBSCRIBED): 같은 구성. 시청 시간대 손입력 field `peak_hours_viewers`.
4. **롱폼 상위 3**(최근 28일 시청시간, `content_kind == long`): 썸네일 · 공개일 · 제목 · 시간 · 조회.
5. **라이브 상위 3**(`content_kind == live_archive`): 같은 구성.
6. **구독 유입**(최근 28일): 쇼츠 / 롱폼 / 라이브 / 기타 각 gained, 이탈(lost) 합. 가로 막대.
7. **음악 장르**(최근 28일, 재생목록 기준): 영상의 재생목록 제목별 시청시간(쇼츠 제외) 합 Top 5 + 비율. 영상이 여러 목록에 들면 각 목록에 다 센다(≈ 표시).

상단: 생성 시각 · 집계 기준일 · 지연 일수 한 줄. 48시간 미갱신 띠 · 비밀번호 · 오류 목록은 그대로. 예약 7일 표 · 쇼츠 표 · 상태 문장(떨어짐/흔들림…) · verdict 는 **없앤다**.

## data.json 3판 모양 (render.build 가 만든다 · site 가 읽는다)

```
{
 "v": 3, "generated_at", "latest_day", "lag_days",
 "order": ["soombi","backthen","urachacha","a2p","justsoombi","soombicafe","groovewav","pliwav"],
 "channels": [{"key","display","is_live","collect_failed","errors":[...]}],   // ORDER 순
 "board": {"<key>": {
    "subscribers": int|null,
    "h48": {"cur": float|null, "prev": float|null, "pct": float|null, "status": color, "days": [d1, d2]},
    "live": null | {"on": bool, "dual": bool, "count": int, "viewers": int|null, "views": int|null, "title": str|null, "taken_at": iso},
    "health": color,
    "monet": {"subs": int|null, "subs_pct": float|null, "hours": float|null, "hours_pct": float|null, "monetized": bool}
 }},
 "subs_trend": {"<key>": {"365": {"start","end","total_net": int|null, "status": color,
                                  "series": [{"day","total": int|null,"net": int|null}]},
                          "14": {...}}},
 "watch_trend": {"<key>": {"365": {"start","end","total": float|null, "status": color, "series": [{"day","hours": float|null}]},
                           "28": {...}, "7": {...}}},
 "detail": {"<key>": {
    "monet": (board.monet 와 같음),
    "audience": {"subscribers": SEG, "viewers": SEG},
       // SEG = {"age_gender": [{"age":"age35-44","gender":"female","pct": float}], "country": [{"country":"KR","views":int,"minutes":float}], "peak_hours": str|null, "as_of": date|null}
    "top_long": [{"video_id","title","thumb","published_at","hours","views"}],   // ≤3
    "top_live": [...],
    "subs_sources": {"days": 28, "shorts": int|null, "vod": int|null, "live": int|null, "other": int|null, "lost": int|null},
    "genres": [{"name","hours","share"}]   // ≤5, 28일
 }},
 "errors": [...]
}
```

- 숫자 0 과 null 은 구별(없는 날은 null). 날짜는 `YYYY-MM-DD`, 시각은 ISO UTC.
- `subs_trend` 365 창의 `start` = max(latest_day−364, 그 채널 첫 자료일). series 는 start~latest_day 하루씩(없는 날 null).
- 성별·나이: 시청자(UNSUBSCRIBED)는 `content` vod · live 두 질의를 각 유형 28일 조회수로 가중 평균해 한 목록으로(≈). 구독자(SUBSCRIBED)도 같은 방식. 자료가 전혀 없으면 빈 목록.
- 지역: vod + live 합(views · minutes 더함), minutes 큰 순 5개.

## 수집 추가 (ytops/collect · db/migrations/2026-11-07-v3.sql)

1. `yt_channel_daily` 열 추가: `subs_gained_vod integer`, `subs_gained_live integer`(쿼리 2 의 subscribersGained 를 videoOnDemand/liveStream 으로도 저장. 기존 `subs_gained_shorts` 와 같은 방식 — day 가 있으면 0 초기화).
2. `yt_live_snapshot` 열 추가: `views bigint`(방송 영상 `statistics.viewCount`). `data.videos()` part 에 `statistics` 추가.
3. 새 표 `yt_audience(channel_key, as_of date, segment text, content text, dim text, key text, views bigint, minutes numeric, pct numeric, primary key(channel_key, as_of, segment, content, dim, key))`.
   새 수집기 `collect/audience.py`: 창 = `today-31 ~ today-1`. segment ∈ {subscribed, unsubscribed} × content ∈ {vod(videoOnDemand), live(liveStream)}:
   - `dims=ageGroup,gender metrics=viewerPercentage sort=-viewerPercentage filters=subscribedStatus==SUBSCRIBED;creatorContentType==videoOnDemand` → dim `age_gender`, key `"<age>/<gender>"`, pct.
   - `dims=country metrics=views,estimatedMinutesWatched sort=-estimatedMinutesWatched max 25 같은 filters` → dim `country`, key 국가코드.
   - 그리고 content 별 가중치용으로 `dims=creatorContentType metrics=views` 같은 subscribedStatus 필터 → dim `weight`, key 유형, views.
   (실측 2026-11-07: 이 조합들 모두 200. SUBSCRIBED 는 행이 적거나 빈 경우가 많다 — 빈 결과는 행 0, 오류 아님.)
4. 새 표 `yt_playlist(channel_key, playlist_id, title, item_count, seen_at, primary key(playlist_id))`, `yt_playlist_item(playlist_id, video_id, channel_key, primary key(playlist_id, video_id))`.
   새 수집기 `collect/playlists.py`: `playlists.list(mine=True, part=snippet,contentDetails, maxResults=50)` 페이지 전부 → 각 `playlistItems.list(part=contentDetails)` 페이지 전부. `DataClient.playlists()`, `DataClient.playlist_items(playlist_id)` 추가. 채널별 replace(REPLACE_PER_CHANNEL 에 두 표 추가 — 지운 목록이 남지 않게).
5. `yt_manual` 은 그대로(`note` 에 글). `ytops manual set K peak_hours 0 --note "..."` 로 넣는다(value 는 무시). render 는 `field in (peak_hours, peak_hours_viewers)` 의 `note` 를 읽는다.
6. 백필 365일: `runner` 가 channel_daily 창을 **180일씩 잘라** 여러 번 수집(쿼리 2 가 1,000행 상한). `backfill --days 365` 가 통째로 돌게. video_daily 는 그대로 28일.
7. CLI `collect --only live` (수집기 이름 목록으로 제한) 추가 — 라이브 전용 워크플로가 쓴다.
8. 워크플로 `.github/workflows/live.yml`: 20분마다(`*/20 * * * *`) + dispatch. 단계는 daily 와 같되 수집은 `python -m ytops collect --all --only live`, 그다음 render · encrypt · deploy. `concurrency: {group: pages, cancel-in-progress: false}` — daily.yml 도 같은 group 으로 바꾼다. 60일 enable 단계는 daily 에만.

## 테스트
- 기존 테스트는 계속 통과(Windows 에서 `test_auth` chmod 2개는 원래 실패 — 무시).
- 새로: audience 행 변환(fixture) · playlists 페이지 합치기 · channel_daily 새 두 열 · live views · runner 180일 분할(창 경계 날짜) · periods.half_trend/color_of · render v3 모양(가짜 fetch) · `--only`.

## 금지
- 다른 저장소 수정 금지. 스코프는 readonly 둘만. 토큰·DB 주소를 찍지 않는다.
- 커밋 메시지 한국어 conventional, 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. 커밋은 맏이(꼬비)가 한다 — 에이전트는 커밋하지 않는다.
