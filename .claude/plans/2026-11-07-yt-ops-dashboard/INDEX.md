# Plan: yt-ops — 8채널 통합 상황판

Created: 2026-11-07
Status: active

## Progress

- [x] Task 1 뼈대 · 레지스트리 · 인증 경로
- [x] Task 2 Analytics · Data 클라이언트
- [x] Task 3 수집기 ① 채널 일별 · 구독자
- [x] Task 4 수집기 ② 영상 · 예약 · 라이브
- [x] Task 5 스키마 · 저장소 · CLI
- [x] Task 6 렌더러
- [x] Task 7 암호화 · 정적 페이지
- [x] Task 8 워크플로 · 문서
- [x] Task 9 요청 시 CLI
- [x] 최종 전체 리뷰(opus) + 수정 회차 1회 — 101 테스트 통과
- [x] code-review 2회 + 수정 회차 2·3 (유령 예약 · 403 사유 · 라이브 PK · 백필 185 · store 실패 표시 · 60일 자동중단 대비 · 채널별 실패 판정) — 112 테스트
- [x] Phase 0 (11/07 꼬비 실행: 금고 재백업 · 공개 저장소 `zionge2k/yt-ops` · Secrets 4개 · Pages · 스키마 적용). Reporting API 는 11/07 밤 gcloud 로 두 프로젝트에 켬
- [x] Task 10 통합 검증: 백필 185일 8채널 errors=0 · collect 2회 멱등 · 11/1~2 값 PDF/실측 일치 · Actions 수동 실행 성공 · Pages 비밀번호 열림 확인(11/07 16:26)
- [x] 화면 2판 결정(11/07 저녁): 카드형 · 유동 그리드(최대 4열) · 상태 말 「떨어짐/흔들림/오름」 · 7일 비교는 그 전 4주 평균(커밋 98b035f) · 채널 찾기 줄 제거
- [x] 화면 2판을 site/ 에 옮겨 push(b4cb268 · 2df3d1a 글꼴 integrity) → Actions 수동 실행 성공(run 42359702136, 18:27) → 새 비밀번호로 열림 · 저장된 비밀번호 재진입 확인(11/07 저녁). 시안 폴더 `docs/mockups/` 와 실측 캡처는 진짜 숫자가 있어 커밋하지 않음(로컬만)
- [x] Reporting API 켜기(11/07 밤, shorts-factory=bono3815 · nowbrd-release=zion.geek.nak 계정으로 gcloud enable) → 8채널 `reportTypes.list` 20종, `channel_reach_basic_a1`(노출수·CTR) 실존. jobs 는 아직 0개(V2-a 에서 jobs.create)
- [x] 3판(PC 꼬비, 11/07 밤) 리뷰·보강(11/08 새벽): 한도 사고 가드 · half_trend · run_log collectors · 라이브 2시간 스냅샷 · 띠 기준 · 트랜잭션 — 24커밋, 테스트 177
- [x] 오류 문구 사람 말로 · ytops quota (11/08)
- [x] API 사용량 게이지 + #api 화면 (11/08)
- [x] 건강 검진(opus, 11/08 오후) 4/5 → 손볼 3곳 반영: 배포 전 pytest 관문(daily·live) + push 마다 test.yml · 렌더 선택 표 읽기 실패를 오류 목록에 표시 · README/주석의 WIF 문구 정정 — 테스트 261
- [x] 11/08 17:00 한도 리셋 뒤 daily 수동 실행 → 8채널 오류 0(숨비네 4채널 복구) · 일회성 cron 줄 삭제 · live 2시간 실행 성공 확인(15:08)
- [x] 호출 상한 조임: 채널 300 · 프로젝트 1,000 (11/08)
- [x] **지금 새로고침 버튼** (11/08 밤 실사용 확인): refresh.yml + Vercel 함수 `yt-ops-refresh`(`refresh/`) + 페이지 버튼. 형아 브라우저에서 눌러 23:55 실행 → 8채널 오류 0. 비밀값은 Vercel 에 GITHUB_TOKEN(PAT · yt-ops Actions 읽기+쓰기) · DASH_PASSWORD. 남은 것: 숨비 폰에서 한 번 눌러 보기.
- [x] API 탭 메서드 → 행위 말("무슨 일에 썼나", 원래 이름은 툴팁) · CLI 같은 말 (11/09 새벽, 형아 지시)
- [x] 새로고침을 전체 수집으로 · 30분 간격 (11/09) · 구독자는 계산값·API 값 중 큰 쪽 (11/09)
- [ ] **V2-a 노출수·CTR**: Reporting API 켬 + 8채널 reach job 생성(11/09 11:20). **코드 완료(11/09)**: `yt_reach_daily` 표 · `ytops/reporting.py` · reach 수집기 · render `reach7`/`reach` · 카드 두 줄 + 심화 「썸네일 성적」(커밋 5개, 테스트 가짜만). 첫 보고서 파일 대기(11/10 오후 확인): `python -m ytops schema --apply` 로 표 만든 뒤 `collect --channel soombi --only reach` 한 번 돌려 실제 열 이름 · 값 범위(ratio) 확인. 그때까지 화면은 「보고서 쌓이는 중」.
- [ ] 남은 것: `config/channels.toml` 채널별 업로드 계획 숫자 채우기(지금은 전부 '계획 없음') · 숨비 폰으로 열어 보기 · 채널 전체 상태 규칙 확정 · 아주 작은 기준값의 퍼센트(+70,900% 류) 표시 규칙 · 11/08 09:30 첫 자동 실행 확인

## Resume Point

- 파일: `plan.md`(Task 10 절) · `docs/runbook.md`(형아 Phase 0 체크리스트 ①)
- 단계: **운영 시작됨(2026-11-07).** 매일 KST 09:30 자동 수집 · 화면 https://zionge2k.github.io/yt-ops/ (비밀번호는 Actions Secret `DASH_PASSWORD`, 형아·숨비 공유). 아래 Phase 0 목록은 11/07 에 1 빼고 완료:
  1. ~~Reporting API 켜기~~ 11/07 밤 완료(두 프로젝트). reach 보고서 실존 확인됨 → V2-a 는 jobs.create 부터
  2. `~/kkobi/yt-channels-vault/scripts/backup.sh` 재실행(analytics.json 포함) + push
  3. GitHub 공개 저장소 `zionge2k/yt-ops` 생성 · Secrets 4개 · Pages Source=Actions → `git remote add origin … && git push -u origin main`
  4. `.env` 에 `SUPABASE_DB_URL` 넣고 `python -m ytops schema --apply` 승인
- 그 다음(Task 10, 꼬비): `backfill --days 180 --all` → `collect --all` 2회 멱등 → `render` 대조(11/03 PDF 값) → Actions dispatch(backfill_days=180) → Pages 확인 → 숨비 폰 확인 → INDEX 완료 처리.
- 규칙 기록: `rulings.md`(실행 중 내린 판단 전부). 보류한 minor 도 거기.

## Files

- `plan.md` — 작업 단위 계획
- `rulings.md` — SDD 레저에서 옮긴 판단·보류 목록
- `/Users/zion/.claude/plans/resilient-shimmying-lark.md` — 승인된 설계
- `docs/runbook.md` · `ai-learnings.md`
