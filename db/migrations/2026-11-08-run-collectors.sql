-- yt_run_log 에 이 run 이 돌린 수집기 이름 목록을 남긴다 (live 전용 run 이 daily 실패를 가리지 않게)
alter table yt_run_log add column if not exists collectors jsonb;
-- 이전 코드(collectors 열을 모르던 live 전용 run)가 남긴 행을 live 전용으로 표시한다. 여러 번 실행해도 같다.
update yt_run_log set collectors = '["live"]'::jsonb
where collectors is null
  and started_at >= '2026-11-07T13:00:00Z'
  and (counts - 'yt_live_snapshot') = '{}'::jsonb
  and not exists (
    select 1 from jsonb_array_elements(coalesce(errors, '[]'::jsonb)) e
    where e->>'stage' not in ('live', 'client'));
