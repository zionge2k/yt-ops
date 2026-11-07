// yt-ops dashboard: static page, renders data.json (from data.enc, or sample.json in dev).
"use strict";

const STORE_KEY = "ytops_pw";
const DOT = { green: "🟢", yellow: "🟡", red: "🔴", grey: "⚪" };
const HEALTH = { good: "🟢 좋음", ok: "🟡 보통", bad: "🔴 나쁨", none: "⚪ 정보 없음" };
const app = document.getElementById("app");

let DATA = null;
let period = "7";
let sampleMode = false;

// ---------- helpers ----------
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
const isNull = (v) => v === null || v === undefined;
function fmt(v, digits) {
  if (isNull(v)) return "—";
  return Number(v).toLocaleString("ko-KR", { maximumFractionDigits: digits === undefined ? 0 : digits });
}
const kstParts = (iso) => {
  const parts = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const o = {};
  parts.forEach((p) => { o[p.type] = p.value; });
  return o;
};
function kstShort(iso) {
  if (!iso) return "—";
  const p = kstParts(iso);
  return `${p.month}/${p.day} ${p.hour}:${p.minute}`;
}
function kstFull(iso) {
  const p = kstParts(iso);
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`;
}
function kstMdHm(iso) {
  const p = kstParts(iso);
  return `${p.month}/${p.day} ${p.hour}:${p.minute}`;
}
const mmdd = (d) => d.slice(5).replace("-", "/");

function sparkline(values) {
  const W = 120, H = 32, pad = 3;
  const nums = values.filter((v) => !isNull(v));
  if (!nums.length) return `<svg class="spark" viewBox="0 0 ${W} ${H}" aria-hidden="true"></svg>`;
  const min = Math.min(...nums), max = Math.max(...nums), span = max - min || 1;
  const n = values.length;
  const x = (i) => (n === 1 ? W / 2 : pad + (i * (W - 2 * pad)) / (n - 1));
  const y = (v) => H - pad - ((v - min) / span) * (H - 2 * pad);
  let d = "", pen = false, dots = "";
  values.forEach((v, i) => {
    if (isNull(v)) { pen = false; return; }
    d += `${pen ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)} `;
    pen = true;
    const prevNull = i === 0 || isNull(values[i - 1]);
    const nextNull = i === n - 1 || isNull(values[i + 1]);
    if (prevNull && nextNull) dots += `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="2"/>`;
  });
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" aria-hidden="true"><path d="${d}"/>${dots}</svg>`;
}

function delta(pct) {
  if (isNull(pct)) return `<span class="delta muted">—</span>`;
  if (pct > 0) return `<span class="delta up">▲ ${fmt(pct, 1)}%</span>`;
  if (pct < 0) return `<span class="delta down">▼ ${fmt(Math.abs(pct), 1)}%</span>`;
  return `<span class="delta muted">변동 없음</span>`;
}

function metricRow(label, icon, valueText, m, unit) {
  return `<div class="metric">
    <div class="label">${esc(label)} ${icon}</div>
    <div><span class="num">${esc(valueText)}</span>${unit ? ` <span class="muted">${esc(unit)}</span>` : ""} ${m ? delta(m.pct) : ""}</div>
    ${m ? sparkline(m.spark) : "<span></span>"}
  </div>`;
}

// ---------- sections ----------
function renderTop() {
  const lag = isNull(DATA.lag_days) ? "—" : DATA.lag_days;
  return `${sampleMode ? '<div class="sample-band">예시 데이터 (data.enc 없음)</div>' : ""}
  <div class="topbar">
    <div>집계 기준일 ${esc(DATA.latest_day || "—")} (${esc(lag)}일 지연) · 화면 생성 ${esc(kstFull(DATA.generated_at))}</div>
    <div class="legend">🔵실측 ⏳집계 ➗계산 ≈근사</div>
  </div>`;
}

function renderScorecards() {
  const per = DATA.periods[period];
  const cards = DATA.channels.map((ch) => {
    // a failed collection hides the comparison (▲▼%) and greys the card
    const failed = ch.collect_failed === true;
    const raw = per.channels[ch.key];
    const m = failed
      ? Object.fromEntries(Object.entries(raw).map(([k, v]) => [k, { ...v, pct: null, status: "grey" }]))
      : raw;
    const fromExact = ch.subscribers && !isNull(ch.subscribers.exact);
    const sub = ch.subscribers ? (fromExact ? ch.subscribers.exact : ch.subscribers.api) : null;
    return `<div class="card">
      <h3>${DOT[m.views.status] || "⚪"} ${esc(ch.display)}</h3>
      ${failed ? '<div class="note">수집 실패 — 로그 확인</div>' : ""}
      ${metricRow("구독자", fromExact ? "➗" : "🔵", fmt(sub), null)}
      ${metricRow("기간 순증", "⏳", fmt(m.subs_net.cur), m.subs_net)}
      ${metricRow("조회수", "⏳", fmt(m.views.cur), m.views)}
      ${metricRow("쇼츠 제외 시청시간", "⏳", fmt(m.watch_hours.cur, 1), m.watch_hours, "시간")}
    </div>`;
  }).join("");
  const toggles = ["7", "28", "90"].map((p) =>
    `<button type="button" data-period="${p}" aria-pressed="${p === period}">${p}일</button>`).join("");
  return `<h2 id="sec1">① 채널 성적표 <span class="toggle">${toggles}</span></h2>
    <div class="cards">${cards}</div>`;
}

function renderLive() {
  const byKey = Object.fromEntries(DATA.channels.map((c) => [c.key, c]));
  const cards = Object.entries(DATA.live).map(([k, l]) => {
    const total = (l.hours_live || 0) + (l.hours_ondemand || 0);
    const livePct = total ? (l.hours_live / total) * 100 : 0;
    const s = l.last_snapshot;
    const snap = s
      ? `<div>상태 ${esc(s.life_cycle || "—")} · 동시접속 <span class="num">${fmt(s.concurrent)}</span> · ${HEALTH[s.health] || HEALTH.none}</div>
         <div class="muted">${esc(kstShort(s.taken_at))} 기준 · ${esc(s.title || "")}</div>`
      : `<div class="muted">스냅샷 없음</div>`;
    return `<div class="card">
      <h3>${esc(byKey[k] ? byKey[k].display : k)}</h3>
      <div>라이브 있던 날 <span class="num">${fmt(l.days_with_live)}</span> / 7</div>
      <div class="seg" role="img" aria-label="LIVE ${fmt(l.hours_live, 1)}시간, 다시보기 ${fmt(l.hours_ondemand, 1)}시간">
        <div class="live" style="width:${livePct}%"></div><div class="vod" style="width:${total ? 100 - livePct : 0}%"></div></div>
      <div class="muted">LIVE ${fmt(l.hours_live, 1)}시간 · 다시보기 ${fmt(l.hours_ondemand, 1)}시간</div>
      ${snap}
      <div class="note">실시간 아님 — 꼬비에게 '지금 라이브' 물어보기</div>
    </div>`;
  }).join("");
  return `<h2 id="sec2">② 라이브</h2><div class="cards">${cards}</div>`;
}

function shortageCell(sh, label) {
  if (sh.status === "ok") return `<span class="ok">🟢 충족</span>`;
  if (sh.status === "short") return `<span class="short">🔴 ${label} ${fmt(sh.need - sh.have)}개 부족</span>`;
  return `<span class="muted">계획 없음</span>`;
}

function renderSchedule() {
  const rows = DATA.channels.map((ch) => {
    const s = DATA.schedule[ch.key];
    const lack = [];
    if (s.shortage.long.status === "short") lack.push(shortageCell(s.shortage.long, "롱폼"));
    if (s.shortage.shorts.status === "short") lack.push(shortageCell(s.shortage.shorts, "쇼츠"));
    const both = [s.shortage.long.status, s.shortage.shorts.status];
    const verdict = lack.length ? lack.join("<br>")
      : both.every((x) => x === "none") ? shortageCell({ status: "none" }) : shortageCell({ status: "ok" });
    return `<tr><td>${esc(ch.display)}</td><td class="c">${fmt(s.long)}</td><td>${esc(kstShort(s.next_long))}</td>
      <td class="c">${fmt(s.shorts)}</td><td>${esc(kstShort(s.next_shorts))}</td><td>${verdict}</td></tr>`;
  }).join("");
  const dates = DATA.schedule[DATA.channels[0].key].next7.map((d) => d.date);
  const head = dates.map((d) => `<th class="c">${esc(mmdd(d))}</th>`).join("");
  const grid = DATA.channels.map((ch) => {
    const cells = DATA.schedule[ch.key].next7.map((d) => {
      const parts = [];
      if (d.long) parts.push(`롱${d.long}`);
      if (d.shorts) parts.push(`쇼${d.shorts}`);
      return `<td class="c">${parts.length ? parts.join(" ") : "·"}</td>`;
    }).join("");
    return `<tr><td>${esc(ch.display)}</td>${cells}</tr>`;
  }).join("");
  return `<h2 id="sec3">③ 예약</h2>
    <div class="tablewrap"><table>
      <tr><th>채널</th><th class="c">롱폼 예약</th><th>다음 공개</th><th class="c">쇼츠 예약</th><th>다음 공개</th><th>부족</th></tr>${rows}</table></div>
    <h3 class="sub">앞으로 7일</h3>
    <div class="tablewrap"><table><tr><th>채널</th>${head}</tr>${grid}</table></div>`;
}

function progress(pct) {
  return `<div class="prog" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${isNull(pct) ? 0 : pct}"><div style="width:${isNull(pct) ? 0 : Math.min(100, pct)}%"></div></div>`;
}

function renderMonetization() {
  const rows = DATA.channels.map((ch) => {
    const m = DATA.monetization[ch.key];
    const official = m.official
      ? `<div class="muted">공식 ${fmt(m.official.value, 1)}h (${esc(m.official.as_of)} 기준)</div>` : "";
    return `<div class="mrow">
      <h3>${esc(ch.display)}</h3>
      <div>구독자 ➗ <span class="num">${fmt(m.subs_exact)}</span> / 1,000</div>${progress(m.subs_pct)}
      <div>시청시간 ≈ <span class="num">${fmt(m.hours_approx, 1)} h</span> / 4,000 h ≈</div>${progress(m.hours_pct)}
      ${official}
    </div>`;
  }).join("");
  return `<h2 id="sec4">④ 수익창출</h2><div class="cards">${rows}</div>`;
}

function renderShorts() {
  const rows = DATA.channels.map((ch) => {
    const s = DATA.shorts[ch.key];
    return `<tr><td>${esc(ch.display)}</td><td class="c">${fmt(s.views)}</td>
      <td class="c">${isNull(s.engaged_ratio) ? "—" : fmt(s.engaged_ratio * 100, 1) + "%"}</td>
      <td class="c">${fmt(s.subs_per_1k, 1)}</td></tr>`;
  }).join("");
  return `<h2 id="sec5">⑤ 쇼츠</h2>
    <div class="tablewrap"><table>
      <tr><th>채널</th><th class="c">조회수 ⏳</th><th class="c">스와이프 안 하고 본 비율 ➗</th><th class="c">1,000회당 구독 ➗</th></tr>${rows}</table></div>`;
}

function renderErrors() {
  if (!DATA.errors || !DATA.errors.length) return "";
  const items = DATA.errors.map((e) => `<li>⚪ ${esc(e.channel)}: ${esc(e.stage)} ${esc(e.error)}${e.run_started_at ? ` <span class="muted">(${esc(kstMdHm(e.run_started_at))})</span>` : ""}</li>`).join("");
  return `<div class="errors"><h3>수집 오류</h3><ul>${items}</ul></div>`;
}

function renderDashboard() {
  app.innerHTML = renderTop() + `<main><div id="sec1-wrap">${renderScorecards()}</div>${renderLive()}${renderSchedule()}${renderMonetization()}${renderShorts()}${renderErrors()}</main>`;
  bindToggle();
}

function bindToggle() {
  document.querySelectorAll(".toggle button").forEach((b) => {
    b.addEventListener("click", () => {
      period = b.dataset.period;
      document.getElementById("sec1-wrap").innerHTML = renderScorecards();
      bindToggle();
    });
  });
}

// ---------- password flow ----------
function store(op, value) {
  try {
    if (op === "get") return localStorage.getItem(STORE_KEY);
    if (op === "set") localStorage.setItem(STORE_KEY, value);
    if (op === "del") localStorage.removeItem(STORE_KEY);
  } catch (e) { /* storage may be blocked; page still works */ }
  return null;
}

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
      store("set", pw);
      DATA = data;
      renderDashboard();
    } else {
      store("del");
      showForm(envelope, true);
    }
  });
}

async function main() {
  let res = null;
  try { res = await fetch("data.enc", { cache: "no-store" }); } catch (e) { res = null; }
  if (res && res.ok) {
    let envelope;
    try { envelope = await res.json(); } catch (e) { app.textContent = "데이터 파일을 읽을 수 없어요."; return; }
    const saved = store("get");
    if (saved) {
      const data = await tryDecrypt(envelope, saved);
      if (data) { DATA = data; renderDashboard(); return; }
      store("del");
    }
    showForm(envelope, false);
    return;
  }
  try {
    const s = await fetch("sample.json", { cache: "no-store" });
    DATA = await s.json();
    sampleMode = true;
    renderDashboard();
  } catch (e) {
    app.textContent = "보여줄 데이터가 없어요.";
  }
}

main();
