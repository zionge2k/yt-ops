-- yt-ops 스키마 정본. 여러 번 실행해도 같다(create ... if not exists). 열은 ytops/collect/* 가 내는 행과 같다.

create table if not exists yt_channel_daily (
  channel_key text not null,
  day date not null,
  views bigint,
  min_shorts numeric,
  min_live numeric,
  min_vod numeric,
  min_unspec numeric,
  min_lol_live numeric,
  min_lol_ondemand numeric,
  subs_gained integer,
  subs_lost integer,
  views_shorts bigint,
  engaged_views_shorts bigint,
  subs_gained_shorts integer,
  collected_at timestamptz,
  primary key (channel_key, day)
);
alter table yt_channel_daily enable row level security;

create table if not exists yt_yearly_minutes (
  channel_key text not null,
  as_of date not null,
  min_live numeric,
  min_vod numeric,
  min_shorts numeric,
  start_day date,
  end_day date,
  primary key (channel_key, as_of)
);
alter table yt_yearly_minutes enable row level security;

create table if not exists yt_subs_snapshot (
  channel_key text not null,
  taken_on date not null,
  api_subscribers bigint,
  exact_subscribers bigint,
  monetized boolean,
  primary key (channel_key, taken_on)
);
alter table yt_subs_snapshot enable row level security;

create table if not exists yt_video (
  video_id text not null,
  channel_key text not null,
  title text,
  published_at timestamptz,
  publish_at timestamptz,
  privacy text,
  duration_s integer,
  content_kind text,
  thumbnail_url text,
  last_seen_at timestamptz,
  first_seen_at timestamptz,
  primary key (video_id)
);
alter table yt_video enable row level security;

create table if not exists yt_video_daily (
  video_id text not null,
  channel_key text not null,
  day date not null,
  views bigint,
  engaged_views bigint,
  minutes numeric,
  avd_s numeric,
  avp numeric,
  subs_gained integer,
  subs_lost integer,
  primary key (video_id, day)
);
alter table yt_video_daily enable row level security;

create table if not exists yt_schedule (
  channel_key text not null,
  video_id text not null,
  title text,
  publish_at timestamptz,
  content_kind text,
  seen_at timestamptz,
  primary key (channel_key, video_id)
);
alter table yt_schedule enable row level security;

create table if not exists yt_live_snapshot (
  channel_key text not null,
  taken_at timestamptz not null,
  broadcast_id text,
  life_cycle text,
  concurrent integer,
  health text,
  stream_status text,
  actual_start timestamptz,
  title text,
  primary key (channel_key, taken_at)
);
alter table yt_live_snapshot enable row level security;

create table if not exists yt_manual (
  channel_key text not null,
  field text not null,
  value numeric,
  as_of date,
  note text,
  primary key (channel_key, field)
);
alter table yt_manual enable row level security;

create table if not exists yt_run_log (
  run_id text not null,
  started_at timestamptz,
  finished_at timestamptz,
  ok boolean,
  latest_day date,
  errors jsonb,
  counts jsonb,
  primary key (run_id)
);
alter table yt_run_log enable row level security;
