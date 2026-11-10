"""Render DB rows into the data.json (v3) structure the dashboard page reads."""
from __future__ import annotations

import re
import sys
import statistics
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from ytops import periods, store
from ytops.errors import KST, human_error

fetch = store.fetch  # single injectable DB read; tests monkeypatch it

# Fixed channel order on every screen (also exported as data.json "order").
ORDER = ("soombi", "backthen", "urachacha", "a2p", "justsoombi", "soombicafe", "groovewav", "pliwav")
SUBS_WINDOWS = (365, 7)
WATCH_WINDOWS = (365, 28, 7)
RECENT_DAYS = 28  # top videos / genres / subscription sources
SUBS_GOAL, HOURS_GOAL = 1000, 4000
SEGMENTS = {"subscribed": "subscribers", "unsubscribed": "viewers"}
PEAK_FIELDS = {"subscribers": "peak_hours", "viewers": "peak_hours_viewers"}
TOP_N, GENRE_N, COUNTRY_N = 3, 5, 5
# Thumbnail reach (yt_reach_daily). The 28-day detail window is judged against the 28 days before it,
# and the reach feed can trail the channel feed, hence a week of slack on the read.
REACH_WINDOW_DAYS, REACH_BOARD_DAYS = 28, 7
REACH_FETCH_DAYS = 2 * REACH_WINDOW_DAYS + 7
REACH_BASELINE_MIN_DAYS = 7  # fewer days of data in the comparison stretch is not a baseline
REACH_TOP_N = 12
# Verdict on a video (channel 28-day ctr c, median impressions m of its videos): a video is judged only once
# it has had a week and 100 impressions; "fix" = shown a lot, clicked little; "push" = clicked a lot, shown little.
# 500 because the sampling error of a ctr over 100 impressions is about +-2pp, which flips a verdict on one click.
REACH_MIN_AGE_DAYS, REACH_MIN_IMPRESSIONS = 7, 500
# A channel whose newest report day trails the channel feed by more than this is shown as "stopped", not as current.
REACH_STALE_DAYS = 5
REACH_FIX_CTR_RATIO = 0.67
REACH_PUSH_CTR_RATIO, REACH_PUSH_IMPRESSIONS_RATIO = 1.5, 0.5


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


def _round(v, n):
    return None if v is None else round(v, n)


def _hours(r):
    """Effective watch hours of a daily/yearly row: live + on-demand minutes, shorts excluded."""
    mins = [r.get("min_live"), r.get("min_vod")]
    return None if all(m is None for m in mins) else sum(_num(m) for m in mins if m is not None) / 60


def _subs_net(r):
    if r.get("subs_gained") is None and r.get("subs_lost") is None:
        return None
    return (r.get("subs_gained") or 0) - (r.get("subs_lost") or 0)


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _latest_per_channel(rows, order_key):
    out = {}
    for r in rows:
        k = r["channel_key"]
        if k not in out or r[order_key] > out[k][order_key]:
            out[k] = r
    return out


def _safe_fetch(conn, sql, params=(), *, problems: list[dict] | None = None):
    """Read an optional table; on failure return no rows but record the problem so the page shows it."""
    try:
        return fetch(conn, sql, params)
    except Exception as e:  # noqa: BLE001 — render must not stop on one unreadable table
        m = re.search(r"\bfrom\s+(\S+)", sql, re.I)
        table = m.group(1) if m else None
        msg = str(e)[:200]
        print(f"[render] {table}: {type(e).__name__}: {msg}", file=sys.stderr)
        if problems is not None:
            problems.append({"channel": None, "stage": "render", "error": type(e).__name__,
                             "message": msg, "table": table})
        return []


# Only stages feeding the card's own numbers fail the channel; errors of side tables
# (playlists, audience, live snapshot) stay in the error list.
FAILED_STAGES = ("client", "budget", "channel_daily", "subs", "store:yt_channel_daily", "store:yt_subs_snapshot")


def _failed(stage) -> bool:
    """Collection or DB-write failures of the card's core numbers make them untrustworthy."""
    return (stage or "") in FAILED_STAGES


# Which collector owns a failure stage: only a run that ran it can say the stage recovered.
# A stage is a collector name, `store:<table>` (the collector writing that table) or `client`
# (any run builds the clients).
TABLE_OWNERS = {
    "yt_playlist": "playlists", "yt_playlist_item": "playlists", "yt_audience": "audience",
    "yt_video": "video", "yt_video_daily": "video_daily", "yt_schedule": "schedule",
    "yt_live_snapshot": "live", "yt_channel_daily": "channel_daily", "yt_yearly_minutes": "channel_daily",
    "yt_subs_snapshot": "subs", "yt_reach_daily": "reach",
}


def _stage_owner(stage) -> str | None:
    """Collector that owns a failure stage; None when any run can speak for it."""
    stage = stage or ""
    if stage.startswith("store:"):
        return TABLE_OWNERS.get(stage[len("store:"):])
    return None if stage == "client" else stage


def _covers(run, key) -> bool:
    """A run without a `channels` value (older rows) is treated as covering every channel."""
    covered = run.get("channels")
    return covered is None or key in covered


def _ran_any(run, owners) -> bool:
    """A run without a `collectors` value (older rows) is treated as having run every collector."""
    ran = run.get("collectors")
    return ran is None or any(o in ran for o in owners)


def _channel_errors(runs, key) -> list[dict]:
    """Errors shown for one channel (runs: newest first).

    Each failure stage is read from the newest covering run that ran the collector owning that
    stage, so a later live-only run cannot clear a daily failure (nor a daily run a live one).
    """
    covering = [r for r in runs if _covers(r, key)]
    stages = {e.get("stage") for r in covering for e in (r.get("errors") or []) if e.get("channel") == key}
    picked: list[tuple[int, int, dict]] = []
    for stage in stages:
        owner = _stage_owner(stage)
        for i, r in enumerate(covering):
            if owner is None or _ran_any(r, (owner,)):
                picked += [(i, j, {**e, "run_started_at": r.get("started_at")})
                           for j, e in enumerate(r.get("errors") or [])
                           if e.get("channel") == key and e.get("stage") == stage]
                break
    return [e for _, _, e in sorted(picked, key=lambda t: t[:2])]


def _last_daily_ok_at(runs):
    """started_at of the newest run that ran channel_daily without a core failure (runs: newest first).

    Side-collector errors (playlists, audience ...) do not count: the card's numbers were still collected.
    """
    for r in runs:
        if _ran_any(r, ("channel_daily",)) and not any(_failed(e.get("stage")) for e in (r.get("errors") or [])):
            return r.get("started_at")
    return None


def health_of(monet: dict) -> str:
    """Card color: monetized = red; else min(subs %, hours %) >= 70 red, < 30 blue, between purple."""
    if monet["monetized"]:
        return "red"
    if monet["subs_pct"] is None or monet["hours_pct"] is None:
        return "grey"
    score = min(monet["subs_pct"], monet["hours_pct"])
    return "red" if score >= 70 else "blue" if score < 30 else "purple"


# Runway of scheduled uploads: days from today to the last scheduled publish. >= RED_DAYS red, < BLUE_DAYS blue.
SCHEDULE_RED_DAYS, SCHEDULE_BLUE_DAYS = 7, 3


def _schedule_summary(rows, now) -> dict:
    """Per kind (long / short): how many are scheduled, the next publish time and how many days ahead the last one is."""
    today = now.astimezone(KST).date()
    out = {}
    for kind in ("long", "short"):
        mine = sorted((r["publish_at"] for r in rows if r.get("content_kind") == kind and r.get("publish_at")
                       and r["publish_at"] >= now))
        if not mine:
            out[kind] = {"n": 0, "next": None, "last": None, "ahead_days": 0, "status": "blue"}
            continue
        ahead = (mine[-1].astimezone(KST).date() - today).days
        out[kind] = {"n": len(mine), "next": mine[0], "last": mine[-1], "ahead_days": ahead,
                     "status": "red" if ahead >= SCHEDULE_RED_DAYS else "blue" if ahead < SCHEDULE_BLUE_DAYS else "purple"}
    return out


def _pct_of(value, goal):
    return None if value is None else min(round(value / goal * 100, 1), 100.0)


def _best_subscribers(snapshot) -> tuple[int | None, bool]:
    """(count, approx). The reconstructed exact count lags Analytics by ~3 days and the API value is rounded
    down from 1,000 on, so both undershoot the truth: the larger one is always the better estimate.
    approx is True when the shown number is the rounded API value."""
    if snapshot is None:
        return None, False
    exact, api = snapshot.get("exact_subscribers"), snapshot.get("api_subscribers")
    if api is not None and api < 1000:
        return api, False  # below 1,000 the API value is exact and live; Analytics lags ~3 days
    if exact is None:
        return api, api is not None and api >= 1000
    if api is not None and api > exact:
        return api, True
    return exact, False


def _monet(subs_n, yearly_row, monetized) -> dict:
    hours = _round(_hours(yearly_row) if yearly_row else None, 1)
    return {"subs": subs_n, "subs_pct": _pct_of(subs_n, SUBS_GOAL),
            "hours": hours, "hours_pct": _pct_of(hours, HOURS_GOAL), "monetized": monetized}


def _h48(by_day, latest, up, down, comparable) -> dict:
    if latest is None:
        return {"cur": None, "prev": None, "pct": None, "status": "grey", "days": []}
    cur_days = [latest - timedelta(days=1), latest]
    prev_days = [latest - timedelta(days=3), latest - timedelta(days=2)]
    cur = _sum(_hours(by_day[d]) for d in cur_days if d in by_day)
    prev = _sum(_hours(by_day[d]) for d in prev_days if d in by_day)
    pct = periods.pct_change(cur, prev) if comparable else None
    return {"cur": _round(cur, 1), "prev": _round(prev, 1) if comparable else None, "pct": pct,
            "status": periods.color_of(pct, up, down), "days": cur_days}


# Live runs are every 2 hours and write a row only while a broadcast is live; 3 hours is that
# cadence plus slack for a late scheduled run.
LIVE_STALE_AFTER = timedelta(hours=3)


def _live_run(runs, key) -> tuple[datetime, bool] | None:
    """(started_at, healthy) of the newest run that ran `live` for this channel; None when there is none."""
    for r in runs:
        if _covers(r, key) and _ran_any(r, ("live",)):
            started = r.get("started_at")
            if started is None:
                return None
            bad = any(e.get("channel") == key and e.get("stage") in ("live", "client", "store:yt_live_snapshot")
                      for e in (r.get("errors") or []))
            return started, not bad
    return None


def _live_state(rows, now, run=None) -> dict | None:
    """State from the channel's newest snapshot; only active broadcasts leave rows.

    run: `_live_run` of the channel. A healthy live run that started after the snapshot saw no
    broadcast (it would have written a row), so the channel is off-air. Without such a run the
    snapshot counts as current for LIVE_STALE_AFTER; older than that (or none at all) means
    off-air when the newest live run is recent and healthy, otherwise unknown (on=None).
    """
    unknown = {"on": None, "dual": False, "count": 0, "viewers": None, "views": None,
               "title": None, "taken_at": None, "stale": False}
    taken_at = max((r["taken_at"] for r in rows), default=None)
    started, healthy = run if run else (None, False)
    if taken_at is not None and healthy and started > taken_at:
        return {**unknown, "on": False, "taken_at": taken_at}
    if taken_at is None or now - taken_at > LIVE_STALE_AFTER:
        if healthy and now - started <= LIVE_STALE_AFTER:
            return {**unknown, "on": False, "taken_at": taken_at}
        return {**unknown, "taken_at": taken_at, "stale": taken_at is not None}
    active = [r for r in rows if r["taken_at"] == taken_at
              and r.get("broadcast_id") != "none" and r.get("life_cycle") == "live"]
    return {
        "on": bool(active), "dual": len(active) >= 2, "count": len(active),
        "viewers": _sum(r.get("concurrent") for r in active),
        "views": _sum(r.get("views") for r in active),
        "title": active[0].get("title") if active else None,
        "taken_at": taken_at, "stale": False,
    }


def _subs_series(by_day, start, end, now, latest) -> list[dict]:
    """Restored subscriber count per day: now minus the net gained after that day."""
    running = now
    totals: dict[date, int | None] = {}
    d = latest
    while d >= start:
        totals[d] = running
        if running is not None and d in by_day:
            running -= _subs_net(by_day[d]) or 0
        d -= timedelta(days=1)
    return [{"day": d, "total": totals.get(d), "net": _subs_net(by_day[d]) if d in by_day else None}
            for d in _days(start, end)]


def _subs_trend(by_day, latest, first_day, now, up, down) -> dict:
    out = {}
    for n in SUBS_WINDOWS:
        if latest is None:
            out[str(n)] = {"start": None, "end": None, "total_net": None, "status": "grey", "series": []}
            continue
        start = latest - timedelta(days=n - 1)
        if n == 365 and first_day is not None:
            start = max(start, first_day)
        series = _subs_series(by_day, start, latest, now, latest)
        nets = [s["net"] for s in series]
        out[str(n)] = {"start": start, "end": latest, "total_net": _sum(nets),
                       "status": periods.color_of(periods.half_trend(nets), up, down), "series": series}
    return out


def _watch_trend(by_day, latest, first_day, up, down) -> dict:
    out = {}
    for n in WATCH_WINDOWS:
        if latest is None:
            out[str(n)] = {"start": None, "end": None, "total": None, "status": "grey", "series": []}
            continue
        start = latest - timedelta(days=n - 1)
        if n == 365 and first_day is not None:
            start = max(start, first_day)
        hours = [_hours(by_day[d]) if d in by_day else None for d in _days(start, latest)]
        out[str(n)] = {
            "start": start, "end": latest, "total": _round(_sum(hours), 1),
            "status": periods.color_of(periods.half_trend(hours), up, down),
            "series": [{"day": d, "hours": _round(h, 1)} for d, h in zip(_days(start, latest), hours)],
        }
    return out


def _segment(rows, peak_note, as_of) -> dict:
    """One audience segment: age/gender weighted across vod+live, country merged, peak hours note."""
    weight = {r["content"]: _num(r.get("views")) or 0 for r in rows if r["dim"] == "weight"}
    by_content: dict[str, dict[str, float]] = {}
    for r in rows:
        if r["dim"] == "age_gender":
            by_content.setdefault(r["content"], {})[r["key"]] = _num(r.get("pct")) or 0.0
    total_w = sum(weight.get(c, 0) for c in by_content)
    # contents without a usable weight share the window equally
    weights = {c: (weight.get(c, 0) if total_w > 0 else 1) for c in by_content}
    denom = sum(weights.values())
    age_gender = []
    if denom > 0:
        keys = {k for pcts in by_content.values() for k in pcts}
        for key in keys:
            pct = sum(by_content[c].get(key, 0.0) * w for c, w in weights.items()) / denom
            age, gender = key.split("/", 1)
            age_gender.append({"age": age, "gender": gender, "pct": round(pct, 1)})
        age_gender.sort(key=lambda a: (-a["pct"], a["age"], a["gender"]))
    country: dict[str, dict] = {}
    for r in rows:
        if r["dim"] == "country":
            c = country.setdefault(r["key"], {"country": r["key"], "views": 0, "minutes": 0.0})
            c["views"] += _num(r.get("views")) or 0
            c["minutes"] += _num(r.get("minutes")) or 0.0
    top_country = sorted(country.values(), key=lambda c: -c["minutes"])[:COUNTRY_N]
    return {"age_gender": age_gender, "country": top_country, "peak_hours": peak_note, "as_of": as_of}


def _audience(rows, notes) -> dict:
    as_of = max((r["as_of"] for r in rows), default=None)
    latest_rows = [r for r in rows if r["as_of"] == as_of]
    return {name: _segment([r for r in latest_rows if r["segment"] == seg], notes.get(PEAK_FIELDS[name]), as_of)
            for seg, name in SEGMENTS.items()}


def _per_video(vd_rows) -> dict[str, dict]:
    """Recent minutes / views per video from yt_video_daily rows."""
    out: dict[str, dict] = {}
    for r in vd_rows:
        v = out.setdefault(r["video_id"], {"minutes": 0.0, "views": 0})
        v["minutes"] += _num(r.get("minutes")) or 0.0
        v["views"] += r.get("views") or 0
    return out


def _top(per_video, videos, kind) -> list[dict]:
    rows = [(vid, m) for vid, m in per_video.items()
            if vid in videos and videos[vid].get("content_kind") == kind]
    rows.sort(key=lambda x: -x[1]["minutes"])
    return [{"video_id": vid, "title": videos[vid].get("title"), "thumb": videos[vid].get("thumbnail_url"),
             "published_at": videos[vid].get("published_at"), "hours": round(m["minutes"] / 60, 1),
             "views": m["views"]} for vid, m in rows[:TOP_N]]


def _genres(per_video, videos, playlists, items) -> list[dict]:
    """Watch hours per playlist title (shorts excluded; a video counts in every playlist it is in)."""
    minutes: dict[str, float] = {}
    for it in items:
        v = per_video.get(it["video_id"])
        pl = playlists.get(it["playlist_id"])
        if v is None or pl is None or videos.get(it["video_id"], {}).get("content_kind") == "short":
            continue
        name = pl.get("title") or it["playlist_id"]
        minutes[name] = minutes.get(name, 0.0) + v["minutes"]
    total = sum(minutes.values())
    top = sorted(minutes.items(), key=lambda x: -x[1])[:GENRE_N]
    return [{"name": name, "hours": round(m / 60, 1), "share": round(m / total * 100, 1) if total else None}
            for name, m in top]


def _subs_sources(rows) -> dict:
    """Where new subscribers came from. Only days with the whole split (gained, shorts, vod,
    live all known) count, so days collected before the split columns existed cannot inflate "other"."""
    split = [r for r in rows
             if all(r.get(c) is not None for c in
                    ("subs_gained", "subs_gained_shorts", "subs_gained_vod", "subs_gained_live"))]
    gained = _sum(r["subs_gained"] for r in split)
    shorts = _sum(r["subs_gained_shorts"] for r in split)
    vod = _sum(r["subs_gained_vod"] for r in split)
    live = _sum(r["subs_gained_live"] for r in split)
    other = None if gained is None else max(0, gained - shorts - vod - live)
    return {"days": len(split), "shorts": shorts, "vod": vod, "live": live, "other": other,
            "lost": _sum(r.get("subs_lost") for r in rows)}


def _weighted_ctr(pairs) -> float | None:
    """CTR of several (impressions, ctr) groups: clicks over impressions, i.e. each ctr weighted by its impressions."""
    pairs = [(_num(i), _num(c)) for i, c in pairs if i is not None and c is not None]
    total = sum(i for i, _ in pairs)
    return sum(i * c for i, c in pairs) / total if total else None


def _reach_latest_day(rows) -> date | None:
    return max((r["day"] for r in rows), default=None)


def _in_window(rows, end, days):
    start, stop = periods.window(end, days)
    return [r for r in rows if start <= r["day"] <= stop]


def _reach_window(rows, end, days) -> tuple[int | None, float | None]:
    """(impressions, ctr) over the `days` days ending at `end`; ctr is impressions-weighted, None without impressions."""
    got = _in_window(rows, end, days)
    return _sum(r.get("impressions") for r in got), _weighted_ctr((r.get("impressions"), r.get("ctr")) for r in got)


def _reach_summary(rows, end, days, up, down) -> dict:
    """Impressions and ctr of the window ending at `end`, judged against the stretch just before it.

    The stretch is periods.compare_window (at least 28 days: a short window is compared with a multi-week
    average, not one noisy week). Both sides are compared per calendar day (days without a row count as zero
    impressions, which is how the report omits them), limited to the days since the channel's first report day;
    `window_days` is that real length of the window (below `days` only in the first weeks). A stretch with under
    a week of data gives no comparison at all.
    impressions_pct is a percent change; ctr_pp is in percentage points; the statuses colour them like h48
    (rising red, falling blue). ctr is a 0..1 ratio, as stored.
    """
    cur_i, cur_c = _reach_window(rows, end, days)
    first = min((r["day"] for r in rows), default=end)
    cur_start, _ = periods.window(end, days)
    window_days = (end - max(cur_start, first)).days + 1
    prev_start, prev_end = periods.compare_window(periods.window(end, days))
    prev_len = (prev_end - prev_start).days + 1
    prev_i, prev_c = _reach_window(rows, prev_end, prev_len)
    prev_days = max(0, (prev_end - max(prev_start, first)).days + 1)  # calendar days with history behind them
    prev_data_days = len({r["day"] for r in _in_window(rows, prev_end, prev_len)})
    comparable = prev_data_days >= REACH_BASELINE_MIN_DAYS and prev_days > 0
    pct = (periods.pct_change(cur_i / window_days, prev_i / prev_days)
           if comparable and cur_i is not None and prev_i is not None else None)
    ctr_pct = periods.pct_change(cur_c, prev_c) if comparable else None
    ctr_pp = round((cur_c - prev_c) * 100, 2) if comparable and cur_c is not None and prev_c is not None else None
    return {"impressions": cur_i, "ctr": _round(cur_c, 5), "impressions_pct": pct, "ctr_pp": ctr_pp,
            "impressions_status": periods.color_of(pct, up, down), "ctr_status": periods.color_of(ctr_pct, up, down),
            "as_of": end, "window_days": window_days}


def _reach_verdict(impressions, ctr, age_days, channel_ctr, median_impressions) -> str | None:
    """"fix" / "push" / "ok", or None while a video is too young, too small or its baseline unknown."""
    if age_days is None or age_days < REACH_MIN_AGE_DAYS:
        return None
    if impressions is None or ctr is None or impressions < REACH_MIN_IMPRESSIONS:
        return None
    if channel_ctr is None or channel_ctr <= 0 or median_impressions is None:
        return None  # no clicks on the whole channel: there is no baseline to be above or below
    if ctr <= REACH_FIX_CTR_RATIO * channel_ctr and impressions >= median_impressions:
        return "fix"
    if ctr >= REACH_PUSH_CTR_RATIO * channel_ctr and impressions <= REACH_PUSH_IMPRESSIONS_RATIO * median_impressions:
        return "push"
    return "ok"


def _kst_date(value) -> date | None:
    """Seoul calendar date of a stored timestamp (what the page shows as "올린 날")."""
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(KST).date()
    return value if isinstance(value, date) else None


def _reach_by_video(rows, end, days) -> dict[str, tuple]:
    """{video_id: (impressions, ctr)} over the window, for videos that were shown at all."""
    groups: dict[str, list] = {}
    for r in _in_window(rows, end, days):
        groups.setdefault(r["video_id"], []).append(r)
    out = {}
    for vid, got in groups.items():
        impressions = _sum(r.get("impressions") for r in got)
        if impressions:
            out[vid] = (impressions, _weighted_ctr((r.get("impressions"), r.get("ctr")) for r in got))
    return out


def _reach_detail(rows, end, channel_key, videos, per_video, up, down) -> dict:
    """Detail panel data: 28-day summary, this week's uploads, the most shown videos, shorts vs long ctr."""
    stats = _reach_by_video(rows, end, REACH_WINDOW_DAYS)
    channel_ctr = _reach_window(rows, end, REACH_WINDOW_DAYS)[1]
    median = statistics.median(i for i, _ in stats.values()) if stats else None

    def row(vid):
        v = videos.get(vid) or {}
        published = _kst_date(v.get("published_at"))
        impressions, ctr = stats.get(vid, (None, None))
        verdict = _reach_verdict(impressions, ctr, (end - published).days if published else None, channel_ctr, median)
        return {"video_id": vid, "title": v.get("title"), "published_at": published, "kind": v.get("content_kind"),
                "impressions": impressions, "ctr": _round(ctr, 5), "views": (per_video.get(vid) or {}).get("views"),
                "verdict": verdict}

    # uploads of the last 7 days up to the newest reach day (Seoul dates), newest first; kept even when YouTube
    # has not reported them yet, so a fresh upload shows up with "—" instead of missing
    week_start = end - timedelta(days=REACH_BOARD_DAYS - 1)
    this_week = sorted(
        ((v["published_at"], vid) for vid, v in videos.items()
         if v.get("channel_key") == channel_key and week_start <= (_kst_date(v["published_at"]) or date.min) <= end),
        reverse=True)
    most_shown = sorted(stats, key=lambda vid: (-stats[vid][0], vid))[:REACH_TOP_N]

    def kind_ctr(kind):
        return _round(_weighted_ctr(stats[vid] for vid in stats if (videos.get(vid) or {}).get("content_kind") == kind), 5)

    return {"days": REACH_WINDOW_DAYS, **_reach_summary(rows, end, REACH_WINDOW_DAYS, up, down),
            "this_week": [row(vid) for _, vid in this_week], "all": [row(vid) for vid in most_shown],
            "shorts_ctr": kind_ctr("short"), "long_ctr": kind_ctr("long")}


def build(conn, *, today: date, config, now: datetime | None = None, quota: dict | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    channels, th = config["channels"], config["thresholds"]
    up, down = th["up_pct"], th["down_pct"]
    keys = [k for k in ORDER if k in channels] + [k for k in channels if k not in ORDER]

    daily = fetch(conn, "select * from yt_channel_daily order by day")
    latest = max((r["day"] for r in daily), default=None)
    by_ch: dict[str, dict[date, dict]] = {k: {} for k in keys}
    for r in daily:
        by_ch.setdefault(r["channel_key"], {})[r["day"]] = r
    first_day = {k: min(rows, default=None) for k, rows in by_ch.items()}
    ch_latest = {k: max(rows, default=None) for k, rows in by_ch.items()}

    subs = _latest_per_channel(fetch(conn, "select * from yt_subs_snapshot"), "taken_on")
    # only each channel's newest snapshot: the table grows with every live run
    live_rows = fetch(conn, "select * from yt_live_snapshot where (channel_key, taken_at) in "
                            "(select channel_key, max(taken_at) from yt_live_snapshot group by 1)")
    yearly = _latest_per_channel(fetch(conn, "select * from yt_yearly_minutes"), "as_of")
    notes: dict[str, dict[str, str | None]] = {}
    for r in fetch(conn, "select * from yt_manual"):
        if r["field"] in PEAK_FIELDS.values():
            notes.setdefault(r["channel_key"], {})[r["field"]] = r.get("note")
    runs = fetch(conn, "select * from yt_run_log order by started_at desc limit 200")

    recent_start = latest - timedelta(days=RECENT_DAYS - 1) if latest else None
    problems: list[dict] = []
    vd_rows = _safe_fetch(conn, "select * from yt_video_daily where day >= %s and day <= %s",
                          (recent_start, latest), problems=problems) if latest else []
    videos = {r["video_id"]: r for r in _safe_fetch(conn, "select * from yt_video", problems=problems)}
    playlists = {r["playlist_id"]: r for r in _safe_fetch(conn, "select * from yt_playlist", problems=problems)}
    items = _safe_fetch(conn, "select * from yt_playlist_item", problems=problems)
    audience_rows = _safe_fetch(conn, "select * from yt_audience where (channel_key, as_of) in "
                                      "(select channel_key, max(as_of) from yt_audience group by 1)",
                                (), problems=problems)

    reach_rows = _safe_fetch(conn, "select * from yt_reach_daily where day >= %s",
                             (latest - timedelta(days=REACH_FETCH_DAYS),), problems=problems) if latest else []

    schedule_rows = _safe_fetch(conn, "select channel_key, publish_at, content_kind from yt_schedule",
                                (), problems=problems)

    out_channels, board, subs_trend, watch_trend, detail = [], {}, {}, {}, {}
    errors: list[dict] = []
    for k in keys:
        ch = channels[k]
        ch_errors = [{**e, "human": human_error(e, now)} for e in _channel_errors(runs, k)]
        errors += ch_errors
        failed = any(_failed(e.get("stage")) for e in ch_errors)
        out_channels.append({"key": k, "display": ch.display, "is_live": ch.is_live,
                             "collect_failed": failed, "errors": ch_errors})
        by_day = by_ch[k]
        s = subs.get(k)
        subs_n, subs_approx = _best_subscribers(s)
        monet = _monet(subs_n, yearly.get(k), bool(s and s.get("monetized")))
        # a channel behind the global latest day (or whose collection failed) gets no comparison
        comparable = not failed and ch_latest[k] is not None and ch_latest[k] >= (latest or ch_latest[k])
        ch_reach = [r for r in reach_rows if r["channel_key"] == k]
        # the headline impressions / ctr count long videos and live archives only; shorts distort both
        ch_reach_nos = [r for r in ch_reach if (videos.get(r["video_id"]) or {}).get("content_kind") != "short"]
        reach_end = _reach_latest_day(ch_reach)  # each channel's own newest report day, not the channel feed's
        reach_stale = (reach_end is not None and latest is not None
                       and reach_end < latest - timedelta(days=REACH_STALE_DAYS))
        stale_reach = {"stale": True, "as_of": reach_end}
        board[k] = {
            "subscribers": subs_n,
            "subscribers_approx": subs_approx,
            "h48": _h48(by_day, latest, up, down, comparable),
            "live": _live_state([r for r in live_rows if r["channel_key"] == k], now, _live_run(runs, k)) if ch.is_live else None,
            "health": health_of(monet),
            "monet": monet,
            "schedule": _schedule_summary([r for r in schedule_rows if r["channel_key"] == k], now),
            "as_of": {"subs": (s.get("taken_on") if subs_n is not None and subs_n == s.get("api_subscribers") else ch_latest[k]) if s else ch_latest[k],
                      "hours": ch_latest[k], "h48": ch_latest[k]},
            "reach7": (stale_reach if reach_stale else
                       _reach_summary(ch_reach_nos, reach_end, REACH_BOARD_DAYS, up, down) if reach_end else None),
        }
        subs_trend[k] = _subs_trend(by_day, latest, first_day[k], subs_n, up, down)
        watch_trend[k] = _watch_trend(by_day, latest, first_day[k], up, down)
        per_video = _per_video([r for r in vd_rows if r["channel_key"] == k])
        recent_daily = [r for d, r in by_day.items() if recent_start and recent_start <= d <= latest]
        detail[k] = {
            "monet": monet,
            "audience": _audience([r for r in audience_rows if r["channel_key"] == k], notes.get(k, {})),
            "top_long": _top(per_video, videos, "long"),
            "top_live": _top(per_video, videos, "live_archive"),
            "subs_sources": _subs_sources(recent_daily),
            "genres": _genres(per_video, videos, playlists, [i for i in items if i["channel_key"] == k]),
            "reach": (stale_reach if reach_stale else
                      {**_reach_detail(ch_reach, reach_end, k, videos, per_video, up, down),
                       **_reach_summary(ch_reach_nos, reach_end, REACH_WINDOW_DAYS, up, down)} if reach_end else None),
        }

    # Render-side read failures are shown on the page but are not collect failures (channels untouched).
    errors += [{**p, "human": human_error(p, now)} for p in problems]

    return {
        "v": 3,
        "generated_at": now,
        "last_daily_ok_at": _last_daily_ok_at(runs),
        "latest_day": latest,
        "lag_days": (today - latest).days if latest else None,
        "order": list(ORDER),
        "channels": out_channels,
        "board": board,
        "subs_trend": subs_trend,
        "watch_trend": watch_trend,
        "detail": detail,
        "errors": errors,
        "quota": quota,
    }
