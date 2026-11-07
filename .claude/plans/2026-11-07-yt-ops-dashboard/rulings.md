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
