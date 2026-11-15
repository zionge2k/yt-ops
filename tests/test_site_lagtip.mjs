// The "why is this not today's number" note: the card labels the 365-day / 48-hour cells with the KST time the data
// ends, and a tooltip explains the lag after 3 s of hovering. app.js is a browser script, so it is evaluated in a vm
// sandbox with a stub DOM. Run: node --test tests/test_site_lagtip.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const SAMPLE = JSON.parse(read("../site/sample.json"));
const WINTER = "2026-11-13T08:00:00+00:00";  // KST 11/13 17:00
const SUMMER = "2026-07-02T07:00:00Z";  // KST 7/2 16:00

// Timers are held by the test: tick(ms) runs what is due, clearTimeout drops one.
function clock() {
  let now = 0, id = 0;
  const timers = new Map();
  return {
    setTimeout: (fn, ms) => { timers.set(++id, { fn, at: now + ms }); return id; },
    clearTimeout: (i) => { timers.delete(i); },
    tick(ms) {
      now += ms;
      for (const [i, t] of [...timers]) if (t.at <= now) { timers.delete(i); t.fn(); }
    },
  };
}

// A cell stand-in: remembers listeners, and a tooltip inserted into it can be found and removed again.
function fakeEl(until = WINTER) {
  const listeners = {};
  const el = {
    dataset: { tip: "lag", until }, tipHtml: null, tip: null, closeBtn: null,
    addEventListener(type, fn) { listeners[type] = fn; },
    fire(type) { if (listeners[type]) listeners[type](); },
    insertAdjacentHTML(_where, html) {
      el.tipHtml = html;
      const closeListeners = {};
      el.closeBtn = { addEventListener(type, fn) { closeListeners[type] = fn; }, click() { closeListeners.click(); } };
      el.tip = { remove() { el.tip = null; el.tipHtml = null; } };
    },
    querySelector(sel) { return sel === ".tip" ? el.tip : sel === ".tip-x" ? el.closeBtn : null; },
    get visible() { return el.tip !== null; },
  };
  return el;
}

function sandbox(app = {}, clk = clock()) {
  const ctx = vm.createContext({
    document: { getElementById: () => app },
    window: { addEventListener() {}, scrollTo() {} },
    location: { hash: "" },
    fetch: () => Promise.reject(new Error("no network in tests")),
    console, Intl, Date, setTimeout: clk.setTimeout, clearTimeout: clk.clearTimeout, setInterval, clearInterval,
  });
  vm.runInContext(read("../site/app.js"), ctx, { filename: "app.js" });
  const run = (expr, vars = {}) => { Object.assign(ctx, vars); return vm.runInContext(expr, ctx); };
  return { run, clk };
}

const clone = () => structuredClone(SAMPLE);
const withUntil = (until, latestUntil) => {
  const d = clone();
  for (const k of ["soombi", "a2p"]) d.board[k].as_of = { subs: "2026-11-04", hours: "2026-11-04", h48: "2026-11-04", ...(until ? { until } : {}) };
  if (latestUntil) d.latest_until = latestUntil;
  return d;
};
const board = (data) => { const s = sandbox(); return s.run("DATA = __d; renderBoard()", { __d: data }); };
const top = (data) => { const s = sandbox(); return s.run("DATA = __d; renderTop('board')", { __d: data }); };
const card = (html, display) => html.split("<article").find((a) => a.includes(`<h2>${display}</h2>`));
const cellOf = (html, label) => html.split('<div class="cell"').find((c) => c.includes(`<span class="k">${label}`));

test("with an end time, the hours and 48-hour cells show it in KST and carry the tooltip hooks", () => {
  const html = card(board(withUntil(WINTER)), "숨비찰나");
  for (const label of ["시간", "48시간"]) {
    const c = cellOf(html, label);
    assert.match(c, /<span class="asof n">11\/13 17시까지<\/span>/);
    assert.match(c, /data-tip="lag"/);
    assert.ok(c.includes('data-until="2026-11-13T08:00:00+00:00"'));
  }
});

test("a daylight-time end time reads 16시", () => {
  const html = card(board(withUntil(SUMMER)), "숨비찰나");
  assert.match(cellOf(html, "시간"), /7\/2 16시까지/);
});

test("without an end time the old label stays and nothing gets a tooltip", () => {
  const html = card(board(withUntil(null)), "숨비찰나");
  assert.ok(!html.includes("data-tip") && !html.includes("시까지"));
  assert.match(cellOf(html, "시간"), /<span class="asof n">11\/4<\/span>/);  // old asOf(a.hours, ""): day differs from the base day
});

test("a collect-failed card and the other cells never get the tooltip", () => {
  const data = withUntil(WINTER);
  assert.ok(!card(board(data), "groove.wav").includes("data-tip"));
  const html = card(board(data), "숨비찰나");
  assert.equal(html.split("data-tip").length - 1, 2);
  for (const label of ["구독자", "노출률", "클릭률", "예약현황"]) assert.ok(!cellOf(html, label).includes("data-tip"), label);
});

test("the header says the confirmed analytics end in KST when latest_until is there, else the old day", () => {
  assert.match(top(withUntil(WINTER, WINTER)), /분석 확정 11\/13 17시까지/);
  assert.match(top(withUntil(WINTER, SUMMER)), /분석 확정 7\/2 16시까지/);
  assert.match(top(withUntil(WINTER)), /분석 확정 11\/4까지/);
});

test("lagTip: title, the four lines with the value, a close button", () => {
  const html = sandbox().run(`lagTip("${WINTER}")`);
  assert.match(html, /^<div class="tip" role="tooltip">/);
  assert.ok(html.includes("왜 오늘 숫자가 아닌가요?"));
  assert.equal(html.split("<li>").length - 1, 4);
  for (const line of ["시청시간은 유튜브가 이틀쯤 늦게 알려 줘요.", "매일 아침 하루치가 새로 나와요.",
    "지금 숫자는 11/13 17시까지 본 시간이에요.", "구독자와 라이브는 늦지 않아요."]) assert.ok(html.includes(line), line);
  assert.match(html, /<button type="button" class="tip-x" aria-label="닫기">×<\/button>/);
});

test("the tooltip appears after 3 s of hovering and not before", () => {
  const { run, clk } = sandbox();
  const el = fakeEl();
  run("bindLagTip(el)", { el });
  el.fire("mouseenter");
  clk.tick(2999);
  assert.ok(!el.visible);
  clk.tick(1);
  assert.ok(el.visible && el.tipHtml.includes("11/13 17시까지"));
});

test("leaving before 3 s cancels it", () => {
  const { run, clk } = sandbox();
  const el = fakeEl();
  run("bindLagTip(el)", { el });
  el.fire("mouseenter");
  clk.tick(2000);
  el.fire("mouseleave");
  clk.tick(5000);
  assert.ok(!el.visible);
});

test("leaving hides it, and hovering again for 3 s shows it again", () => {
  const { run, clk } = sandbox();
  const el = fakeEl();
  run("bindLagTip(el)", { el });
  el.fire("mouseenter"); clk.tick(3000);
  assert.ok(el.visible);
  el.fire("mouseleave");
  assert.ok(!el.visible);
  el.fire("mouseenter"); clk.tick(2000);
  assert.ok(!el.visible);
  clk.tick(1000);
  assert.ok(el.visible);
});

test("the close button hides it for good: no cell shows it again, until the page is reloaded", () => {
  const { run, clk } = sandbox();
  const a = fakeEl(), b = fakeEl();
  run("bindLagTip(a); bindLagTip(b)", { a, b });
  a.fire("mouseenter"); clk.tick(3000);
  a.closeBtn.click();
  assert.ok(!a.visible);
  a.fire("mouseleave");
  a.fire("mouseenter"); clk.tick(10000);
  b.fire("mouseenter"); clk.tick(10000);
  assert.ok(!a.visible && !b.visible);
  // a new sandbox is a fresh page load
  const fresh = sandbox();
  const c = fakeEl();
  fresh.run("bindLagTip(c)", { c });
  c.fire("mouseenter"); fresh.clk.tick(3000);
  assert.ok(c.visible);
});

test("render() binds the tooltip on the cells it just drew, and a dismissal survives the next render()", () => {
  const cells = [];
  const app = {
    set innerHTML(html) {
      this._html = html;
      cells.length = 0;
      const n = (html.match(/data-tip="lag"/g) || []).length;
      for (let i = 0; i < n; i++) cells.push(fakeEl());
    },
    get innerHTML() { return this._html; },
    querySelectorAll: (sel) => (sel === '[data-tip="lag"]' ? [...cells] : []),
  };
  const { run, clk } = sandbox(app);
  run("DATA = __d; sampleMode = true; render()", { __d: withUntil(WINTER, WINTER) });
  assert.equal(cells.length, 4);  // two cards x (hours, 48-hour)
  cells[0].fire("mouseenter"); clk.tick(3000);
  assert.ok(cells[0].visible);
  cells[0].closeBtn.click();
  run("render()");  // a hash change redraws the page
  cells[1].fire("mouseenter"); clk.tick(10000);
  assert.ok(!cells[1].visible);
});
