# 실행 중 판단 기록 (2026-11-07, SDD 레저에서 옮김)

## Rulings
- Ruling: 새 저장소(커밋 0개)라 worktree 없이 main 에서 바로 작업 — 격리할 기존 코드가 없음 — 틀리면 비용 없음(히스토리 재작성 가능).
- Task 2: Ruling: 백오프 "3회" = 총 3번 시도(sleep 1·2초) 로 확정 — 일 1회 수집이라 충분 — 틀리면 일시 장애 때 하루 비는 비용
- Task 3: Ruling: 구현자가 고른 일별 쿼리 3종(day / day,creatorContentType(+engagedViews) / day,liveOrOnDemand) 을 실측해 통과 확인 — 스펙 쿼리 1~3 과 같은 정보를 담으므로 채택 — 틀리면 없음(실측됨)
- Task 3: Ruling: 연간 쿼리는 `month` 차원 금지(월 경계 정렬 400) → `dims=creatorContentType` 단독, 기간 today-365..today-1 — 스펙 결함 수정 — 틀리면 수익창출 근사 한 칸 비는 비용
- Task 6: Ruling: 예약 "다가올" 판정은 UTC 가 아니라 KST 날짜 기준(next7 과 일관) — 숨비가 보는 날짜와 맞추기 위해 — 틀리면 자정 전후 9시간 경계의 예약 한 건이 칸을 옮기는 비용
- Task 8: Ruling: 배포 아티팩트에서 site/sample.json 제거(공개 사이트에 예시 데이터 노출 방지) — 구현자 제안 채택 — 틀리면 data.enc 없을 때 페이지가 빈 오류만 보이는 비용
- Task 9: Ruling: video_daily 청크 = min(50, 1000 // 일수) 영상 — 10일이면 50, 28일 백필이면 35 — 틀리면 질의 수 증가뿐
- Task 9: Ruling: query 기본 정렬은 `-<첫 metric>` (옛 스크립트의 `-views` 고정은 views 없는 질의에서 400) — 런북 인구통계 예시가 그대로 돌게 — 비용 없음
- Task 9: Ruling: 백필 90일에 channel_daily 가 200행 상한을 넘기므로 max_results=1000 으로 — fix round 2 디스패치 — 틀리면 없음
- Final: Ruling: 정확 구독자 — api_now<1000 이면 api_now 그대로(기준점 무시), ≥1000 구간은 d>=base_day 누적, 화면은 ➗ 표시 — 스펙 "최근 3일 API 근사" 가 plan 에서 빠진 결함 보정 — 틀리면 1,000 전후 며칠 수치 오차
- Final: Ruling: 백필 기본 180일(channel_daily, Q2 ≤ 900행) + render 는 수집 시작일이 prev_start 보다 늦으면 prev/pct None — 90일 비교 엉터리 % 방지 — 틀리면 첫 석 달 90일 카드가 ⚪
- Final: Ruling: 채널별 마지막 집계일 < 전체 latest 이거나 이번 run 에 client/channel_daily 오류면 pct None·grey, 화면에 "수집 실패" — 실패를 하락으로 읽지 않게 — 틀리면 지연 다른 채널이 ⚪ 로 보이는 비용
- Final: Ruling: 예약은 채널별 max(seen_at) 행만 사용(삭제 없음) — 유령 예약 제거 — 틀리면 없음
- Final: Ruling: 추가로 고칠 minor — runner today KST 통일 · 라이브 or 0 제거 · 청크 (MAX_ROWS-1)//n_days · packages.find · 런북 비밀번호 길이 한 줄. 나머지 minor 는 보류

## 보류한 minor (머지 전 수정 아님)
- Task 1: minor (deferred): auth._PC_NAME 이 registry 와 중복 — Channel.pc_name 재사용 권장
- Task 1: minor (deferred): credentials() 갱신·조건부 저장 경로 테스트 없음
- Task 1: minor (deferred): 토큰 파일 재기록 시 0o600 권한 미지정
- Task 1: minor (deferred): ~/.config/yt-channels 기본 경로가 registry 와 auth 두 곳에
- Task 2: minor (deferred): analytics 셀 None → TypeError/"None" 문자열 — None 통과가 안전
- Task 2: minor (deferred): test_analytics 의 pytest.raises(Exception) 너무 넓음 → HttpError
- Task 2: minor (deferred): _retry DELAYS 세 번째 값(4) 미사용 · ATTEMPTS 와 분리
- Task 2: minor (deferred): for_key 두 모듈 중복 · 미테스트
- Task 3: minor (deferred): 엣지 테스트 부족(min_unspec 양수, yearly 빈 결과, Q1 누락일, UNKNOWN 무시)
- Task 3: minor (deferred): Q2/Q3 0-초기화 루프 중복 → _zero_fill 헬퍼
- Task 4: minor (deferred): 구현 후 RED 재현(ImportError) — 재발 금지 고지
- Task 4: minor (deferred): live 엣지 테스트(boundStreamId 없음 · videos() 빈 결과 · 다중 방송) 없음
- Task 4: minor (deferred): live.py 의 liveStreamingDetails 이중 조회
- Task 4: minor (deferred): duration_seconds 타입 힌트 str|None
- Task 4: minor (deferred): test_video_daily_empty 끝의 중복 호출 줄
- Task 5: minor (deferred): upsert 의 assert → ValueError
- Task 5: minor (deferred): first_seen_at 을 수집기 행 dict 에 직접 추가(변이)
- Task 5: minor (deferred): store.connect 의 sys.exit 는 예외로 바꾸고 CLI 에서 변환
- Task 5: minor (deferred): status 명령 fake-conn 테스트 없음
- Task 6: minor (deferred): test_build_shape 에 live/next_long/shortage/lag_days 단언 없음
- Task 6: minor (deferred): KST 경계(UTC 15~16시) 예약 테스트 없음
- Task 6: minor (deferred): run_log errors 행이 dict 아니면 e.get 예외
- Task 6: minor (deferred): render CLI 가 DB 연결을 닫지 않음(다른 명령과 동일)
- Task 7: minor (deferred): 다크모드 accent 버튼 대비 2.3:1 → --on-accent 토큰
- Task 7: minor (deferred): tryDecrypt 가 모든 오류를 "비밀번호 틀림" 으로 — OperationError 만 구분 권장
- Task 7: minor (deferred): data.enc 404 외 실패(500·네트워크)도 sample 로 폴백 — "읽지 못했어요" 분리 권장
- Task 7: minor (deferred): ytops encrypt 입력 파일 없을 때 traceback(exit 1)
- Task 7: minor (deferred): JS↔Python 호환 자동 테스트 없음(고정 envelope fixture 권장)
- Task 7: minor (deferred): innerHTML 삽입 시 autofocus 무시 → .focus()
- Task 7: minor (deferred): "라이브 있던 날 /7" 하드코딩, 구독자 exact 없을 때 🔵 표시 재검토
- Task 8: minor (deferred): 금고 단계에 `rm -rf vault` 누락(control.yml 53행)
- Task 8: minor (deferred): 런북 CLI 예시 `ytops …` vs PC 는 `python -m ytops` 안내 한 줄
- Task 8: minor (deferred): encrypt 단계의 rm sample.json 에 이유 주석
- Task 9: minor (deferred): video_daily 청크 1000//n_days 가 정확히 1000행 가능 → (MAX_ROWS-1)//n_days
- Task 9: minor (deferred): paginate/top_n 불리언 두 개 → mode 하나로 단순화 권장(paginate=True 경로는 프로덕션 호출자 없음)
- Task 9: minor (deferred): manual set 의 nan/inf 허용 · 비숫자 traceback
- Task 9: minor (deferred): query/live 는 전 채널 실패여도 exit 0

## 참고
- Task 4: note: 리뷰어의 max_results=200 절단 우려는 analytics 클라이언트가 startIndex 로 5,000행까지 넘기므로 해당 없음
- Task 4: note: 재리뷰어의 200행 절단 우려 — analytics 클라이언트 startIndex 페이지 넘김으로 해소(5,000행 상한), uploads() 는 전체 페이지
- Task 6: note: channels[].subscribers 는 스냅샷 없으면 None — Task 7 디스패치에 명시
- Task 9: note: 백필 90일에 61행은 API 가 데이터 없는 날을 생략해서임(plain day 질의도 61행) — 결함 아님

## API 한도 (2026-11-07 형아 결정)

- 통장(GCP 프로젝트)은 지금 둘: shorts-factory(숨비찰나·BACK THEN·A2P·MORROW) · nowbrd-release(pli.wav·groove.wav·숨비카페·JustSoombi). 하루 1회 수집은 한 통장 한도의 수 % 수준.
- **모자랄 기능이 생길 때만** 통장을 추가한다(예: 2차 레퍼런스 채널 검색은 100포인트/회라 검색 전용 통장). 지금 4/4 배치는 바꾸지 않는다(열쇠가 통장에 묶여 있어 옮기면 재인증).

## 2차 수정 회차 판단 (2026-11-07, code-review 10건 중 5건 수정)

- 예약 유령: 채널별 삭제 후 다시 넣기(replace) — 빈 결과도 삭제 — 틀리면 두 문장 사이 중단 시 그 채널 예약이 다음 run 까지 빔
- 라이브 403: 사유 liveStreamingNotEnabled 만 "방송 없음", 나머지(쿼터·권한)는 오류로 기록 — 틀리면 없음
- 라이브 PK 에 broadcast_id 추가(none 행은 문자열 "none") — 스키마 미적용 상태라 initial 마이그레이션 직접 수정 — 틀리면 없음
- 백필 기본 185일(3일 지연 + 90일 비교 창) — 틀리면 질의 몇 개 추가뿐
- collect_failed 에 store: 단계 포함 — 틀리면 없음
- 보류: 업로드 목록 3회 조회 · 정확 구독자 공백 검사 · age 바이너리 검증 · localStorage 비밀번호 · 죽은 코드 정리 (다음 회차 또는 형아 결정)

## 3차 수정 회차 (2026-11-07 형아 결정)

- 비밀번호는 숨비 브라우저(localStorage)에 기억시킨다 — 설계 유지, 형아 결정.
- age 바이너리 다운로드 검증은 하지 않는다 — 널리 쓰이는 프로그램 · GitHub 릴리스 직접 다운로드라 위험 낮다고 판단, 형아 결정. 필요해지면 SHA256 핀 한 줄.
- 고칠 것: ① 60일 무활동 자동 비활성화 대비(워크플로 자가 enable + 화면에 "2일 넘게 미갱신" 경고) ② 채널별 "그 채널을 마지막으로 다룬 run" 기준으로 수집 실패 판정(run_log 에 channels 기록).
- 보류: 예약 교체 트랜잭션 · 구독자 수 숨김 처리 · 나머지(이전 회차 보류 목록).
- (추가, 형아 "해") age 배포본 SHA256 핀(두 번 내려받아 동일 확인: 7df45a6c…79d50) + requirements.txt 버전 고정(Mac .venv 에서 dry-run 통과한 조합). yt-auto-live 는 손대지 않음(별도 결정).
- (켜기 당일) uploads 중복 id 는 재생목록 응답 자체의 중복 → 걸러냄(fbf1527). 보류: max_items 가 중복 포함 수로 세어 실제보다 적게 돌아올 수 있음(지금은 max_items 미사용).
- (디자인) 형아 2026-11-07: **PC 화면 우선**, 폰은 볼 수 있으면 됨. 시안은 docs/mockups/ (A 표 · B 카드), 채널 전체 상태 기준은 미정.
- (디자인) 형아 2026-11-07: **B 카드 방향 채택**, 반응형(PC 1600+ 4열 · 1200+ 3열 · 800+ 2열 · 폰 1열)으로 다듬는 중. 채택되면 site/ 를 이 시안으로 교체(Task: 화면 2판).

## 2026-11-07 저녁 — 화면 2판

- Ruling: 7일 비교 기준 = 그 앞 28일 합 ÷ 4 (`periods.compare_window`, min_days=28). 28·90일은 직전 같은 기간. — 한 주 몰아 튼 라이브로 BACK THEN 이 「손보기」로 찍히는 걸 막기 위해(형아 승인) — 틀리면: 7일 추세가 둔해 보일 수 있음.
- Ruling: 상태 말은 「떨어짐 / 흔들림 / 오름 / 확인 불가」. 화면은 지시하지 않고 사실만 말한다(형아 승인).
- 미정(계속): 채널 전체 상태 규칙(빨강 2개↑=떨어짐), 기준값이 아주 작을 때의 퍼센트(+70,900%) 표시.
- 비밀번호 `DASH_PASSWORD` 11/07 19:22 교체(형아 지정). 값은 기록하지 않는다.
- (11/07 밤) Reporting API 두 프로젝트 켬(gcloud). reach 보고서 실존 확인. jobs.create 는 안 함 — 형아 결정 대기(만들면 다음 날부터 CSV 가 쌓이기 시작, 저장은 V2-a 에서).

## 2026-11-07 밤 — Data API 한도 사고

- 사실: 22:14 KST PC 꼬비가 3판(42641a9, playlists 수집기 + live.yml 20분 폴링)을 push 하고 daily 를 BACKFILL_DAYS=365 로 수동 실행. 숨비찰나의 옛 재생목록 `PLaHLZbm2iaaM`(id 13자, 영상 3개)이 2쪽부터 빈 응답 + 같은 nextPageToken 을 영원히 돌려줘 playlistItems.list 8,684회 → shorts-factory 하루 한도 소진(9,939/10,000). Mac · Actions 18:27 실행 · 숨비 앱은 무관(Monitoring 으로 확인). 한도는 11/08 17:00 KST 에 풀림.
- Ruling(PC, 2797c7a): 토큰 반복 차단 · MAX_PAGES 100 · 클라이언트(=채널·run)당 CALL_BUDGET 600. — 틀리면 정상 채널이 600 넘을 때 수집 실패(지금 run 당 ~40~60).
- Ruling(Mac, 보완): 빈 쪽이면 토큰이 새 것이어도 멈춤(사고 응답 그대로 테스트). 
- 미결(형아): live.yml 20분 폴링 유지 여부 — 11/07 낮에 "2시간 폴링도 과하다" 고 뺀 결정과 어긋남. 비용은 작음(Data ~3단위 × 3채널 × 72회/일, Pages 배포 72회/일).
- 할 일: 11/08 17:00 이후 daily 수동 실행으로 shorts-factory 4채널 복구(09:30 자동 실행은 403 으로 실패 예정).

## 2026-11-08 새벽 — 3판 리뷰 · 보강

- 리뷰(opus) HIGH 3 · MED 5 · LOW 8 → 1~3차 수정 24커밋, 테스트 141 → 177(+JS 3). 재검토에서 11 FIXED · 새 발견 8 중 7 고침. 보고서는 세션 임시 폴더(요지는 아래).
- Ruling(형아 11/08): 라이브 스냅샷은 **2시간마다**, 방송 중일 때만 행을 쓴다(`live.yml` cron `0 */2 * * *`). 20분 폴링은 뺌. 방송 뒤 정확히 2시간은 yt-auto-live 연동이 필요해 보류.
- Ruling: run_log 에 `collectors` 기록. 채널 실패 판정 · 오류 목록 · 미갱신 띠(`last_daily_ok_at`)는 "그 수집기를 돌린 마지막 run" 기준. live 전용 run 은 is_live 채널만 만진다.
- Ruling: `half_trend` 는 절반 **평균** 비교(홀수면 가운데 날 버림). 3판 spec 의 "합" 은 홀수 창에서 치우쳤음.
- Ruling: 페이지 상한(MAX_PAGES)에 닿으면 PagingAborted 예외. 재생목록 수가 itemCount 의 90% 미만이면 오류로 끝내 replace 가 좋은 행을 지우지 않음. replace_channel 은 트랜잭션.
- Ruling: 스키마 적용은 daily 에서만. 11/08 01:40 push 직후 Mac 에서 `schema --apply` 수동 실행(옛 live 행 8개 백필 확인).
- 보류(minor): N5 daily·live 동시 Pages 배포 가능성(배포 job 분리) · L6 구독자 복원선 3일 어긋남 · L8 프로젝트 단위 호출 상한 · L2 일회성 cron(`30 8 8 11 *`) 은 11/08 17:30 실행 뒤 지울 것.

## 2026-11-08 낮 — API 사용량을 어떻게 보일까

- 형아 제안: 상황판에 Claude 앱식 사용량 동그라미(숨비가 알아야 한다). 꼬비 의견: 방향은 맞고 모양은 반쯤 과함 — 한도를 쓰는 건 숨비가 아니라 봇이라 숫자를 보고 할 행동이 없고, 평소 3~4% 라 한 달이면 벽지가 됨. 숨비에게 필요한 건 "오늘 데이터 믿어도 돼?" 와 "안 되면 왜 · 언제 돌아와?".
- Ruling(형아 11/08): **1) 오류 문구를 사람 말로**("API 하루 한도 소진 · 17:00 에 다시 열림") **+ GCP 한도 알림 메일**(80% · 소진, 두 프로젝트) 지금. **2) `ytops quota` CLI**(꼬비 조사용) 바로 이어서. **3) 상황판 게이지는 한 달 뒤** 숨비가 숫자를 원하면 — 넣는다면 늘 보이는 동그라미가 아니라 50% 넘을 때만 켜지는 조용한 칩으로. 넣으려면 Actions 가 Monitoring 을 읽어야 하므로 Workload Identity Federation(키 없음) 권장. — 틀리면: 숨비가 숫자를 좋아하는 사람이면 게이지를 당긴다.
- 알림(Monitoring REST 로 생성, gcloud alpha/beta 컴포넌트 없이): 각 프로젝트에 이메일 채널(zion.geek.py) + 정책 둘 — `quota/exceeded`(limit_name=defaultPerDayPerProject) > 0 · `quota/rate/net_usage` 24h 합 > 8,000. 24h 합은 리셋 창(태평양 자정)과 어긋나 전날 저녁 + 당일 사용이 겹치면 80% 가 일찍 울 수 있음(소진 알림은 정확). 숨비 메일은 주소를 받으면 추가. 스크립트는 세션 임시 폴더 `make_alerts.py`.
- 시험: 11/08 15:00 live 실행이 shorts-factory 403 → 소진 알림 첫 실전.
