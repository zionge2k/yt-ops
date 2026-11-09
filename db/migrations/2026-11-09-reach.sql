-- yt-ops V2-a 마이그레이션: 썸네일 노출수 · 클릭률(YouTube Reporting API channel_reach_basic_a1) 일별 표. 여러 번 실행해도 같다.
-- 실행: `python -m ytops schema --apply` (db/schema.sql 정본에도 같은 정의가 있다).

create table if not exists yt_reach_daily (
  channel_key text not null,
  day date not null,
  video_id text not null,
  impressions bigint,
  ctr numeric,            -- ratio 0..1 (thumbnail clicks / impressions)
  collected_at timestamptz,
  primary key (channel_key, day, video_id)
);
alter table yt_reach_daily enable row level security;
