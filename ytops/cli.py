"""ytops command line: argument wiring only; on-demand commands live in ytops.commands."""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ytops import commands, crypt, registry, render, runner, store
from ytops.registry import KEYS, resolve_key

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
TABLES = (
    "yt_channel_daily", "yt_yearly_minutes", "yt_subs_snapshot", "yt_video",
    "yt_video_daily", "yt_schedule", "yt_live_snapshot", "yt_manual", "yt_run_log",
    "yt_audience", "yt_playlist", "yt_playlist_item",
)


def _targets(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--channel", help="channel key or alias (e.g. chalna)")
    g.add_argument("--all", action="store_true", help="all 8 channels")


def _keys(args) -> list[str]:
    return list(KEYS) if args.all else [resolve_key(args.channel)]


def _only_names(raw: str) -> list[str]:
    """argparse type for --only: an empty list must not silently mean "run everything"."""
    names = [n.strip() for n in raw.split(",") if n.strip()]
    if not names:
        raise argparse.ArgumentTypeError("--only needs at least one collector name")
    return names


def _only(args) -> list[str] | None:
    return getattr(args, "only", None)


def _collect(args, *, days: int, video_days: int) -> int:
    conn = None if args.dry_run else store.connect()
    res = runner.run_collect(_keys(args), days=days, video_days=video_days, dry_run=args.dry_run, conn=conn,
                             only=_only(args))
    print(f"run {res.run_id} latest_day={res.latest_day} errors={len(res.errors)} counts={res.counts}")
    for e in res.errors:
        print(f"  ERROR {e['channel']} {e['stage']}: {e['error']}: {e['message']}")
    return 1 if res.errors else 0


def _status() -> int:
    conn = store.connect()
    for table in TABLES:
        n = store.fetch(conn, f"select count(*) as n from {table}")[0]["n"]
        print(f"{table}: {n}")
    last = store.fetch(conn, "select * from yt_run_log order by started_at desc limit 1")
    print("last run:", last[0] if last else "none")
    return 0


def _render(args) -> int:
    today = date.fromisoformat(args.today) if args.today else datetime.now(ZoneInfo("Asia/Seoul")).date()
    config = {"channels": registry.load_channels(), "thresholds": registry.load_thresholds()}
    data = render.build(store.connect(), today=today, config=config)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, default=render._json_default)
    print(f"wrote {out} latest_day={data['latest_day']} lag_days={data['lag_days']}")
    return 0


def _encrypt(args) -> int:
    password = os.environ.get("DASH_PASSWORD")
    if not password:
        print("DASH_PASSWORD 환경변수가 없어요. 비밀번호는 환경변수로만 받아요.")
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(crypt.encrypt(Path(args.inp).read_bytes(), password))
    print(f"wrote {out}")
    return 0


def _schema(args) -> int:
    if not args.apply:
        print(f"{SCHEMA_PATH} (use --apply to run it)")
        return 0
    print(f"스키마 적용: {SCHEMA_PATH} — 여러 번 실행해도 같다. 형아 승인 뒤에만 실행할 것.")
    store.apply_schema(store.connect(), SCHEMA_PATH)
    print("적용 완료")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ytops")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    _targets(c)
    c.add_argument("--days", type=int, default=10)
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--only", type=_only_names, help="comma-separated collector names (e.g. live)")
    b = sub.add_parser("backfill")
    _targets(b)
    b.add_argument("--days", type=int, default=185,
                   help="channel daily/subs/live/schedule window (default 185: analytics lags ~3 days, so the 90-day "
                        "comparison needs a full previous window; 365 for the subscriber chart — channel daily is "
                        "collected in 180-day slices); per-video daily stays 28")
    b.add_argument("--dry-run", action="store_true")
    b.add_argument("--only", type=_only_names, help="comma-separated collector names")
    sub.add_parser("status")
    r = sub.add_parser("render")
    r.add_argument("--out", required=True)
    r.add_argument("--today", help="YYYY-MM-DD (default: today in Asia/Seoul)")
    e = sub.add_parser("encrypt")
    e.add_argument("inp", metavar="IN")
    e.add_argument("out", metavar="OUT")
    s = sub.add_parser("schema")
    s.add_argument("--apply", action="store_true")
    lv = sub.add_parser("live")
    lv.add_argument("--channel", required=True)
    lv.add_argument("--save", action="store_true")
    sh = sub.add_parser("shorts")
    sh.add_argument("--channel", required=True)
    sh.add_argument("--days", type=int, default=28)
    sh.add_argument("--top", type=int, default=20)
    sc = sub.add_parser("schedule")
    sc.add_argument("--channel", required=True)
    q = sub.add_parser("query")
    qg = q.add_mutually_exclusive_group(required=True)
    qg.add_argument("--channel")
    qg.add_argument("--channels", help="'all' for every channel")
    q.add_argument("--dims", default="country")
    q.add_argument("--metrics", default="views,estimatedMinutesWatched,averageViewDuration")
    q.add_argument("--filters")
    q.add_argument("--sort", help="default: descending by the first metric")
    q.add_argument("--days", type=int, default=28)
    q.add_argument("--start")
    q.add_argument("--end")
    q.add_argument("--max", type=int, default=25)
    m = sub.add_parser("manual")
    ms = m.add_subparsers(dest="action", required=True)
    mset = ms.add_parser("set")
    mset.add_argument("key")
    mset.add_argument("field")
    mset.add_argument("value")
    mset.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    mset.add_argument("--note")
    ms.add_parser("list")
    args = parser.parse_args(argv)
    if args.cmd == "collect":
        return _collect(args, days=args.days, video_days=args.days)
    if args.cmd == "backfill":
        return _collect(args, days=args.days, video_days=28)
    if args.cmd == "status":
        return _status()
    if args.cmd == "render":
        return _render(args)
    handler = {"live": commands.cmd_live, "shorts": commands.cmd_shorts, "schedule": commands.cmd_schedule,
               "query": commands.cmd_query, "manual": commands.cmd_manual}.get(args.cmd)
    if handler:
        return handler(args)
    if args.cmd == "encrypt":
        return _encrypt(args)
    return _schema(args)
