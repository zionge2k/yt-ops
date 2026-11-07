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
- [x] Phase 0 (11/07 꼬비 실행: 금고 재백업 · 공개 저장소 `zionge2k/yt-ops` · Secrets 4개 · Pages · 스키마 적용). Reporting API 켜기만 형아 몫으로 남음
- [x] Task 10 통합 검증: 백필 185일 8채널 errors=0 · collect 2회 멱등 · 11/1~2 값 PDF/실측 일치 · Actions 수동 실행 성공 · Pages 비밀번호 열림 확인(11/07 16:26)
- [x] 화면 2판 결정(11/07 저녁): 카드형 · 유동 그리드(최대 4열) · 상태 말 「떨어짐/흔들림/오름」 · 7일 비교는 그 전 4주 평균(커밋 98b035f) · 채널 찾기 줄 제거
- [ ] 화면 2판을 site/ 에 옮겨 push → Actions 수동 실행 → 새 비밀번호로 열림 확인(진행 중)
- [ ] 남은 것: 형아 Reporting API 켜기 → `reportTypes.list` 확인 · `config/channels.toml` 채널별 업로드 계획 숫자 채우기(지금은 전부 '계획 없음') · 숨비 폰으로 열어 보기 · uploads 중복 수정 push

## Resume Point

- 파일: `plan.md`(Task 10 절) · `docs/runbook.md`(형아 Phase 0 체크리스트 ①)
- 단계: **운영 시작됨(2026-11-07).** 매일 KST 09:30 자동 수집 · 화면 https://zionge2k.github.io/yt-ops/ (비밀번호는 Actions Secret `DASH_PASSWORD`, 형아·숨비 공유). 아래 Phase 0 목록은 11/07 에 1 빼고 완료:
  1. GCP 543780518761 에서 YouTube Reporting API 켜기 → 꼬비가 `reportTypes.list` 로 reach 보고서 실존 확인(2차 CTR 범위 확정)
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
