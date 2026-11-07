// yt-ops dashboard: static page, renders data.json (from data.enc, or sample.json in dev).
"use strict";

const STORE_KEY = "ytops_pw";
const app = document.getElementById("app");
let DATA = null;
let period = "7";
let sampleMode = false;

// ---------- helpers ----------
const isNull = (v) => v === null || v === undefined;
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (v, d = 0) => isNull(v) ? "—" : Number(v).toLocaleString("ko-KR", { maximumFractionDigits: d });
const kst = (iso) => {
  const o = {};
  new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })
    .formatToParts(new Date(iso)).forEach((p) => { o[p.type] = p.value; });
  return o;
};
const mdhm = (iso) => { const p = kst(iso); return `${p.month}/${p.day} ${p.hour}:${p.minute}`; };
const ymd = (d) => { const [, m, dd] = d.split("-"); return `${+m}/${+dd}`; };
// weekday of a YYYY-MM-DD calendar date, independent of the viewer's timezone
const wday = (d) => "일월화수목금토"[new Date(Date.UTC(...d.split("-").map((x, i) => (i === 1 ? x - 1 : +x)))).getUTCDay()];
const addDays = (d, n) => { const t = new Date(d + "T00:00:00Z"); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); };

// Korean particle: 이/가, 과/와 depending on final consonant
const jong = (w) => { const c = w.charCodeAt(w.length - 1); return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 !== 0; };
const iga = (w) => w + (jong(w) ? "이" : "가");
const gwa = (w) => w + (jong(w) ? "과" : "와");

const METRIC = { watch_hours: "시청시간", views: "조회수", subs_net: "순증" };
const STATUS = {
  red: { word: "떨어짐", order: 0 },
  yellow: { word: "흔들림", order: 1 },
  green: { word: "오름", order: 2 },
  grey: { word: "확인 불가", order: 3 },
};

function pctText(m) {
  if (isNull(m.pct)) return "";
  if (m.pct === 0) return "그대로";
  return `${m.pct > 0 ? "+" : "−"}${fmt(Math.abs(m.pct), Math.abs(m.pct) < 10 ? 1 : 0)}%`;
}

// provisional rule for one channel's status (see header comment)
function channelStatus(ch, m) {
  if (ch.collect_failed) return "grey";
  const st = Object.keys(METRIC).map((k) => m[k].status);
  const reds = st.filter((s) => s === "red").length;
  const yellows = st.filter((s) => s === "yellow").length;
  if (reds >= 2) return "red";
  if (reds === 1 || yellows >= 2) return "yellow";
  return "green";
}

function reason(m, status) {
  if (status === "grey") return "숫자를 못 가져왔어요";
  const order = ["watch_hours", "views", "subs_net"];
  const bad = order.filter((k) => m[k].status === "red").map((k) => METRIC[k]);
  if (bad.length) {
    const subj = bad.length === 1 ? iga(bad[0]) : bad.slice(0, -1).map(gwa).join(" ") + " " + iga(bad[bad.length - 1]);
    return `${subj} 줄었어요`;
  }
  const up = order.filter((k) => m[k].status === "green").map((k) => METRIC[k]);
  if (status === "green") return up.length ? `${iga(up[0])} 늘었어요` : "고르게 좋아요";
  return "조금 줄거나 그대로예요";
}

const subsOf = (ch) => !ch.subscribers ? null : (isNull(ch.subscribers.exact) ? ch.subscribers.api : ch.subscribers.exact);

function rows() {
  const per = DATA.periods[period];
  return DATA.channels.map((ch) => {
    const m = per.channels[ch.key];
    const status = channelStatus(ch, m);
    const reds = Object.keys(METRIC).filter((k) => m[k].status === "red").length;
    return { ch, m, status, reds, why: reason(m, status) };
  }).sort((a, b) => STATUS[a.status].order - STATUS[b.status].order
    || b.reds - a.reds
    || (a.m.watch_hours.pct ?? 0) - (b.m.watch_hours.pct ?? 0));
}

// ---------- top ----------
function renderTop(rs) {
  const gen = kst(DATA.generated_at);
  const per = DATA.periods[period];
  const line = (s, tail) => {
    const list = rs.filter((r) => r.status === s);
    if (!list.length) return "";
    return `<p><span class="pill s-${s}">${STATUS[s].word} ${list.length}곳</span><span>${list.map((r) => `<b>${esc(r.ch.display)}</b>`).join(", ")}${tail ? ` <span style="color:var(--ink-2)">${tail}</span>` : ""}</span></p>`;
  };
  const btns = ["7", "28", "90"].map((p) => `<button type="button" data-period="${p}" aria-pressed="${p === period}">${p}일</button>`).join("");
  return `<div class="top">
      <div><h1>${gen.month}월 ${gen.day}일 채널 상황</h1>
        <p class="when">${gen.hour}:${gen.minute}에 만든 화면이에요. 지난 ${period}일을 ${period === "7" ? "그 전 4주 평균" : `그 전 ${period}일`}과 비교했어요.</p></div>
      <div class="period"><div class="seg" role="group" aria-label="기간">${btns}</div>
        <span class="range"><b class="n">${ymd(per.start)}~${ymd(per.end)}</b> 숫자예요. 유튜브 집계는 ${DATA.lag_days}일 늦게 들어와요.</span></div>
    </div>
    <div class="verdict">${line("red")}${line("yellow")}${line("green")}${line("grey", "연결을 다시 해야 해요")}</div>
    <p class="provisional">상태 기준은 아직 임시예요.</p>`;
}

// ---------- cards ----------
function bars(values, start) {
  const W = 300, H = 30, n = values.length;
  const nums = values.filter((v) => !isNull(v));
  if (!nums.length) return "";
  const max = Math.max(...nums) || 1;
  const gap = n > 30 ? 0.6 : n > 10 ? 2 : 5;
  const bw = (W - gap * (n - 1)) / n;
  const rects = values.map((v, i) => {
    const x = (i * (bw + gap)).toFixed(2);
    const day = ymd(addDays(start, i));
    if (isNull(v)) return `<rect x="${x}" y="${H - 2}" width="${bw.toFixed(2)}" height="2" style="fill:var(--rule)"><title>${day} 숫자 없음</title></rect>`;
    const h = Math.max(2, (v / max) * (H - 2));
    return `<rect x="${x}" y="${(H - h).toFixed(2)}" width="${bw.toFixed(2)}" height="${h.toFixed(2)}" rx="${n > 30 ? 0 : 1.5}"><title>${day} ${fmt(v)}시간</title></rect>`;
  }).join("");
  return `<svg class="bars" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="하루별 시청시간">${rects}</svg>`;
}

function changeSentence(m) {
  if (isNull(m.pct)) return "";
  if (m.pct === 0) return "그대로";
  return `${fmt(Math.abs(m.pct), Math.abs(m.pct) < 10 ? 1 : 0)}% ${m.pct > 0 ? "늘었어요" : "줄었어요"}`;
}

function mini(k, m, signed) {
  if (isNull(m.cur)) return `<div><span class="k">${k}</span><span class="val">—</span></div>`;
  const v = signed && m.cur > 0 ? `+${fmt(m.cur)}` : fmt(m.cur);
  return `<div><span class="k">${k}</span><span class="val n">${v}</span><span class="dd n t-${m.status}">${pctText(m)}</span></div>`;
}

function renderCards(rs) {
  const per = DATA.periods[period];
  return `<div class="cards">${rs.map((r) => {
    const { ch, m } = r;
    const band = `<div class="band"><span>${STATUS[r.status].word}</span><span class="reason" title="${esc(r.why)}">${esc(r.why)}</span></div>`;
    if (ch.collect_failed) {
      const e = ch.errors[0];
      return `<article class="card s-grey" id="ch-${esc(ch.key)}">${band}<div class="body"><h3>${esc(ch.display)}</h3>
        <p>${e ? esc(e.message) + ". " : ""}꼬비에게 다시 연결해 달라고 해 주세요.</p></div></article>`;
    }
    const w = m.watch_hours;
    return `<article class="card s-${r.status}" id="ch-${esc(ch.key)}">${band}<div class="body">
      <div class="namerow"><h3 title="${esc(ch.display)}">${esc(ch.display)}</h3><span class="lbl">${period}일 시청시간</span></div>
      <div class="big"><span class="num n">${fmt(w.cur)}</span><span class="unit">시간</span><span class="chg t-${w.status}">${changeSentence(w)}</span></div>
      ${bars(w.spark, per.start)}
      <div class="mini">
        <div><span class="k">구독자</span><span class="val n">${fmt(subsOf(ch))}</span><span class="dd" style="color:var(--ink-3)">지금</span></div>
        ${mini("순증", m.subs_net, true)}
        ${mini("조회수", m.views)}
      </div>
    </div></article>`;
  }).join("")}</div>`;
}

// ---------- lower sections ----------
function goal(label, have, pct, target, extra, approx) {
  if (isNull(have)) return `<div class="goal"><div class="line"><span>${label}</span><span>—</span></div></div>`;
  const p = Math.min(100, pct || 0);
  return `<div class="goal"><div class="line"><span>${label}</span><span><b class="n">${approx ? "약 " : ""}${fmt(have)}</b> / ${target}</span></div>
    <div class="track" role="progressbar" aria-label="${label}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${p}"><i style="width:${p}%"></i></div>
    ${extra ? `<div class="extra">${extra}</div>` : ""}</div>`;
}

function renderMoney(rs) {
  const list = rs.filter((r) => !r.ch.collect_failed).map((r) => ({ ch: r.ch, mo: DATA.monetization[r.ch.key] }))
    .sort((a, b) => ((b.mo.subs_pct || 0) + (b.mo.hours_pct || 0)) - ((a.mo.subs_pct || 0) + (a.mo.hours_pct || 0)));
  const items = list.map(({ ch, mo }) => {
    const done = mo.subs_pct >= 100 && mo.hours_pct >= 100;
    const subLeft = mo.subs_pct >= 100 ? "" : `${fmt(1000 - mo.subs_exact)}명 남음`;
    const hrsExtra = mo.official ? `공식 숫자는 ${fmt(mo.official.value)}시간 (${ymd(mo.official.as_of)} 기준)`
      : mo.hours_pct >= 100 ? "" : `약 ${fmt(4000 - mo.hours_approx)}시간 남음`;
    return `<div class="panel mrow"><h3>${esc(ch.display)}${done ? '<span class="done">두 조건 다 채움</span>' : ""}</h3>
      ${goal("구독자", mo.subs_exact, mo.subs_pct, "1,000명", subLeft)}
      ${goal("시청시간", mo.hours_approx, mo.hours_pct, "4,000시간", hrsExtra, true)}</div>`;
  }).join("");
  return `<section><h2>수익창출까지</h2>
    <p class="sub">구독자 1,000명과 1년 시청시간 4,000시간을 둘 다 채워야 해요. 시청시간은 어림값이에요.</p>
    <div class="money">${items}</div></section>`;
}

const HEALTH = { good: ["green", "송출 좋음"], ok: ["yellow", "송출 보통"], bad: ["red", "송출 나쁨"] };
function renderLive() {
  const byKey = Object.fromEntries(DATA.channels.map((c) => [c.key, c]));
  const items = Object.entries(DATA.live).map(([k, l]) => {
    const total = (l.hours_live || 0) + (l.hours_ondemand || 0);
    const lp = total ? (l.hours_live / total) * 100 : 0;
    const s = l.last_snapshot;
    let now = `<div class="now"><span class="ttl">기록 없음</span></div>`;
    if (s) {
      const h = HEALTH[s.health];
      const on = s.life_cycle === "live";
      now = `<div class="now"><span class="onair">${on ? "방송 중" : "방송 끝남"}</span>
        ${on && !isNull(s.concurrent) ? `<span class="n">${fmt(s.concurrent)}명 보는 중</span>` : ""}
        ${h ? `<span class="pill s-${h[0]}">${h[1]}</span>` : ""}</div>
        <div class="ttl">${esc(s.title || "")}, ${mdhm(s.taken_at)}에 본 모습</div>`;
    }
    return `<div class="panel live"><h3>${esc(byKey[k] ? byKey[k].display : k)}</h3>${now}
      <div class="split" role="img" aria-label="라이브 ${fmt(l.hours_live, 1)}시간, 다시보기 ${fmt(l.hours_ondemand, 1)}시간"><i class="l" style="width:${lp}%"></i><i class="o" style="width:${total ? 100 - lp : 0}%"></i></div>
      <div class="hrs">지난 7일 중 <b class="n">${fmt(l.days_with_live)}일</b> 켰어요. 라이브 <b class="n">${fmt(l.hours_live, 1)}</b>시간, 다시보기 <b class="n">${fmt(l.hours_ondemand, 1)}</b>시간</div>
    </div>`;
  }).join("");
  return `<section><h2>라이브</h2>
    <p class="sub">실시간이 아니라 마지막으로 들여다본 모습이에요. 지금 상태는 꼬비에게 물어봐 주세요.</p>
    <div class="lives">${items}</div></section>`;
}

function renderSchedule(rs) {
  const dates = DATA.schedule[DATA.channels[0].key].next7.map((d) => d.date);
  const head = dates.map((d) => `<th>${ymd(d)}<span class="day">${wday(d)}</span></th>`).join("");
  const body = rs.map(({ ch }) => {
    const s = DATA.schedule[ch.key];
    const cells = s.next7.map((d) => {
      const parts = [];
      if (d.long) parts.push(`<span class="chip long">영상 ${d.long}</span>`);
      if (d.shorts) parts.push(`<span class="chip sh">쇼츠 ${d.shorts}</span>`);
      return `<td>${parts.length ? `<div class="cell">${parts.join("")}</div>` : '<span class="empty">·</span>'}</td>`;
    }).join("");
    const lack = [];
    const L = s.shortage.long, S = s.shortage.shorts;
    if (L.status === "short") lack.push(`영상 ${L.need - L.have}개`);
    if (S.status === "short") lack.push(`쇼츠 ${S.need - S.have}개`);
    let need;
    if (lack.length) need = `<span class="t-red" style="font-weight:700">${lack.join(", ")} 더 필요</span>`;
    else if (L.status === "none" && S.status === "none") need = `<span class="t-grey">계획 없음</span>`;
    else need = `<span class="t-grey">충분해요</span>`;
    return { short: lack.length > 0, html: `<tr><td><b>${esc(ch.display)}</b><span class="need">${need}</span></td>${cells}</tr>` };
  }).sort((a, b) => b.short - a.short).map((x) => x.html).join("");
  return `<section><h2>앞으로 7일 예약</h2>
    <p class="sub">예약해 둔 영상과 쇼츠예요. 모자라는 채널만 빨갛게 보여요.</p>
    <div class="tablewrap"><table class="sched"><colgroup><col class="ch">${dates.map(() => "<col>").join("")}</colgroup>
      <thead><tr><th>채널</th>${head}</tr></thead><tbody>${body}</tbody></table></div>
    <div class="legend-row"><span><span class="chip long">영상</span> 긴 영상</span><span><span class="chip sh">쇼츠</span> 쇼츠</span></div>
  </section>`;
}

function renderShorts(rs) {
  const body = rs.map(({ ch }) => {
    const s = DATA.shorts[ch.key];
    return `<tr><td><b>${esc(ch.display)}</b></td><td class="n">${fmt(s.views)}</td>
      <td class="n">${isNull(s.engaged_ratio) ? "—" : fmt(s.engaged_ratio * 100, 0) + "%"}</td>
      <td class="n">${fmt(s.subs_per_1k, 1)}</td></tr>`;
  }).join("");
  return `<section><h2>쇼츠</h2>
    <p class="sub">지난 7일 쇼츠만 따로 봤어요.</p>
    <div class="tablewrap shorts-wrap"><table class="shorts"><colgroup><col class="ch"><col><col><col></colgroup>
      <thead><tr><th>채널</th><th>조회수</th><th>넘기지 않고 본 비율</th><th>1,000회당 구독</th></tr></thead><tbody>${body}</tbody></table></div>
  </section>`;
}

function renderFoot() {
  return `<div class="foot">
    <p>구독자는 지금 숫자예요. 조회수, 순증, 시청시간은 유튜브가 모아서 주는 숫자라 ${DATA.lag_days}일 늦게 들어와요(${ymd(DATA.latest_day)}까지).</p>
    <p>쇼츠의 비율과 1,000회당 구독은 꼬비가 계산한 값이고, 수익창출 시청시간은 어림값이라 앞에 "약"을 붙였어요. 막대에 마우스를 올리면 그날 숫자가 보여요.</p>
  </div>`;
}

// ---------- bands and errors ----------
const STALE_HOURS = 48;
/** Whole days since generated_at when older than 48 hours, else 0 (fresh or unparsable). */
function staleDays(generatedAtIso, nowMs) {
  const t = Date.parse(generatedAtIso);
  if (Number.isNaN(t)) return 0;
  const hours = (nowMs - t) / 3600000;
  return hours > STALE_HOURS ? Math.floor(hours / 24) : 0;
}

function renderBands() {
  if (sampleMode) return `<div class="sample-band">예시 데이터예요. 실제 숫자가 아니에요.</div>`;
  const stale = staleDays(DATA.generated_at, Date.now());
  return stale ? `<div class="stale-band">상황판이 ${stale}일째 갱신되지 않았어요. 꼬비에게 알려 주세요.</div>` : "";
}

function renderErrors() {
  if (!DATA.errors || !DATA.errors.length) return "";
  const names = Object.fromEntries(DATA.channels.map((c) => [c.key, c.display]));
  const items = DATA.errors.map((e) => `<li>${esc(names[e.channel] || e.channel)}: ${esc(e.stage)} ${esc(e.error)}${e.run_started_at ? ` (${esc(mdhm(e.run_started_at))})` : ""}</li>`).join("");
  return `<section><h2>숫자를 못 가져온 곳</h2><ul class="errors">${items}</ul></section>`;
}

function render() {
  const rs = rows();
  app.innerHTML = renderBands() + "<main>" + renderTop(rs) + renderCards(rs) + renderMoney(rs) + renderLive() + renderSchedule(rs) + renderShorts(rs) + renderErrors() + renderFoot() + "</main>";
  app.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => {
    const y = window.scrollY;
    period = b.dataset.period;
    render();
    window.scrollTo(0, y);
  }));
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
      render();
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
      if (data) { DATA = data; render(); return; }
      store("del");
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
