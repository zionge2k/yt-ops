-- yt-ops 3판 마이그레이션: 열 3개 추가 + 새 표 3개(청중 · 재생목록 · 재생목록 항목). 여러 번 실행해도 같다.
-- 실행은 맏이(꼬비)가: `python -m ytops schema --apply` (db/schema.sql 정본에도 같은 정의가 있다).

alter table yt_channel_daily add column if not exists subs_gained_vod integer;
alter table yt_channel_daily add column if not exists subs_gained_live integer;

alter table yt_live_snapshot add column if not exists views bigint;

create table if not exists yt_audience (
  channel_key text not null,
  as_of date not null,
  segment text not null,   -- subscribed | unsubscribed
  content text not null,   -- vod | live
  dim text not null,       -- age_gender | country | weight
  key text not null,       -- "<age>/<gender>" | country code | content type
  views bigint,
  minutes numeric,
  pct numeric,
  primary key (channel_key, as_of, segment, content, dim, key)
);
alter table yt_audience enable row level security;

create table if not exists yt_playlist (
  channel_key text not null,
  playlist_id text not null,
  title text,
  item_count integer,
  seen_at timestamptz,
  primary key (playlist_id)
);
alter table yt_playlist enable row level security;

create table if not exists yt_playlist_item (
  playlist_id text not null,
  video_id text not null,
  channel_key text not null,
  primary key (playlist_id, video_id)
);
alter table yt_playlist_item enable row level security;
