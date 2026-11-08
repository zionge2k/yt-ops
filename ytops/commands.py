"""On-demand drill-down commands (live, shorts, schedule, query, manual, quota)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ytops import quota, registry, reports, store
from ytops.analytics import for_key as analytics_for_key
from ytops.collect import live as live_collector
from ytops.collect import schedule as schedule_collector
from ytops.collect.context import CollectContext
from ytops.data import for_key as data_for_key
from ytops.registry import KEYS, resolve_key

KST = ZoneInfo("Asia/Seoul")
STATE = {"good": "🟢", "ok": "🟡", "bad": "🔴"}


def connect():
    return store.connect()


def today() -> date:
    return datetime.now(KST).date()


def _keys(args) -> list[str]:
    raw = getattr(args, "channels", None) or args.channel
    return list(KEYS) if raw == "all" else [resolve_key(raw)]


def _context(key: str, channels: dict, *, analytics: bool = False, data: bool = False) -> CollectContext:
    # Only the clients a command needs are built; the rest stay None.
    return CollectContext(
        key=key, channel=channels[key],
        analytics=analytics_for_key(key) if analytics else None,
        data=data_for_key(key) if data else None,
        today=today(), collected_at=datetime.now(timezone.utc),
    )


def _short(text: str | None, n: int = 40) -> str | None:
    return text if text is None else text[:n]


def cmd_live(args) -> int:
    channels = registry.load_channels()
    rows: list[dict] = []
    for key in _keys(args):
        try:
            ctx = _context(key, channels, data=True)
            got = live_collector.collect(ctx, ctx.today, ctx.today).get("yt_live_snapshot", [])
            if not got:
                print(f"⚫ {channels[key].display}: 방송 없음")
            rows += got
        except Exception as e:  # one broken channel must not hide the others
            print(f"⚪ {channels[key].display}: {type(e).__name__}")
    shown = [dict(r, channel=channels[r["channel_key"]].display,
                  state=STATE.get(r["health"], "⚪")) for r in rows]
    if shown:
        print(reports.table(shown, ["channel", "state", "life_cycle", "concurrent", "health", "stream_status", "title"]))
    if args.save and rows:
        store.upsert(connect(), "yt_live_snapshot", rows, pk=["channel_key", "taken_at", "broadcast_id"])
        print(f"saved {len(rows)} rows")
    return 0


def cmd_shorts(args) -> int:
    key = resolve_key(args.channel)
    ctx = _context(key, registry.load_channels(), analytics=True, data=True)
    end = ctx.today - timedelta(days=1)
    start = end - timedelta(days=args.days - 1)
    rows = ctx.analytics.query(
        start, end, "video", "views,engagedViews,estimatedMinutesWatched,subscribersGained,subscribersLost",
        filters="creatorContentType==shorts", sort="-views", max_results=args.top, top_n=True)
    titles = {v["id"]: v.get("snippet", {}).get("title") for v in ctx.data.videos([r["video"] for r in rows])}
    for r in rows:
        views = r.get("views")
        r["title"] = _short(titles.get(r["video"]))
        r["engaged_pct"] = round(r["engagedViews"] / views * 100, 1) if views else None
        r["subs_per_1k"] = round(r["subscribersGained"] / views * 1000, 1) if views else None
    print(f"# {registry.load_channels()[key].display} · {start} ~ {end} · shorts top {args.top}")
    print(reports.table(rows, ["video", "title", "views", "engagedViews", "engaged_pct", "subs_per_1k"]))
    return 0


def cmd_schedule(args) -> int:
    channels = registry.load_channels()
    rows: list[dict] = []
    for key in _keys(args):
        try:
            ctx = _context(key, channels, data=True)
            rows += schedule_collector.collect(ctx, ctx.today, ctx.today)["yt_schedule"]
        except Exception as e:
            print(f"⚪ {channels[key].display}: {type(e).__name__}")
    rows.sort(key=lambda r: r["publish_at"])
    shown = [dict(r, channel=channels[r["channel_key"]].display,
                  publish_at=r["publish_at"].astimezone(KST).strftime("%m/%d %H:%M"),
                  title=_short(r["title"])) for r in rows]
    print(reports.table(shown, ["channel", "publish_at", "content_kind", "title"]))
    return 0


def cmd_query(args) -> int:
    keys = _keys(args)
    end = date.fromisoformat(args.end) if args.end else today() - timedelta(days=1)
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=args.days - 1)
    names = "all" if len(keys) == len(KEYS) else ",".join(keys)
    print(f"# {names} · {start} ~ {end} · {args.dims} · {args.filters or '전체'}")
    multi = len(keys) > 1
    out: list[dict] = []
    for key in keys:
        try:
            client = analytics_for_key(key)
            rows = client.query(start, end, args.dims, args.metrics, filters=args.filters,
                                sort=args.sort or "-" + args.metrics.split(",")[0], max_results=args.max, top_n=True)
        except Exception as e:
            print(f"# ⚪ {key}: {type(e).__name__}")
            continue
        out += [dict(r, channel=key) if multi else r for r in rows]
    cols = args.dims.split(",") + args.metrics.split(",")
    print(reports.tsv(out, (["channel"] if multi else []) + cols))
    return 0


def _number(text: str):
    value = float(text)
    return int(value) if value.is_integer() else value


def cmd_manual(args) -> int:
    if args.action == "set":
        row = {"channel_key": resolve_key(args.key), "field": args.field, "value": _number(args.value),
               "as_of": date.fromisoformat(args.as_of), "note": args.note}
        store.upsert(connect(), "yt_manual", [row], pk=["channel_key", "field"])
        print(f"saved {row['channel_key']} {row['field']} = {row['value']} (as of {row['as_of']})")
        return 0
    rows = store.fetch(connect(), "select channel_key, field, value, as_of, note from yt_manual order by channel_key, field")
    print(reports.table(rows, ["channel_key", "field", "value", "as_of", "note"]))
    return 0


def cmd_quota(args) -> int:
    """Today's Data API units per GCP project, read from Cloud Monitoring (needs a gcloud login)."""
    projects = registry.load_projects()
    if args.project:
        projects = [p for p in projects if p.id == args.project]
        if not projects:
            print(f"{args.project} 은 channels.toml 의 [projects] 에 없어요.")
            return 2
    accounts = [args.account] if args.account else None
    mon = quota.Monitoring(lambda pid: quota.token_for(pid, accounts))
    now = datetime.now(timezone.utc)
    infos, texts, read = [], [], 0
    for project in projects:
        try:
            info = quota.collect_project(mon, project, now)
        except Exception as e:  # one unreadable project must not hide the others
            msg = str(e) if isinstance(e, quota.QuotaAccessError) else f"권한 또는 네트워크 문제예요 ({type(e).__name__})"
            texts.append(f"{project.label} ({project.id})\n  읽지 못했어요: {msg}")
            infos.append(quota.failed_info(project, now, msg))
            continue
        read += 1
        infos.append(info)
        texts.append(quota.report_from(info))
    if args.json:
        payload = json.dumps(infos, ensure_ascii=False, indent=1)
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(payload, encoding="utf-8")
        else:
            print(payload)
    else:
        print("\n\n".join(texts))
    return 0 if read else 1
