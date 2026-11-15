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
- Ruling 변경(형아 11/08 13:50): **게이지를 지금 넣는다.** 이유: 숨비가 상황을 알고, 어느 앱이 API 를 비효율적으로 쓰는지 봐야 함. 모양은 머리줄 칩(프로젝트별 %) + `#api` 상세(시간대별 · 열쇠별 · 메서드별). 갱신은 워크플로 실행마다(하루 ~13회).
- 권한: 키 없는 WIF. 서비스 계정 `yt-ops-monitor@nowbrd-release`(monitoring.viewer 두 프로젝트), 풀/제공자 `projects/240395376214/locations/global/workloadIdentityPools/github/providers/github`, 조건 `assertion.repository=='zionge2k/yt-ops'`. 열쇠 이름표(`[credentials]`): 숨비네 `v63007rf`=yt-ops 열쇠(찰나 공용) · `6sl59ntt`=숨비 PC 앱, 형아네 `11hllqpn`=yt-ops 열쇠 · `rsgoo1ju`=다른 앱.
- Ruling(형아 11/08 14:10): **결제 연결은 안 한다.** Monitoring 은 결제 없는 프로젝트의 서비스 계정 호출을 거절(403 "requires billing")하므로 WIF·서비스 계정은 지우고, Mac 의 gcloud 와 같은 **사용자 자격증명**을 쓴다: 읽기 전용 계정 zion.geek.py(두 프로젝트 monitoring.viewer 만)의 gcloud 로그인 파일을 Actions 비밀값 `GCP_MONITOR_ADC` 로. 러너 임시 폴더에 풀고 읽은 뒤 삭제. 새면 `gcloud auth revoke zion.geek.py@gmail.com` 으로 끊고 비밀값 교체.
- 칩은 하나(API 사용량 · 두 프로젝트 두 줄). 새로고침 때 즉시 재조회는 정적 페이지라 불가 — 필요해지면 Cloudflare Worker 로 "지금 새로고침" 버튼(형아 판단 보류).

## 2026-11-08 오후 — 건강 검진(opus) 뒤

- 판정 4/5. 손볼 3곳은 바로 고침(배포 전 테스트 관문 · `_safe_fetch` 가 오류를 삼키던 것 · WIF 문구). 작은 것 넷은 보류: 저장소 전체 "일일 실패" 띠가 채널 하나 때문에 켜짐 · 일회성 cron 매년 반복(17:30 뒤 삭제) · daily/live 70줄 중복 · "정확 구독자" 시간대 오차(추정).
- Ruling: **스키마 자동 적용(daily)은 유지.** 1인 운영에서 손으로 적용하는 쪽이 더 자주 빠뜨림. 대신 테스트가 먼저 돌고, `schema --apply` 안내문을 "push 전 로컬 검토" 로 바꿈. 리뷰어 지적(공개 저장소의 Gmail 계정 이름·프로젝트 번호)은 형아 판단 대기.
- Ruling(형아 11/08 17:20): "같은 호출 15번이면 중단" 제안 → 같은 호출(토큰 포함)은 이미 2번째에서 멈추고, 메서드 이름만 세면 정상 페이징(videos.list 30회)이 오탐. 대신 **상한을 조임**: 채널당 300(정상 ~100) + **프로젝트당 1,000**(`CallMeter`, 같은 프로젝트 채널이 한 run 에서 공유 · 넘으면 뒤 채널은 stage `budget` 으로 건너뜀). 최악의 사고도 하루 한도의 10%. 영상 수가 두 배 되면 상한도 올릴 것(상한에 닿으면 화면 오류 목록에 보임).

## 2026-11-08 저녁 — 지금 새로고침 버튼

- Ruling(형아): 숨비가 원할 때 한 번 새로 읽는 버튼. 범위는 **구독자 · 유효시청 · 라이브 현황 · 수익창출 막대**(= `collect --only channel_daily,subs,live`; Analytics 는 3일 지연이라 시청시간 쪽은 새 날이 풀렸을 때만 바뀜). 중간 서버는 **Vercel 함수**(형아 선택, Cloudflare 아님). 전체 daily 재수집은 안 함(400 단위 · 5분).
- 설계: 페이지 → POST {password} → Vercel `refresh/api/refresh.js`(비밀번호 timingSafeEqual · 틀리면 1.5초 지연 · GitHub 최근 workflow_dispatch 실행 시각으로 10분 쿨다운 · PAT 로 `refresh.yml` dispatch) → 워크플로 ~2분 → 페이지가 30초마다 data.enc 를 다시 받아 generated_at 바뀌면 그 자리에서 교체.
- 실측: GitHub Pages CDN 은 쿼리 문자열을 캐시 키에서 무시(`?r=` 로 못 뚫음)하지만 **배포 완료 시 캐시를 비움**(11/08 11:46 UTC, etag 교체 10초 이내). 그래서 폴링은 평문 URL 로 충분하고 "2~3분" 문구 유지.
- 보안 리뷰 지적(비밀번호 대입 창구): data.enc 가 공개라 오프라인 대입이 이미 가능하므로 새 위험은 아님. 그래도 틀린 답을 1.5초 늦춰 온라인이 더 빠르지 않게 함. 별도 비밀번호는 숨비 부담이라 안 둠.
- 배포 뒤 겪은 것(11/08 밤): ① `!` 로 `vercel env add` 를 치면 입력창이 안 떠서 `pbpaste | tr -d '\n' |` 로 클립보드에서 넣음. ② DASH_PASSWORD 가 한 번, GITHUB_TOKEN 이 한 번 잘못 들어감(복사 시점 클립보드 문제 또는 PAT 저장소 미선택) → 버튼 문구에 서버 오류 키를 붙이고(`(github_unavailable)`) 함수 로그에 상태 한 줄을 남기도록 고침. ③ 401 때 저장된 비밀번호를 지우던 처리는 잘못이라 뺌(페이지 쪽 값은 data.enc 를 푼 값이라 항상 맞음). 끝: 23:55 버튼 → refresh 실행 성공, 오류 0.

## 2026-11-09 새벽 — 구독자 숫자가 3일 늦던 것

- 사실: JustSoombi 가 11/07 957 → 11/09 1,027(Studio). API 는 1,020(세 자리 내림). 상황판은 "정확 구독자"(기준점 957 + Analytics 일별 증감)를 우선했는데 Analytics 가 11/05 까지라 증감 0 → 957 그대로. 형아가 새로고침 뒤 발견.
- Ruling: **둘 중 큰 쪽**을 보여준다(`render._best_subscribers`). 계산값은 지연으로, API 값은 내림으로 둘 다 실제 이하라 큰 쪽이 늘 더 가깝다. API 값이 보일 땐 ≈ 와 툴팁("유튜브가 세 자리까지만 알려 줘요 · 정확한 값은 2~3일 뒤"). 1,000명 막대도 같은 값. Studio 의 정확한 실시간 수를 받는 공식 API 는 없음(긁기는 안 함).
- Ruling(형아 11/09 새벽): **새로고침 = 아침 09:30 전체 수집을 지금 한 번 더**(스키마 적용만 뺌). 이유: 숨비에게 "구독자·라이브만" 은 설명이 어렵고, 예약 영상·영상 목록도 같이 새로 보이는 게 낫다. 대가: 프로젝트당 약 400단위/회 → 함수 쿨다운 10분 → **30분**, 문구 "3~4분". 시청시간은 유튜브가 하루 한 번(2~3일 지연) 내놓는 것이라 어떤 방식으로도 즉시 갱신 불가 — 숨비에게 그렇게 설명한다. 구독자를 2시간마다 자동 수집하는 안은 이 결정으로 대체.

## 2026-11-09 오전 — Reporting API 켬 (V2-a 시작)

- 형아가 두 프로젝트에 YouTube Reporting API 켬. 8채널 모두 `reportTypes.list` 20종 · `channel_reach_basic_a1`(노출수·클릭률) 실존 확인.
- 11:20 KST 채널마다 `channel_reach_basic_a1` job 1개씩 생성(이름 `yt-ops reach <key>`). 보고서는 생성 다음 날부터 쌓임(과거분 백필 여부는 내일 확인). 작업 목록·삭제는 `jobs.list/delete`.
- 다음: 보고서 파일이 보이면 `collect/reach.py` + `yt_reach_daily` 표 + 화면(노출수·CTR) — 확장 규칙대로 수집기 1 · 마이그레이션 1 · render 키 1 · app.js 구역 1.
- 11/09 낮 V2-a 코드 완료(커밋 7 + 리뷰 반영 2, 테스트 347): 표 `yt_reach_daily`(channel_key, day, video_id · impressions · ctr 비율) · `ytops/reporting.py` + `collect/reach.py`(최근 7일 보고서 재읽기 upsert, BOM-safe, 파일 단위 퍼센트 판정, channel_id 불일치 거부) · render `board.reach7`(7일 합계·채널 CTR, 직전 4주 달력일 평균 대비, 5일 이상 멈추면 stale) · `detail.reach`(이번 주 올린 영상 / 28일 전체 표, 한마디 fix·push·ok, 쇼츠 vs 롱폼 CTR) · 페이지. 한마디 규칙: 28일 채널 CTR c · 노출 중앙값 m, 노출 500 미만·올린 지 7일 미만·c≤0 은 판정 안 함, fix = ctr ≤ 0.67c 且 노출 ≥ m, push = ctr ≥ 1.5c 且 노출 ≤ 0.5m. 색은 한국식(빨강=오름). 스키마는 Mac 에서 미리 적용. **11/10 첫 파일 확인 목록**: 헤더·날짜 형식·ctr 단위, Content-Type/BOM, 한 파일 내 중복 (date,video_id), 노출 0 행 유무, 과거분 백필 수, 쇼츠 노출 포함 여부(쇼츠 vs 롱폼 패널 유지 여부).
- 리뷰에서 보류: reach 오류가 daily 를 빨간불로 만드는 것(정책, 유지) · 다운로드 하나 실패 시 그 채널 그 회차 전부 버림(다음 날 자동 회복, M).

## 2026-11-15 — reach 수집 429

- 사실: 11/10 부터 daily 6일 중 5일, 새로고침 8번 연속이 reach 단계 429(가끔 500)로 빨간불. 구독자 · 시청시간 · 예약 · 라이브는 매번 정상 수집 · 배포됐고, 노출 자료도 다른 실행이 메워 빈 날은 없었음.
- 원인(Monitoring 실측): Reporting API 한도는 프로젝트당 **분당 60건**(하루 20,000). 파일 다운로드 한 번이 요청 2건(302 + 200)으로 찍힘. 수집기가 "최근 7일에 생긴 보고서"를 매번 다시 받았는데, 11/10 에 유튜브가 과거 30일치를 한꺼번에 만들어 채널당 33~34개 → 채널당 약 70건, 프로젝트당 4채널이 1~2분에 몰려 분당 100~117건.
- 형아 제안 "수집 전용 앱을 하나 더 만들자" → 안 함. 새 프로젝트도 분당 60건이고(총량이 아니라 속도 한도), 8채널을 한 앱에 모으면 통이 둘에서 하나로 줄어 더 걸림. 8채널 재인증 비용도 큼.
- Ruling: ① 채널의 `yt_reach_daily.collected_at` 최댓값(= 마지막 성공 시각, 채널 수집은 전부 아니면 전무)의 **하루 전 이후에 생긴 보고서만** 읽는다. 다시 만들어진 보고서는 createTime 이 새로 찍혀 잡힘. 저장된 행이 없을 때만 7일. ② Reporting 호출 · 다운로드의 429 는 20 · 40초(합 1분), 5xx 는 1 · 2초 기다려 최대 3번(`reporting._wait_for`). 공용 `_retry.py` 는 그대로. — 틀리면: 보고서가 목록에 하루 넘게 늦게 나타나면 그 파일을 놓침(다음에 다시 만들어지면 회복).
- 실측(Mac, 11/15 17:30 `collect --all --only reach`): 8채널 오류 0 · 34초 · 985행(고치기 전 8,459행).
- 독립 리뷰(opus, 11/15 저녁) → 그대로 둬도 되나 세 곳 보강(형아 "전부 진행"):
  - Ruling: 책갈피를 `yt_reach_daily.collected_at` 최댓값에서 **`yt_run_log` 의 "그 채널을 다뤘고 reach 를 돌렸고 그 채널에 `client` · `budget` · `reach` · `store:yt_reach_daily` 오류가 없는 마지막 실행의 `started_at`"** 으로 바꿈(`runner.reach_since`). 이유: 행이 0개인 성공 실행이 책갈피를 못 움직여 창이 매일 넓어지고(한 달 뒤 같은 429), 저장이 일부만 되면 책갈피가 앞서 나감. 화면의 오류 판정과 같은 표 · 같은 기준. — 틀리면: run_log 최근 200건(reach 실행) 안에 깨끗한 실행이 없으면 첫 수집처럼 7일 창.
  - Ruling: `collect --reach-reread-days N` — 책갈피를 무시하고 최근 N일에 생긴 보고서를 다시 읽음(파서 수정 · 표 복구 뒤). 예전 7일 재읽기가 주던 "저절로 낫는 창"이 하루로 줄어든 것의 보완. 런북 ④.
  - Ruling: `downloadUrl` 없는 보고서는 건너뛰지 않고 오류(ValueError) — 조용히 지나가면 책갈피가 그 보고서를 넘어감.
  - 보류: 다운로드 사이를 ~2초 벌려 429 를 아예 안 맞는 방식(평소 채널당 1~2개 파일이라 불필요, 따라잡기 때만 의미) · 보고서 id 표(이 규모엔 과함) · requests 네트워크 예외 재시도 · dry-run 이 책갈피 없이 7일치를 받는 것.
  - 실측(Mac, 17:48 KST): 책갈피가 실제 DB 에서 읽힘(8채널 모두 17:30 실행) → reach 만 실행 오류 0 · 24초 · 543행, 실행 뒤 책갈피 17:47 로 이동.
- 따로 발견: push 때 도는 test 워크플로가 11/09 `c11d273`(카드 간략형)부터 빨간불 — `tests/test_site_reach.mjs` 18개 중 7개 실패(카드 모양을 바꾸고 화면 테스트를 안 맞춤). daily · live 관문은 pytest 뿐이라 배포는 안 막힘. → 11/15 저녁 정리(형아 지시): 옛 카드를 기대하던 7개 중 5개는 간략형 카드에 맞게 고치고, 카드에서 없어진 표시(기준일 라벨 · 짧은 창 일수)를 보던 2개는 지움. 남은 것: `site/app.js` 의 `reachStats` 는 이제 아무도 안 부르는 죽은 코드.

## 2026-11-15 저녁 — 시청시간 기준 표기 · 늦는 이유 말풍선 (형아 지시)

- 사실(run_log 57건): 유튜브는 하루 한 번, 한국 시간 02:28~09:44 사이에 새 날짜 하루치를 푼다. 09:30 daily 가 그 직후라 바로 받고, 그 뒤 새로고침은 다음 날 아침까지 같은 날짜. Analytics 의 하루는 미국 태평양 시간이라 「11/12」 자료는 한국 시간 11/13 17시(서머타임엔 16시)까지 — 실제 공백은 3일이 아니라 41~65시간.
- Ruling: 숫자는 그대로, **표기만** 한국 시간 끝 시각으로(「11/13 17시까지」). 카드 「시간」 · 「48시간」 과 머리줄 「분석 확정」. render 가 `board.as_of.until` · `latest_until`(UTC) 을 내보냄. 빠진 이틀을 추정해 메우는 것은 안 함(수익창출 4,000시간 기준과 맞물린 칸이라 큰 숫자가 추정이면 안 됨) — 형아 확인.
- Ruling: 두 칸에 3초 머물면 말풍선(왜 오늘 숫자가 아닌지 4줄). 칸을 떠나면 사라지고 × 로 닫으면 새로고침 전까지 어느 칸에서도 안 나옴(모듈 변수, 저장 안 함). 3판 spec 의 "화면에 설명 문장을 두지 않는다" 는 늘 보이는 글에 대한 것이고, 이건 머물러야 나오는 글이라 형아 지시로 둠.
- 미리보기 확인(Playwright): 3초 뒤 나타남 · × 뒤 다른 칸에서도 안 나옴 · 새로 열면 다시 나옴 · 1,246px(칸 125px)에선 기준 표기가 라벨 아래 줄로, 1,760px 에선 한 줄. 미리보기 브라우저 창 위에 실제 마우스가 있으면 타이머가 끊겨 확인이 흔들린다(코드 문제 아님).
- (같은 날, 형아 지시) 「48시간」 칸은 「시간」 칸과 다른 말풍선: 언제부터 언제까지(「11/11 17시부터 11/13 17시까지」) + 증감률이 있으면 비교한 앞 이틀의 기간. render `h48.from` · `until` · `prev_from`. 닫힘은 종류별로 따로(메모리). 알아 둘 것: 「시간」(365일 합계)은 창 시작을 "오늘 − 365일" 로 잡아 자료 끝이 3일 전일 때 실제로는 363일 치 — 숨비찰나만 해당, 정확도 점검 때 볼 것.

## 2026-11-15 밤 — 예약현황이 Studio 와 다름 (형아 지적)

- 사실: Studio 숨비찰나 예약 롱폼 6편, 현황판 1편. 원인은 유튜브 업로드 재생목록(주인용, 비공개 포함)이 2쪽부터 각 쪽 앞머리 5~12칸에 앞 영상을 되풀이하고 그 자리 영상을 빼고 줌. 쪽 크기를 바꾸면 빠지는 영상이 바뀜. 1쪽은 온전. 가동 첫날 본 "중복" 을 걸러 내기만 해서 누락을 몰랐음(fbf1527). 숨비찰나 540칸 중 486편만 받았고, 숨비카페 예약 롱폼 5편도 빠져 있었음. 공개 전용 종류별 목록(UULF · UUSH · UULV)은 온전했고 우리 롱폼/쇼츠 판정과 한 편도 안 어긋남(숨비찰나 공개 235편).
- 처음에 "자료는 유튜브와 일치" 라고 잘못 보고함 — 같은 경로로 다시 읽어 DB 와 비교한 것뿐이었음.
- Ruling(형아 "정확한 수치가 목표, 최선이면 진행"): 명단은 DB(yt_video)가 갖고, 유튜브 목록은 1쪽만(새 영상은 항상 1쪽), 영상 정보는 ID 로 직접 조회, 1쪽 응답의 totalResults 와 개수를 매번 대조. 모자라면 나머지를 훑고 그래도 모자라면 오류 목록에. 검색(쪽당 100단위)은 자동으로 안 돌리고 `ytops discover` 로 손으로. 버린 안: 매번 검색(비쌈) · 쪽 크기 바꿔 여러 번 훑기(3편 끝내 안 나옴) · 공개 전용 목록(예약 못 봄).
- 실측(Mac): `discover --channel soombi` 7쪽(700단위)으로 4월 비공개 쇼츠 3편 찾음 → `collect --all --only video,video_daily,schedule` 8채널 오류 0(= 모두 totalResults 와 일치). 예약 롱폼/쇼츠: 숨비찰나 6/11 · 숨비카페 5/21 · BACK THEN 7/7 · JustSoombi 3/8 · groove.wav 6/6 · pli.wav 4/9 · MORROW 0/7 · A2P 0/2. 채널당 영상 목록 호출 ~87 → ~13.
- 같이: 예약현황 날짜를 한국 날짜로(UTC 날짜를 잘라 09시 이전 예약이 전날로 보였음).
- 전수 검수(형아 지시, 11/15 밤): 숨비찰나 외 7채널을 내 영상 검색으로 끝까지 훑음(30쪽, 3,000단위). 예약 영상은 7채널 모두 ID 단위로 현황판 DB 와 같음(BACK THEN 7/7 · MORROW 0/7 · A2P 0/1 · JustSoombi 3/8 · 숨비카페 5/21 · groove.wav 6/6 · pli.wav 4/9). DB 에서 지금 존재하는 영상 수 = 유튜브 총 개수(7채널 모두). 검색은 채널당 0~3편을 못 돌려줬음(검색도 완전하지 않음) — 검산용으로만 쓰고 수집 경로로 쓰지 않는 근거. DB 에만 있는 영상 중 3편(BACK THEN 1 · JustSoombi 2)은 유튜브에서 지워진 것.
