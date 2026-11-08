// yt-ops dashboard v3: static page, renders data.json (from data.enc, or sample.json in dev).
// Routes (hash): #board (default) · #subs · #watch · #api · #ch/<key>
"use strict";

const STORE_KEY = "ytops_pw";
const WIN_KEY = "ytops_watch_win";
const app = document.getElementById("app");
let DATA = null;
let sampleMode = false;
let watchWin = "28";
const REFRESH_URL = "https://yt-ops-refresh.vercel.app/api/refresh";  // Vercel function (refresh/README.md); empty hides the button
const REFRESH_LABEL = "지금 새로고침";
const POLL_MS = 30000, POLL_MAX_MS = 8 * 60 * 1000;
// Button state lives here (not in the DOM) because render() rebuilds the header on every hash change.
let rf = { text: REFRESH_LABEL, disabled: false };
let rfTimer = null, rfPoll = null;

// ---------- helpers ----------
const isNull = (v) => v === null || v === undefined;
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (v, d = 0) => isNull(v) ? "—" : Number(v).toLocaleString("ko-KR", { maximumFractionDigits: d });
const signed = (v, d = 0) => isNull(v) ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + fmt(Math.abs(v), d);
const pct = (v) => isNull(v) ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${fmt(Math.abs(v), Math.abs(v) < 10 ? 1 : 0)}%`;
const kst = (iso) => {
  const o = {};
  new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
    .formatToParts(new Date(iso)).forEach((p) => { o[p.type] = p.value; });
  return o;
};
const mdhm = (iso) => { const p = kst(iso); return `${p.month}/${p.day} ${p.hour}:${p.minute}`; };
const ymd = (d) => { if (!d) return "—"; const [, m, dd] = d.split("-"); return `${+m}/${+dd}`; };
const ymdFull = (d) => { if (!d) return "—"; const [y, m, dd] = d.split("-"); return `${y}.${+m}.${+dd}`; };
const COLOR = { red: "var(--red)", purple: "var(--purple)", blue: "var(--blue)", grey: "var(--off)" };
const col = (s) => COLOR[s] || COLOR.grey;
const nameOf = (key) => { if (key == null) return "상황판"; const c = DATA.channels.find((x) => x.key === key); return c ? c.display : key; };

function store(op, key, value) {
  try {
    if (op === "get") return localStorage.getItem(key);
    if (op === "set") localStorage.setItem(key, value);
    if (op === "del") localStorage.removeItem(key);
  } catch (e) { /* storage may be blocked; page still works */ }
  return null;
}

// ---------- charts (inline SVG, no libraries) ----------
// Subscriber window: line = restored total, small bars below = daily net.
function subsChart(win, status) {
  const W = 320, H = 130, LH = 78, BH = 34, PAD = 4;
  const s = win.series || [];
  const n = s.length;
  if (!n) return `<div class="nochart">—</div>`;
  const totals = s.map((p) => p.total).filter((v) => !isNull(v));
  const nets = s.map((p) => p.net).filter((v) => !isNull(v));
  const tMax = totals.length ? Math.max(...totals) : null;
  const tMin = totals.length ? Math.min(...totals) : null;
  const nMax = nets.length ? Math.max(1, ...nets.map(Math.abs)) : 1;
  const xw = W / n;
  const xOf = (i) => (i + 0.5) * xw;
  const yOf = (v) => tMax === tMin ? PAD + (LH - 2 * PAD) / 2 : PAD + (LH - 2 * PAD) * (1 - (v - tMin) / (tMax - tMin));
  // line path, broken at null days
  let d = "", pen = false;
  s.forEach((p, i) => {
    if (isNull(p.total)) { pen = false; return; }
    d += `${pen ? "L" : "M"}${xOf(i).toFixed(1)} ${yOf(p.total).toFixed(1)} `;
    pen = true;
  });
  const zero = LH + BH / 2;
  const bw = Math.max(0.6, xw * (n > 60 ? 0.9 : 0.6));
  const bars = s.map((p, i) => {
    if (isNull(p.net)) return "";
    const h = Math.abs(p.net) / nMax * (BH / 2 - 1);
    const y = p.net >= 0 ? zero - h : zero;
    return `<rect x="${(xOf(i) - bw / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(h, 0.6).toFixed(1)}" fill="${p.net >= 0 ? col(status) : "var(--ink-3)"}" opacity="0.75"/>`;
  }).join("");
  const hits = s.map((p, i) => `<rect class="hit" x="${(i * xw).toFixed(1)}" y="0" width="${xw.toFixed(1)}" height="${H}" fill="transparent"><title>${ymdFull(p.day)} 구독자 ${fmt(p.total)} · 순증 ${signed(p.net)}</title></rect>`).join("");
  const dots = n <= 31 ? s.map((p, i) => isNull(p.total) ? "" : `<circle cx="${xOf(i).toFixed(1)}" cy="${yOf(p.total).toFixed(1)}" r="2.6" fill="${col(status)}"/>`).join("") : "";
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="구독자 추이">
    <line x1="0" y1="${zero}" x2="${W}" y2="${zero}" stroke="var(--rule)" stroke-width="0.6"/>
    ${bars}<path d="${d.trim()}" fill="none" stroke="${col(status)}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>${dots}${hits}</svg>
    <div class="axis"><span>${ymd(win.start)}</span><span class="n">최고 ${fmt(tMax)}</span><span>${ymd(win.end)}</span></div>`;
}

// Watch window: daily hours bars.
function hoursChart(win, status) {
  const W = 320, H = 90, PAD = 2;
  const s = win.series || [];
  const n = s.length;
  if (!n) return `<div class="nochart">—</div>`;
  const vals = s.map((p) => p.hours).filter((v) => !isNull(v));
  const max = vals.length ? Math.max(...vals) : 0;
  const xw = W / n;
  const gap = n > 60 ? 0.2 : n > 14 ? 1.5 : 4;
  const bw = Math.max(0.6, xw - gap);
  const rects = s.map((p, i) => {
    const x = (i * xw + gap / 2).toFixed(1);
    if (isNull(p.hours)) return `<rect x="${x}" y="${H - 2}" width="${bw.toFixed(1)}" height="2" fill="var(--rule)"><title>${ymdFull(p.day)} 자료 없음</title></rect>`;
    const h = max ? Math.max(1, p.hours / max * (H - PAD)) : 1;
    return `<rect x="${x}" y="${(H - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" fill="${col(status)}"><title>${ymdFull(p.day)} ${fmt(p.hours, 1)}시간</title></rect>`;
  }).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="하루별 시청시간">${rects}</svg>
    <div class="axis"><span>${ymd(win.start)}</span><span class="n">최고 ${fmt(max, 1)}시간</span><span>${ymd(win.end)}</span></div>`;
}

// Horizontal bars: rows = [{label, value, text, color}], scaled to the largest value.
function hbars(rows, color) {
  const vals = rows.map((r) => r.value).filter((v) => !isNull(v));
  const max = vals.length ? Math.max(...vals.map(Math.abs)) || 1 : 1;
  if (!rows.length) return `<div class="nochart">—</div>`;
  return `<div class="hbars">${rows.map((r) => {
    const w = isNull(r.value) ? 0 : Math.abs(r.value) / max * 100;
    return `<div class="hrow"><span class="hl">${esc(r.label)}</span>
      <svg viewBox="0 0 100 10" preserveAspectRatio="none" role="img" aria-label="${esc(r.label)} ${esc(r.text)}"><rect x="0" y="0" width="100" height="10" fill="var(--track)"/><rect x="0" y="0" width="${w.toFixed(1)}" height="10" fill="${col(r.color || color)}"><title>${esc(r.label)} ${esc(r.text)}</title></rect></svg>
      <span class="hv n">${esc(r.text)}</span></div>`;
  }).join("")}</div>`;
}

// Progress bar toward a target.
function progress(label, have, p, target, unit, color) {
  const w = isNull(p) ? 0 : Math.min(100, p);
  return `<div class="prog"><div class="pl"><span>${label}</span><span class="n"><b>${fmt(have, unit === "시간" ? 0 : 0)}</b> / ${target}${unit}</span></div>
    <svg viewBox="0 0 100 12" preserveAspectRatio="none" role="progressbar" aria-label="${label}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${w.toFixed(0)}"><rect x="0" y="0" width="100" height="12" fill="var(--track)"/><rect x="0" y="0" width="${w.toFixed(1)}" height="12" fill="${col(color)}"><title>${label} ${isNull(p) ? "—" : fmt(p, 1) + "%"}</title></rect></svg>
    <div class="pp n t-${color}">${isNull(p) ? "—" : fmt(p, 1) + "%"}</div></div>`;
}

// ---------- API usage (quota) ----------
const hm = (iso) => { const p = kst(iso); return `${p.hour}:${p.minute}`; };
// Usage status -> existing colour tone (no green/amber in the palette: ok = calm blue, warn = purple).
const QUOTA_TONE = { ok: "blue", warn: "purple", bad: "red", out: "red", unknown: "grey" };
const quotaTone = (p) => QUOTA_TONE[p.status] || "grey";
const usageKnown = (p) => !isNull(p.used) && !p.error;

function hoursBars(hours) {
  if (!hours.length) return `<div class="nochart">—</div>`;
  const max = Math.max(...hours.map((x) => x.n), 1);
  let prevDay = null;
  return `<div class="qhours" role="img" aria-label="시간대별 사용량">${hours.map((x) => {
    const [day, hour] = x.h.split(" ");
    const showDay = day !== prevDay;
    prevDay = day;
    return `<div class="qh" title="${esc(x.h)} ${fmt(x.n)}단위"><span class="qn n">${fmt(x.n)}</span><span class="qbar"><i style="height:${Math.max(3, x.n / max * 100).toFixed(0)}%"></i></span><span class="ql n">${esc(hour)}</span><span class="qd n">${showDay ? esc(day) : ""}</span></div>`;
  }).join("")}</div>`;
}

function quotaCard(p) {
  const names = (p.channels || []).map(nameOf).join(" · ");
  const head = `<div class="namerow"><h2>${esc(p.label)}${names ? ` (${esc(names)})` : ""}</h2></div>`;
  if (!usageKnown(p)) return `<article class="card h-grey">${head}<div class="fail">사용량을 읽지 못했어요 (권한 또는 네트워크)</div></article>`;
  const mark = p.status === "out" ? "⛔ 소진 " : p.status === "bad" ? "⚠ " : "";
  const w = Math.min(100, p.pct || 0);
  const when = `${p.reset_at ? `${hm(p.reset_at)} 에 0 으로 돌아감` : ""}${p.reset_at && DATA.quota.as_of ? " · " : ""}${DATA.quota.as_of ? `${hm(DATA.quota.as_of)} 기준` : ""}`;
  const apps = (p.apps || []).map((a) => ({ label: a.name, value: a.n, text: `${fmt(a.n)}${p.used ? ` (${fmt(Math.round(a.n / p.used * 100))}%)` : ""}` }));
  const methods = (p.methods || []).map((m) => ({ label: m.name, value: m.n, text: fmt(m.n) }));
  const tone = quotaTone(p);
  return `<article class="card h-${tone}">${head}
    <div class="stat"><span class="num n t-${tone}">${mark}${fmt(p.used)} / ${fmt(p.limit)}<small>단위 (${fmt(p.pct)}%)</small></span></div>
    <div class="qtrack"><i class="s-${tone}" style="width:${w}%"></i></div>
    <div class="n qwhen">${esc(when)}</div>
    <div><h4>시간대별</h4>${hoursBars(p.hours || [])}</div>
    <div><h4>어디서 썼나</h4>${hbars(apps, tone)}</div>
    <div><h4>메서드</h4>${hbars(methods, tone)}</div>
    <div class="n qwhen">Analytics API <b>${fmt(p.analytics_used)}</b> / ${fmt(p.analytics_limit)}</div>
  </article>`;
}

function renderApi() {
  const q = DATA.quota;
  const projects = (q && q.projects) || [];
  const limit = (projects.find((p) => !isNull(p.limit)) || {}).limit || 10000;
  const size = Math.max(0, ...projects.map((p) => (p.channels || []).length));
  const intro = `<p class="apinote">한도는 Google 프로젝트(채널 ${fmt(size || 4)}개 묶음)마다 하루 ${fmt(limit)} 단위예요. 다 쓰면 그날 수집이 멈추고, 태평양 자정(한국 16~17시)에 0 으로 돌아가요.</p>`;
  // Numbers refresh with each collection run (09:30 and every odd hour KST) and reach the page ~10 min later.
  const asOf = q && q.as_of ? `<p class="qwhen n">${hm(q.as_of)} 기준 · 숫자는 매일 09:30 과 홀수 시 정각(01·03·…·23시) 수집 뒤 10분쯤 지나 바뀌고, 17시 수집 뒤 0 근처로 돌아가요</p>` : "";
  if (!projects.length) return `${intro}<article class="card h-grey"><div class="fail">API 사용량을 확인하지 못했어요</div></article>`;
  return `${intro}${asOf}<div class="apigrid">${projects.map(quotaCard).join("")}</div>`;
}

// ---------- top ----------
function route() {
  const h = (location.hash || "#board").slice(1);
  if (h.startsWith("ch/")) return { view: "ch", key: h.slice(3) };
  return { view: ["board", "subs", "watch", "api"].includes(h) ? h : "board" };
}

function refreshButton() {
  if (sampleMode) return `<button type="button" class="refresh" id="refresh" disabled title="시안 모드">${REFRESH_LABEL}</button>`;
  if (!REFRESH_URL) return "";
  return `<button type="button" class="refresh" id="refresh"${rf.disabled ? " disabled" : ""}>${esc(rf.text)}</button>`;
}

function renderTop(view) {
  const tabs = [["board", "현황판"], ["subs", "구독자"], ["watch", "시청시간"], ["api", "API"]]
    .map(([k, t]) => `<a href="#${k}" ${view === k ? 'aria-current="page"' : ""}>${t}</a>`).join("");
  return `<header class="top">
    <h1>유튜브 상황판</h1>
    <nav class="tabs" aria-label="화면">${tabs}</nav>
    <div class="meta n"><span>생성 ${mdhm(DATA.generated_at)} · 기준일 ${ymd(DATA.latest_day)} · 지연 ${fmt(DATA.lag_days)}일</span>${refreshButton()}</div>
  </header>`;
}

// ---------- #board ----------
/** Snapshot time for the live block; a channel with no snapshot has taken_at null (never new Date(null)). */
const liveAt = (l) => `<span class="at n">${isNull(l.taken_at) ? "기록 없음" : mdhm(l.taken_at)}</span>`;

function liveBlock(ch, b) {
  if (!ch.is_live) return `<div class="live off"><span class="k">라이브</span><span class="v">없음</span></div>`;
  const l = b.live;
  if (!l) return `<div class="live off"><span class="k">라이브</span><span class="v">—</span></div>`;
  // on === null: state unknown (live collection stopped or never ran); stale keeps the last snapshot time
  if (l.on === null || l.on === undefined) return `<div class="live off"><span class="k">라이브</span><span class="v">확인 불가</span>${l.stale ? liveAt(l) : ""}</div>`;
  if (!l.on) return `<div class="live off"><span class="k">라이브</span><span class="v">꺼짐</span>${liveAt(l)}</div>`;
  return `<div class="live on"><span class="k">라이브</span>
    <span class="v on">방송 중${l.dual ? ` · 듀얼 ${fmt(l.count)}` : ""}</span>
    <span class="n">보는 중 <b>${fmt(l.viewers)}</b>명</span>
    <span class="n">조회 <b>${fmt(l.views)}</b></span>
    ${liveAt(l)}</div>`;
}

function renderBoard() {
  const cards = DATA.order.map((key) => {
    const ch = DATA.channels.find((c) => c.key === key) || { key, display: key, is_live: false, collect_failed: true, errors: [] };
    const b = DATA.board[key] || { subscribers: null, h48: { cur: null, pct: null, status: "grey" }, live: null, health: "grey" };
    const head = `<div class="namerow"><h2>${esc(ch.display)}</h2><a class="more" href="#ch/${esc(key)}">심화 ›</a></div>`;
    if (ch.collect_failed) {
      const e = ch.errors && ch.errors[0];
      return `<article class="card h-grey">${head}<div class="fail n">${e ? esc(e.human || e.error) : "—"}</div></article>`;
    }
    const h = b.h48 || {};
    return `<article class="card h-${esc(b.health || "grey")}">${head}
      <div class="stat"><span class="k">구독자</span><span class="num n">${fmt(b.subscribers)}</span></div>
      <div class="stat"><span class="k">48시간 유효시청</span><span class="num n">${fmt(h.cur, 1)}${isNull(h.cur) ? "" : "<small>시간</small>"}</span><span class="chg n t-${esc(h.status || "grey")}">${pct(h.pct)}</span></div>
      ${liveBlock(ch, b)}
    </article>`;
  }).join("");
  return `<div class="grid">${cards}</div>`;
}

// ---------- #subs ----------
function renderSubs() {
  const cards = DATA.order.map((key) => {
    const t = DATA.subs_trend[key];
    const head = `<div class="namerow"><h2>${esc(nameOf(key))}</h2><a class="more" href="#ch/${esc(key)}">심화 ›</a></div>`;
    if (!t) return `<article class="card h-grey">${head}<div class="fail">—</div></article>`;
    const block = (w, label) => `<div class="win"><div class="wl"><span class="k">${label}</span><span class="num n t-${esc(w.status)}">${signed(w.total_net)}</span></div>${subsChart(w, w.status)}</div>`;
    return `<article class="card h-${esc(t["365"].status)}">${head}${block(t["365"], "365일 순증")}${block(t["14"], "14일 순증")}</article>`;
  }).join("");
  return `<div class="grid">${cards}</div>`;
}

// ---------- #watch ----------
function renderWatch() {
  const seg = `<div class="seg" role="group" aria-label="기간">${["365", "28", "7"].map((p) => `<button type="button" data-win="${p}" aria-pressed="${p === watchWin}">${p}일</button>`).join("")}</div>`;
  const cards = DATA.order.map((key) => {
    const t = DATA.watch_trend[key];
    const head = `<div class="namerow"><h2>${esc(nameOf(key))}</h2><a class="more" href="#ch/${esc(key)}">심화 ›</a></div>`;
    if (!t || !t[watchWin]) return `<article class="card h-grey">${head}<div class="fail">—</div></article>`;
    const w = t[watchWin];
    return `<article class="card h-${esc(w.status)}">${head}
      <div class="stat"><span class="k">${watchWin}일 유효시청</span><span class="num n t-${esc(w.status)}">${fmt(w.total, 1)}${isNull(w.total) ? "" : "<small>시간</small>"}</span></div>
      ${hoursChart(w, w.status)}</article>`;
  }).join("");
  return `<div class="segrow">${seg}</div><div class="grid">${cards}</div>`;
}

// ---------- #ch/<key> ----------
const AGE = (a) => a.replace("age", "").replace("-", "~").replace(/~$/, "+");
const GENDER = { female: "여", male: "남", user_specified: "기타" };
const SRC = [["shorts", "쇼츠"], ["vod", "롱폼"], ["live", "라이브"], ["other", "기타"]];

function audienceBlock(title, seg) {
  const ag = (seg.age_gender || []).slice(0, 8).map((r) => ({ label: `${AGE(r.age)} ${GENDER[r.gender] || r.gender}`, value: r.pct, text: `${fmt(r.pct, 1)}%` }));
  const co = (seg.country || []).slice(0, 5).map((r) => ({ label: r.country, value: r.minutes, text: `${fmt(r.minutes / 60, 1)}시간` }));
  return `<section class="panel"><h3>${title}${seg.as_of ? `<span class="asof n">${ymd(seg.as_of)} 기준</span>` : ""}</h3>
    <div class="cols">
      <div><h4>성별 · 나이</h4>${hbars(ag, "purple")}</div>
      <div><h4>지역 Top 5</h4>${hbars(co, "purple")}</div>
      <div><h4>시청 시간대</h4><p class="peak">${seg.peak_hours ? esc(seg.peak_hours) : "—"}</p></div>
    </div></section>`;
}

function videoList(title, list) {
  const items = (list || []).slice(0, 3).map((v) => `<li class="vid">
      ${v.thumb ? `<img src="${esc(v.thumb)}" alt="" loading="lazy" onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'thumb'}))">` : `<span class="thumb"></span>`}
      <div class="vi"><span class="vt">${esc(v.title || v.video_id)}</span>
      <span class="vm n">${ymd(v.published_at)} · ${fmt(v.hours, 1)}시간 · 조회 ${fmt(v.views)}</span></div></li>`).join("");
  return `<section class="panel"><h3>${title}<span class="asof">28일</span></h3>${items ? `<ul class="vids">${items}</ul>` : `<div class="nochart">—</div>`}</section>`;
}

function renderChannel(key) {
  const ch = DATA.channels.find((c) => c.key === key);
  const d = DATA.detail[key];
  const back = `<a class="back" href="#board">‹ 현황판</a>`;
  if (!ch || !d) return `${back}<h2 class="chname">${esc(nameOf(key))}</h2><div class="panel fail">—</div>`;
  const b = DATA.board[key] || {};
  const health = b.health || "grey";
  const m = d.monet || {};
  const monet = `<section class="panel"><h3>수익창출${m.monetized ? `<span class="tag t-red">수익창출 중</span>` : ""}</h3>
    ${progress("구독자", m.subs, m.subs_pct, "1,000", "명", health)}
    ${progress("시청시간", m.hours, m.hours_pct, "4,000", "시간", health)}</section>`;
  const aud = d.audience || { subscribers: {}, viewers: {} };
  const ss = d.subs_sources || {};
  const src = SRC.map(([k, label]) => ({ label, value: ss[k], text: isNull(ss[k]) ? "—" : signed(ss[k]), color: "red" }))
    .concat([{ label: "이탈", value: isNull(ss.lost) ? null : -ss.lost, text: isNull(ss.lost) ? "—" : "−" + fmt(ss.lost), color: "blue" }]);
  const genres = (d.genres || []).slice(0, 5).map((g) => ({ label: g.name, value: g.hours, text: `≈ ${fmt(g.hours, 1)}시간 · ${fmt(g.share, 0)}%` }));
  return `${back}<h2 class="chname">${esc(ch.display)}</h2><div class="stack">
    ${monet}
    ${audienceBlock("구독자 현황", aud.subscribers || {})}
    ${audienceBlock("시청자 현황", aud.viewers || {})}
    ${videoList("롱폼 상위 3", d.top_long)}
    ${videoList("라이브 상위 3", d.top_live)}
    <section class="panel"><h3>구독 유입<span class="asof">${fmt(ss.days || 28)}일</span></h3>${hbars(src)}</section>
    <section class="panel"><h3>음악 장르<span class="asof">28일 · 재생목록</span></h3>${hbars(genres, "purple")}</section>
  </div>`;
}

// ---------- bands and errors ----------
function renderBands() {
  if (sampleMode) return `<div class="sample-band">예시 데이터예요. 실제 숫자가 아니에요.</div>`;
  // Keyed to the last successful daily collection: live runs re-render every 2 hours, so generated_at is always fresh.
  if (DATA.last_daily_ok_at === null) return `<div class="stale-band">최근 일일 핵심 수집 성공 기록이 없어요. 꼬비에게 알려 주세요.</div>`;
  const stale = staleDays(DATA.last_daily_ok_at ?? DATA.generated_at, Date.now());
  return stale ? `<div class="stale-band">일일 핵심 수집이 ${stale}일째 성공하지 못했어요. 꼬비에게 알려 주세요.</div>` : "";
}

function renderErrors() {
  if (!DATA.errors || !DATA.errors.length) return "";
  const items = DATA.errors.map((e) => `<li>${esc(nameOf(e.channel))} · ${esc(e.stage || "")} ${esc(e.human || e.error || "")}${e.run_started_at ? ` <span class="n">${esc(mdhm(e.run_started_at))}</span>` : ""}</li>`).join("");
  return `<section class="errs"><h3>오류</h3><ul class="errors">${items}</ul></section>`;
}

function render() {
  if (!DATA) return;
  const r = route();
  let body;
  if (r.view === "ch") body = renderChannel(r.key);
  else if (r.view === "subs") body = renderSubs();
  else if (r.view === "watch") body = renderWatch();
  else if (r.view === "api") body = renderApi();
  else body = renderBoard();
  app.innerHTML = renderBands() + `<main>${renderTop(r.view)}${body}${renderErrors()}</main>`;
  app.querySelectorAll(".seg button").forEach((btn) => btn.addEventListener("click", () => {
    const y = window.scrollY;
    watchWin = btn.dataset.win;
    store("set", WIN_KEY, watchWin);
    render();
    window.scrollTo(0, y);
  }));
  const rfBtn = document.getElementById("refresh");
  if (rfBtn && !sampleMode) rfBtn.addEventListener("click", startRefresh);
  if (r.view === "ch") window.scrollTo(0, 0);
}

// ---------- refresh now ----------
function setRefresh(text, disabled) {
  rf = { text, disabled };
  const b = document.getElementById("refresh");
  if (b) { b.textContent = text; b.disabled = disabled; }
}

function releaseRefreshAfter(ms, text) {
  clearTimeout(rfTimer);
  rfTimer = setTimeout(() => setRefresh(text || REFRESH_LABEL, false), ms);
}

async function startRefresh() {
  if (rf.disabled) return;
  setRefresh("요청 중…", true);
  let res = null, info = {};
  try {
    res = await fetch(REFRESH_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: store("get", STORE_KEY) }),
    });
    info = await res.json().catch(() => ({}));
  } catch (e) { res = null; }
  if (res && res.status === 202) {
    setRefresh("새로 읽는 중 · 2~3분 걸려요", true);
    pollForNewData();
  } else if (res && res.status === 429) {
    const secs = Math.min(Math.max(Number(info.retry_after_s) || 60, 1), 600);
    setRefresh(`방금 새로고침했어요 · ${Math.ceil(secs / 60)}분 뒤 다시`, true);
    releaseRefreshAfter(secs * 1000);
  } else if (res && res.status === 401) {
    setRefresh("비밀번호가 달라요 · 다시 로그인", true);
    store("del", STORE_KEY);
    setTimeout(() => location.reload(), 1500);
  } else {
    setRefresh("지금은 안 돼요 · 잠시 뒤 다시", true);
    releaseRefreshAfter(30000);
  }
}

// Poll data.enc until generated_at changes (workflow takes ~2-3 min), at most POLL_MAX_MS.
function pollForNewData() {
  clearInterval(rfPoll);
  const t0 = Date.now();
  rfPoll = setInterval(async () => {
    try {
      const res = await fetch("data.enc?r=" + Date.now(), { cache: "no-store" });
      if (res.ok) {
        const data = await tryDecrypt(await res.json(), store("get", STORE_KEY));
        if (data && data.generated_at !== DATA.generated_at) {
          clearInterval(rfPoll);
          DATA = data;
          render();
          setRefresh(`방금 갱신됨 ${hm(data.generated_at)}`, true);
          releaseRefreshAfter(60000);
          return;
        }
      }
    } catch (e) { /* keep polling until the deadline */ }
    if (Date.now() - t0 >= POLL_MAX_MS) {
      clearInterval(rfPoll);
      setRefresh("아직이에요 · 잠시 뒤 새로고침(F5)", false);
    }
  }, POLL_MS);
}

window.addEventListener("hashchange", render);

// ---------- password flow ----------
async function tryDecrypt(envelope, password) {
  try {
    return JSON.parse(await decryptEnvelope(envelope, password));
  } catch (e) {
    return null;
  }
}

function showForm(envelope, wrong) {
  app.innerHTML = `<form class="pwform" id="pwform">
    <h1>유튜브 상황판</h1>
    <input id="pw" type="password" autocomplete="current-password" placeholder="비밀번호" aria-label="비밀번호" autofocus>
    <div class="pwerr" id="pwerr" role="alert">${wrong ? "비밀번호가 맞지 않아요" : ""}</div>
    <button type="submit">열기</button>
  </form>`;
  document.getElementById("pwform").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const pw = document.getElementById("pw").value;
    const data = await tryDecrypt(envelope, pw);
    if (data) {
      store("set", STORE_KEY, pw);
      DATA = data;
      render();
    } else {
      store("del", STORE_KEY);
      showForm(envelope, true);
    }
  });
}

async function main() {
  const w = store("get", WIN_KEY);
  if (["365", "28", "7"].includes(w)) watchWin = w;
  let res = null;
  try { res = await fetch("data.enc", { cache: "no-store" }); } catch (e) { res = null; }
  if (res && res.ok) {
    let envelope;
    try { envelope = await res.json(); } catch (e) { app.textContent = "데이터 파일을 읽을 수 없어요."; return; }
    const saved = store("get", STORE_KEY);
    if (saved) {
      const data = await tryDecrypt(envelope, saved);
      if (data) { DATA = data; render(); return; }
      store("del", STORE_KEY);
    }
    showForm(envelope, false);
    return;
  }
  try {
    const s = await fetch("sample.json", { cache: "no-store" });
    DATA = await s.json();
    sampleMode = true;
    render();
  } catch (e) {
    app.textContent = "보여줄 데이터가 없어요.";
  }
}

main();
