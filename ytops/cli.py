"""ytops command line: collect / backfill / status / schema."""
from __future__ import annotations

import argparse
from pathlib import Path

from ytops import runner, store
from ytops.registry import KEYS, resolve_key

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
TABLES = (
    "yt_channel_daily", "yt_yearly_minutes", "yt_subs_snapshot", "yt_video",
    "yt_video_daily", "yt_schedule", "yt_live_snapshot", "yt_manual", "yt_run_log",
)


def _targets(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--channel", help="channel key or alias (e.g. chalna)")
    g.add_argument("--all", action="store_true", help="all 8 channels")


def _keys(args) -> list[str]:
    return list(KEYS) if args.all else [resolve_key(args.channel)]


def _collect(args, *, days: int, video_days: int) -> int:
    conn = None if args.dry_run else store.connect()
    res = runner.run_collect(_keys(args), days=days, video_days=video_days, dry_run=args.dry_run, conn=conn)
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
    b = sub.add_parser("backfill")
    _targets(b)
    b.add_argument("--days", type=int, default=90)
    b.add_argument("--dry-run", action="store_true")
    sub.add_parser("status")
    s = sub.add_parser("schema")
    s.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "collect":
        return _collect(args, days=args.days, video_days=args.days)
    if args.cmd == "backfill":
        return _collect(args, days=args.days, video_days=28)
    if args.cmd == "status":
        return _status()
    return _schema(args)
