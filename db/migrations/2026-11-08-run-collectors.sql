-- yt_run_log 에 이 run 이 돌린 수집기 이름 목록을 남긴다 (live 전용 run 이 daily 실패를 가리지 않게)
alter table yt_run_log add column if not exists collectors jsonb;
