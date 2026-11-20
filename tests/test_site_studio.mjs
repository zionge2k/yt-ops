// The "open all" Studio button and the #studio account-number view.
// app.js is a browser script, so it is evaluated in a vm sandbox with a stub DOM. Run: node --test tests/test_site_studio.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const SAMPLE = JSON.parse(read("../site/sample.json"));
const KEY = "ytops_studio_nums";
const ORDER = SAMPLE.order;
const ACCOUNT = { soombi: "가", backthen: "가", urachacha: "가", a2p: "가", justsoombi: "나", soombicafe: "나", groovewav: "다", pliwav: "다" };
const url = (key, n) => `https://studio.youtube.com/channel/UCsample-${key}?authuser=${n}`;
const NAMES = Object.fromEntries(SAMPLE.channels.map((c) => [c.key, c.display]));
const unesc = (s) => s.replace(/&(amp|lt|gt|quot|#39);/g, (_, e) => ({ amp: "&", lt: "<", gt: ">", quot: '"', "#39": "'" }[e]));

// The page: innerHTML is kept; the number buttons and the #studio-all button found in it can be clicked.
// opts.storage: a Map shared between sandboxes (a reload keeps it); opts.brokenStorage: every access throws;
// opts.open(i): what the i-th window.open call returns (default: a window object).
function page({ hash = "#board", storage = new Map(), brokenStorage = false, open = () => ({}) } = {}) {
  const calls = { scrollTo: [], opens: [], timers: [], opened: [] };
  let all = null;
  const picks = [];
  // attribute values are entity-decoded, as a browser does before filling dataset
  const attrs = (tag) => Object.fromEntries([...tag.matchAll(/([\w-]+)="([^"]*)"/g)].map((m) => [m[1], unesc(m[2])]));
  const app = {
    set innerHTML(html) {
      this._html = html;
      picks.length = 0;
      all = null;
      for (const m of html.matchAll(/<button\b[^>]*>/g)) {
        const a = attrs(m[0]);
        if (a["data-acct"] !== undefined) {
          const listeners = {};
          picks.push({ dataset: { acct: a["data-acct"], n: a["data-n"] }, addEventListener(t, fn) { listeners[t] = fn; }, click() { listeners.click(); } });
        }
        if (a.id === "studio-all") {
          const listeners = {};
          all = { textContent: html.slice(m.index).match(/>([^<]*)</)[1], addEventListener(t, fn) { listeners[t] = fn; }, click() { listeners.click(); } };
        }
      }
    },
    get innerHTML() { return this._html; },
    querySelectorAll: (sel) => (sel === "[data-acct]" ? [...picks] : sel === "#studio-all" && all ? [all] : []),
  };
  const localStorage = brokenStorage
    ? { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); } }
    : { getItem: (k) => (storage.has(k) ? storage.get(k) : null), setItem: (k, v) => storage.set(k, String(v)), removeItem: (k) => storage.delete(k) };
  const ctx = vm.createContext({
    document: { getElementById: (id) => (id === "studio-all" ? all : id === "app" ? app : null) },
    window: {
      addEventListener() {},
      scrollTo: (...a) => calls.scrollTo.push(a),
      scrollY: 120,
      open: (...args) => {
        calls.opens.push(args);
        // like a browser: with noopener in the features the opener gets no window back
        const w = /noopener/.test(args[2] || "") ? null : open(calls.opens.length - 1);
        if (w) calls.opened.push(w);
        return w;
      },
    },
    location: { hash },
    localStorage,
    fetch: () => Promise.reject(new Error("no network in tests")),
    // fake timers: the 15 s label reset is fired by hand
    setTimeout: (fn, ms) => { calls.timers.push({ fn, ms, live: true }); return calls.timers.length; },
    clearTimeout: (id) => { if (calls.timers[id - 1]) calls.timers[id - 1].live = false; },
    console, Intl, Date, setInterval() {}, clearInterval() {},
  });
  vm.runInContext(read("../site/app.js"), ctx, { filename: "app.js" });
  const run = (expr, vars = {}) => { Object.assign(ctx, vars); return vm.runInContext(expr, ctx); };
  const show = (data = SAMPLE) => { run("DATA = __d; sampleMode = true; render()", { __d: data }); return app.innerHTML; };
  const fire = () => { for (const t of calls.timers) if (t.live) { t.live = false; t.fn(); } };
  return {
    app, run, show, calls, fire, storage, location: ctx.location,
    html: () => app.innerHTML,
    pick: (acct, n) => picks.find((b) => b.dataset.acct === acct && b.dataset.n === String(n)).click(),
    allBtn: () => all,
  };
}

const oldData = () => {
  const d = structuredClone(SAMPLE);
  for (const c of d.channels) { delete c.channel_id; delete c.account; }
  return d;
};
const studioLinks = (html) => [...html.matchAll(/<a ([^>]*)>Studio<\/a>/g)].map((m) => Object.fromEntries([...m[1].matchAll(/([\w-]+)="([^"]*)"/g)].map((x) => [x[1], x[2]])));
const withNums = (nums) => new Map([[KEY, JSON.stringify(nums)]]);
const ALL_NUMS = { 가: 1, 나: 0, 다: 2 };
const DEFAULTS = { 가: 0, 나: 1, 다: 2 };   // nothing saved: the accounts' place in the board order

test("board cards keep their header: no Studio link on a card", () => {
  const html = page({ storage: withNums(ALL_NUMS) }).show();
  assert.equal(studioLinks(html).length, 0);
  const body = html.split("</header>")[1];
  assert.ok(!body.includes("studio.youtube.com") && !body.includes("#studio"));
  assert.ok(html.includes(`<div class="namerow"><h2>${NAMES.soombi}</h2><a class="more" href="#ch/soombi">심화 ›</a></div>`));
});

test("the channel id is URL-encoded and a channel with no account label is its own account", () => {
  const d = structuredClone(SAMPLE);
  d.channels[0].channel_id = "UC a/b";
  for (const c of d.channels) delete c.account;
  const p = page({ storage: withNums({ soombi: 3 }) });
  p.show(d);
  p.allBtn().click();
  // eight accounts: the saved one keeps its number, the others get their place in the board order
  assert.deepEqual(p.calls.opens.map((o) => o[0]), ["https://studio.youtube.com/channel/UC%20a%2Fb?authuser=3", ...ORDER.slice(1).map((key, i) => url(key, i + 1))]);
  p.location.hash = "#studio";
  p.run("render()");
  assert.equal((p.html().match(/data-acct="/g) || []).length, 8 * 10);   // eight rows, ten numbers each
});

test("data without channel_id shows no Studio controls anywhere", () => {
  const p = page();
  const board = p.show(oldData());
  assert.ok(!board.includes("Studio") && !board.includes('id="studio-all"') && !board.includes("#studio"));
  assert.equal((board.match(/심화 ›/g) || []).length, 8);   // the rest of the card is unchanged
  p.location.hash = "#studio";
  p.run("render()");
  assert.match(p.html(), /‹ 현황판/);
  assert.ok(p.html().includes('<h2 class="chname">Studio 계정 번호</h2>'));
  assert.ok(p.html().includes('<div class="panel fail">—</div>'));
  assert.ok(!p.html().includes("data-acct"));
  p.location.hash = "#api";
  p.run("render()");
  assert.ok(!p.html().includes('id="studio-all"'));
});

test("the top bar has the open-all button and the gear link next to the refresh button, also in sample mode", () => {
  const html = page().show();
  assert.match(html, /<button type="button" class="refresh" id="studio-all">Studio 전부<\/button>/);
  assert.match(html, /<a [^>]*href="#studio"[^>]*aria-label="Studio 계정 번호"[^>]*>⚙︎<\/a>/);
  assert.ok(html.indexOf('id="refresh"') < html.indexOf('id="studio-all"'));
});

test("open-all opens every Studio channel in order with the right numbers", () => {
  const p = page({ storage: withNums(ALL_NUMS) });
  p.show();
  p.allBtn().click();
  assert.deepEqual(p.calls.opens, ORDER.map((key) => [url(key, ALL_NUMS[ACCOUNT[key]]), "_blank"]));
  assert.ok(p.calls.opened.every((w) => w.opener === null));
  assert.equal(p.allBtn().textContent, "Studio 전부");
  assert.equal(p.location.hash, "#board");
});

test("open-all with nothing saved opens at once, guessing the sign-in order 0, 1, 2 for the accounts in board order", () => {
  const p = page();
  p.show();
  p.allBtn().click();
  assert.deepEqual(p.calls.opens.map((o) => o[0]), ORDER.map((key) => url(key, DEFAULTS[ACCOUNT[key]])));
  assert.equal(p.location.hash, "#board");
});

test("a saved number replaces the guess for that account only", () => {
  const p = page({ storage: withNums({ 나: 4 }) });
  p.show();
  p.allBtn().click();
  assert.deepEqual(p.calls.opens.map((o) => o[0]), ORDER.map((key) => url(key, { ...DEFAULTS, 나: 4 }[ACCOUNT[key]])));
});

test("the guess keeps an account's place even when an earlier account has no channel to open, and stops at 9", () => {
  const d = structuredClone(SAMPLE);
  for (const c of d.channels) if (ACCOUNT[c.key] === "가") delete c.channel_id;
  const p = page();
  p.show(d);
  p.allBtn().click();
  assert.deepEqual(p.calls.opens.map((o) => o[0]), ORDER.filter((k) => ACCOUNT[k] !== "가").map((key) => url(key, DEFAULTS[ACCOUNT[key]])));
  const many = structuredClone(SAMPLE);   // twelve channels, each its own account
  for (const c of many.channels) delete c.account;
  for (let i = 0; i < 4; i++) { many.order.push(`x${i}`); many.channels.push({ key: `x${i}`, display: `x${i}`, is_live: false, collect_failed: false, errors: [], channel_id: `UCx${i}` }); }
  const q = page();
  q.show(many);
  q.allBtn().click();
  assert.deepEqual(q.calls.opens.slice(8).map((o) => o[0].split("authuser=")[1]), ["8", "9", "9", "9"]);
});

test("open-all with blocked pop-ups shows how many opened, survives a re-render and resets after 15 seconds", () => {
  const p = page({ storage: withNums(ALL_NUMS), open: (i) => (i === 0 ? {} : null) });
  p.show();
  p.allBtn().click();
  assert.equal(p.calls.opens.length, 8);
  const msg = "1/8 열림 · 주소창에서 팝업 허용";
  assert.equal(p.allBtn().textContent, msg);
  p.run("render()");
  assert.ok(p.html().includes(`>${msg}</button>`));
  assert.equal(p.allBtn().textContent, msg);
  p.allBtn().click();   // a second blocked click replaces the pending reset instead of adding one
  assert.equal(p.calls.timers.filter((t) => t.live && t.ms === 15000).length, 1);
  p.fire();
  assert.equal(p.allBtn().textContent, "Studio 전부");
  p.run("render()");
  assert.equal(p.allBtn().textContent, "Studio 전부");
});

test("open-all that works after a blocked try puts the label back at once", () => {
  let blocked = true;
  const p = page({ storage: withNums(ALL_NUMS), open: (i) => (blocked && i > 0 ? null : {}) });
  p.show();
  p.allBtn().click();
  assert.equal(p.allBtn().textContent, "1/8 열림 · 주소창에서 팝업 허용");
  blocked = false;   // the person allowed pop-ups
  p.allBtn().click();
  assert.equal(p.allBtn().textContent, "Studio 전부");
  assert.ok(!p.calls.timers.some((t) => t.live));
});

test("channels without a channel_id are left out of open-all and the settings rows", () => {
  const d = structuredClone(SAMPLE);
  for (const c of d.channels) if (["backthen", "groovewav", "pliwav"].includes(c.key)) delete c.channel_id;   // 다 loses both channels
  const left = ORDER.filter((k) => !["backthen", "groovewav", "pliwav"].includes(k));
  const p = page({ storage: withNums({ 가: 1, 나: 0 }) });
  p.show(d);
  p.allBtn().click();
  assert.deepEqual(p.calls.opens.map((o) => o[0]), left.map((k) => url(k, { 가: 1, 나: 0 }[ACCOUNT[k]])));
  p.location.hash = "#studio";
  p.run("render()");
  assert.ok(!p.html().includes('data-acct="다"') && !p.html().includes(NAMES.backthen));
  assert.ok(p.html().includes([NAMES.soombi, NAMES.urachacha, NAMES.a2p].join(" · ")));
});

test("settings: names and account labels with HTML characters are escaped, and the pick saves the real label", () => {
  const d = structuredClone(SAMPLE);
  const odd = 'a<b>&"c';
  for (const c of d.channels) if (ACCOUNT[c.key] === "나") { c.account = odd; c.display = `<i>${c.key}&`; }
  const storage = new Map();
  const p = page({ hash: "#studio", storage });
  const html = p.show(d);
  assert.ok(!html.includes("<i>") && !html.includes(odd));
  assert.ok(html.includes('data-acct="a&lt;b&gt;&amp;&quot;c"') && html.includes("&lt;i&gt;justsoombi&amp; · &lt;i&gt;soombicafe&amp;"));
  p.pick(odd, 3);
  assert.deepEqual(JSON.parse(storage.get(KEY)), { [odd]: 3 });
  assert.deepEqual(p.calls.opens, [[url("justsoombi", 3), "_blank"]]);
});

test("moving to #studio goes to the top of the page; picking a number keeps the scroll position", () => {
  const p = page({ storage: withNums(ALL_NUMS) });
  p.show();
  p.calls.scrollTo.length = 0;
  p.location.hash = "#studio";
  p.run("render({ type: 'hashchange' })");   // what the hashchange listener passes
  assert.deepEqual(p.calls.scrollTo, [[0, 0]]);
  p.calls.scrollTo.length = 0;
  p.pick("가", 2);
  assert.deepEqual(p.calls.scrollTo, [[0, 120]]);
});

test("settings: one row per account in order, with ten buttons and the number in use pressed", () => {
  const p = page({ hash: "#studio", storage: withNums({ 가: 4 }) });
  const html = p.show();
  assert.ok(html.includes('<a class="back" href="#board">‹ 현황판</a>'));
  assert.ok(html.includes('<h2 class="chname">Studio 계정 번호</h2>'));
  assert.ok(html.includes("번호를 누르면 그 채널 Studio 가 새 탭으로 열려요. 대시보드가 보이면 맞는 번호예요."));
  const names = (keys) => keys.map((k) => NAMES[k]).join(" · ");
  const at = ["가", "나", "다"].map((a) => html.indexOf(names(ORDER.filter((k) => ACCOUNT[k] === a))));
  assert.ok(at.every((i) => i >= 0) && at[0] < at[1] && at[1] < at[2]);
  for (const a of ["가", "나", "다"]) for (let n = 0; n < 10; n++) {
    const pressed = n === { ...DEFAULTS, 가: 4 }[a];   // saved for 가, the guess for the others
    assert.match(html, new RegExp(`<button type="button" data-acct="${a}" data-n="${n}" aria-pressed="${pressed}">${n}</button>`));
  }
  assert.ok(!/aria-current="page"/.test(html));   // not a tab
});

test("settings: a number is saved, opens exactly one tab for the first channel of the account and shows pressed", () => {
  const storage = new Map();
  const p = page({ hash: "#studio", storage });
  p.show();
  p.calls.scrollTo.length = 0;
  p.pick("나", 7);
  assert.deepEqual(p.calls.opens, [[url("justsoombi", 7), "_blank"]]);
  assert.equal(p.calls.opened[0].opener, null);
  assert.match(p.html(), /data-acct="나" data-n="7" aria-pressed="true"/);
  assert.match(p.html(), /data-acct="나" data-n="0" aria-pressed="false"/);
  assert.deepEqual(p.calls.scrollTo, [[0, 120]]);
  assert.deepEqual(JSON.parse(storage.get(KEY)), { 나: 7 });
  const again = page({ storage });   // a reloaded page reads it back
  again.show();
  again.allBtn().click();
  assert.equal(again.calls.opens[ORDER.indexOf("soombicafe")][0], url("soombicafe", 7));
});

test("storage: broken stored values are ignored", () => {
  for (const bad of ["not json", "[1,2]", "null", '"x"', '{"가":"1"}', '{"가":10}', '{"가":-1}', '{"가":1.5}', '{"가":1,"나":"x"}']) {
    const p = page({ storage: new Map([[KEY, bad]]) });
    p.show();
    p.allBtn().click();
    assert.deepEqual(p.calls.opens.map((o) => o[0]), ORDER.map((key) => url(key, DEFAULTS[ACCOUNT[key]])), bad);
  }
});

test("storage: with localStorage throwing, a number picked in this visit still works", () => {
  const p = page({ hash: "#studio", brokenStorage: true });
  p.show();
  p.pick("가", 2);
  p.pick("나", 0);
  p.pick("다", 5);
  p.calls.opens.length = 0;
  p.location.hash = "#board";
  p.show();
  p.allBtn().click();
  assert.deepEqual(p.calls.opens.map((o) => o[0]), ORDER.map((key) => url(key, { 가: 2, 나: 0, 다: 5 }[ACCOUNT[key]])));
});
