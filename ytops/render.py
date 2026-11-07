"""Render DB rows into the data.json structure the dashboard page reads."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from ytops import periods, store

fetch = store.fetch  # single injectable DB read; tests monkeypatch it

KST = ZoneInfo("Asia/Seoul")
PERIODS = (7, 28, 90)
TRUST = {
    "subscribers": "live", "views": "lagged", "watch_hours": "lagged", "subs_net": "lagged",
    "shorts": "computed", "hours_approx": "approx", "live_snapshot": "live",
}


def _json_default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(f"not serializable: {type(o).__name__}")


def _num(v):
    return float(v) if isinstance(v, Decimal) else v


def _sum(values):
    """Sum of the non-None values; None when there is none."""
    got = [_num(v) for v in values if v is not None]
    return sum(got) if got else None


def _kst_date(dt: datetime) -> date:
    return dt.astimezone(KST).date()


def period_summary(rows, win, prev_win, extract, up, down) -> dict:
    """rows: one channel's daily rows; extract(row) -> number or None."""
    if win is None:
        return {"cur": None, "prev": None, "pct": None, "status": "grey", "spark": []}
    by_day = {r["day"]: r for r in rows}

    def values(w):
        days = (w[1] - w[0]).days + 1
        return [extract(by_day[d]) if d in by_day else None
                for d in (w[0] + timedelta(days=i) for i in range(days))]

    spark = [_num(v) for v in values(win)]
    cur, prev_total = _sum(spark), _sum(values(prev_win))
    # prev_win may be longer than win (4-week baseline): scale it to the window length
    scale = len(spark) / ((prev_win[1] - prev_win[0]).days + 1)
    prev = None if prev_total is None else round(prev_total * scale, 1)
    pct = periods.pct_change(cur, prev)
    return {"cur": cur, "prev": prev, "pct": pct, "status": periods.status_of(pct, up, down), "spark": spark}


def _hours(r):
    mins = [r.get("min_live"), r.get("min_vod")]
    return None if all(m is None for m in mins) else sum(_num(m) for m in mins if m is not None) / 60


def _subs_net(r):
    if r.get("subs_gained") is None and r.get("subs_lost") is None:
        return None
    return (r.get("subs_gained") or 0) - (r.get("subs_lost") or 0)


def _round(v, n):
    return None if v is None else round(v, n)


def shortage(plan_long_per_week: int, plan_shorts_per_day: int, scheduled: list[dict],
             today: date, days: int = 3) -> dict:
    window_days = {today + timedelta(days=i) for i in range(days)}
    have = {"long": 0, "short": 0}
    for s in scheduled:
        if s.get("publish_at") and _kst_date(s["publish_at"]) in window_days and s["content_kind"] in have:
            have[s["content_kind"]] += 1

    def one(need, got):
        status = "none" if need == 0 else ("ok" if got >= need else "short")
        return {"need": need, "have": got, "status": status}

    return {
        "long": one(math.ceil(plan_long_per_week * days / 7), have["long"]),
        "shorts": one(plan_shorts_per_day * days, have["short"]),
    }


def _schedule(ch, rows, today: date, days: int) -> dict:
    # `today` is a KST calendar date; "future" means publish_at on/after it
    future = sorted((r for r in rows if r["publish_at"] and _kst_date(r["publish_at"]) >= today),
                    key=lambda r: r["publish_at"])
    longs = [r for r in future if r["content_kind"] == "long"]
    shorts = [r for r in future if r["content_kind"] == "short"]
    next7 = []
    for i in range(7):
        d = today + timedelta(days=i)
        day_rows = [r for r in future if _kst_date(r["publish_at"]) == d]
        next7.append({"date": d, "long": sum(r["content_kind"] == "long" for r in day_rows),
                      "shorts": sum(r["content_kind"] == "short" for r in day_rows)})
    return {
        "long": len(longs), "shorts": len(shorts),
        "next_long": longs[0]["publish_at"] if longs else None,
        "next_shorts": shorts[0]["publish_at"] if shorts else None,
        "next7": next7,
        "shortage": shortage(ch.plan_long_per_week, ch.plan_shorts_per_day, future, today, days),
    }


def _latest_per_channel(rows, order_key):
    out = {}
    for r in rows:
        k = r["channel_key"]
        if k not in out or r[order_key] > out[k][order_key]:
            out[k] = r
    return out


def _cap(v):
    return min(v, 100.0)


def _no_compare(m: dict) -> None:
    """Drop the comparison of a period summary (the current window still shows)."""
    m["prev"], m["pct"], m["status"] = None, None, "grey"


def _current_schedule(rows):
    """Rows from each channel's latest collection only (yt_schedule is upsert-only)."""
    last: dict[str, object] = {}
    for r in rows:
        k, seen = r["channel_key"], r.get("seen_at")
        if seen is not None and (last.get(k) is None or seen > last[k]):
            last[k] = seen
    return [r for r in rows if r.get("seen_at") == last.get(r["channel_key"])]


FAILED_STAGES = ("client", "channel_daily")


def _failed(stage) -> bool:
    """Collection or DB-write failures make a channel's numbers untrustworthy."""
    stage = stage or ""
    return stage in FAILED_STAGES or stage.startswith("store:")


def _channel_errors(runs, key) -> list[dict]:
    """Errors of the most recent run that covered this channel (runs: newest first).

    A run without a `channels` value (older rows) is treated as covering every channel.
    """
    for r in runs:
        covered = r.get("channels")
        if covered is None or key in covered:
            return [{**e, "run_started_at": r.get("started_at")}
                    for e in (r.get("errors") or []) if e.get("channel") == key]
    return []


def build(conn, *, today: date, config) -> dict:
    channels, th = config["channels"], config["thresholds"]
    up, down = th["up_pct"], th["down_pct"]
    daily = fetch(conn, "select * from yt_channel_daily order by day")
    latest = max((r["day"] for r in daily), default=None)

    by_ch: dict[str, list] = {k: [] for k in channels}
    for r in daily:
        by_ch.setdefault(r["channel_key"], []).append(r)

    # a channel's comparison is meaningless when its history does not reach back to the
    # previous window, or when its collection fell behind the global latest day
    first_day = {k: min((r["day"] for r in rs), default=None) for k, rs in by_ch.items()}
    ch_latest = {k: max((r["day"] for r in rs), default=None) for k, rs in by_ch.items()}

    wins = {p: periods.window(latest, p) if latest else None for p in PERIODS}
    out_periods = {}
    for p, w in wins.items():
        pw = periods.compare_window(w) if w else None
        out_periods[str(p)] = {
            "start": w[0] if w else None, "end": w[1] if w else None,
            "prev_start": pw[0] if pw else None, "prev_end": pw[1] if pw else None,
            "channels": {
                k: {
                    "views": period_summary(by_ch[k], w, pw, lambda r: r["views"], up, down),
                    "subs_net": period_summary(by_ch[k], w, pw, _subs_net, up, down),
                    "watch_hours": period_summary(by_ch[k], w, pw, _hours, up, down),
                }
                for k in channels
            },
        }
        for k, m in out_periods[str(p)]["channels"].items():
            if pw and (first_day[k] is None or first_day[k] > pw[0] or ch_latest[k] < latest):
                for summary in m.values():
                    _no_compare(summary)
            wh = m["watch_hours"]
            wh["cur"], wh["prev"] = _round(wh["cur"], 1), _round(wh["prev"], 1)
            wh["spark"] = [_round(v, 1) for v in wh["spark"]]

    w7 = wins[7]

    def in7(k):
        return [r for r in by_ch[k] if w7 and w7[0] <= r["day"] <= w7[1]]

    subs = _latest_per_channel(fetch(conn, "select * from yt_subs_snapshot"), "taken_on")
    snaps = _latest_per_channel(fetch(conn, "select * from yt_live_snapshot"), "taken_at")
    yearly = _latest_per_channel(fetch(conn, "select * from yt_yearly_minutes"), "as_of")
    manual = {r["channel_key"]: r for r in fetch(conn, "select * from yt_manual")
              if r["field"] == "official_watch_hours_365"}
    sched_rows = _current_schedule(fetch(conn, "select * from yt_schedule"))
    runs = fetch(conn, "select * from yt_run_log order by started_at desc limit 50")
    errors: list[dict] = []

    out_channels, live, schedule, monet, shorts = [], {}, {}, {}, {}
    for k, ch in channels.items():
        s = subs.get(k)
        sub = {"api": s["api_subscribers"], "exact": s["exact_subscribers"]} if s else None
        ch_errors = _channel_errors(runs, k)
        errors += ch_errors
        out_channels.append({"key": k, "display": ch.display, "is_live": ch.is_live,
                             "subscribers": sub, "errors": ch_errors,
                             "collect_failed": any(_failed(e.get("stage")) for e in ch_errors)})
        rows7 = in7(k)
        if ch.is_live:
            sn = snaps.get(k)
            lv, od = _sum(r["min_lol_live"] for r in rows7), _sum(r["min_lol_ondemand"] for r in rows7)
            live[k] = {
                # no rows in the window -> unknown (None), not "no live" (0)
                "days_with_live": sum(1 for r in rows7 if (_num(r["min_lol_live"]) or 0) > 0) if rows7 else None,
                "hours_live": None if lv is None else _round(lv / 60, 1),
                "hours_ondemand": None if od is None else _round(od / 60, 1),
                "last_snapshot": None if sn is None else {
                    "taken_at": sn["taken_at"], "life_cycle": sn["life_cycle"], "concurrent": sn["concurrent"],
                    "health": sn["health"], "stream_status": sn["stream_status"], "title": sn["title"]},
            }
        schedule[k] = _schedule(ch, [r for r in sched_rows if r["channel_key"] == k], today,
                                th["shortage_days"])
        subs_n = (sub["exact"] if sub and sub["exact"] is not None else sub["api"] if sub else None)
        y = yearly.get(k)
        hours = _round(_hours(y) if y else None, 1)
        man = manual.get(k)
        monet[k] = {
            "subs_exact": subs_n,
            "subs_pct": None if subs_n is None else _cap(round(subs_n / 1000 * 100, 1)),
            "hours_approx": hours,
            "hours_pct": None if hours is None else _cap(round(hours / 4000 * 100, 1)),
            "official": None if man is None or man["value"] is None
            else {"value": _num(man["value"]), "as_of": man["as_of"]},
        }
        v = _sum(r["views_shorts"] for r in rows7)
        e = _sum(r["engaged_views_shorts"] for r in rows7)
        g = _sum(r["subs_gained_shorts"] for r in rows7)
        shorts[k] = {
            "views": v,
            "engaged_ratio": round(e / v, 3) if v and e is not None else None,
            "subs_per_1k": round(g / v * 1000, 1) if v and g is not None else None,
        }

    return {
        "generated_at": datetime.now(timezone.utc),
        "latest_day": latest,
        "lag_days": (today - latest).days if latest else None,
        "trust": dict(TRUST),
        "channels": out_channels,
        "periods": out_periods,
        "live": live,
        "schedule": schedule,
        "monetization": monet,
        "shorts": shorts,
        "errors": errors,
    }
