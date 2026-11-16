// The thumbnail panel of a channel page hides the shorts behind a button. The open/closed state lives in memory only.
// app.js is a browser script, so it is evaluated in a vm sandbox with a stub DOM. Run: node --test tests/test_site_shorts.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const SAMPLE = JSON.parse(read("../site/sample.json"));
const R = SAMPLE.detail.soombi.reach;
const SHORTS_COUNT = new Set([...R.this_week_shorts, ...R.all_shorts].map((v) => v.video_id)).size;

// The page: innerHTML is kept, and the shorts button found in it can be clicked.
function page() {
  const calls = { scrollTo: [] };
  const buttons = [];
  const app = {
    set innerHTML(html) {
      this._html = html;
      buttons.length = 0;
      if (html.includes('data-toggle="shorts"')) {
        const listeners = {};
        buttons.push({ addEventListener(type, fn) { listeners[type] = fn; }, click() { listeners.click(); } });
      }
    },
    get innerHTML() { return this._html; },
    querySelectorAll: (sel) => (sel === '[data-toggle="shorts"]' ? [...buttons] : []),
  };
  const ctx = vm.createContext({
    document: { getElementById: () => app },
    window: { addEventListener() {}, scrollTo: (...a) => calls.scrollTo.push(a), scrollY: 120 },
    location: { hash: "#ch/soombi" },
    fetch: () => Promise.reject(new Error("no network in tests")),
    console, Intl, Date, setTimeout, clearTimeout, setInterval, clearInterval,
  });
  vm.runInContext(read("../site/app.js"), ctx, { filename: "app.js" });
  const run = (expr, vars = {}) => { Object.assign(ctx, vars); return vm.runInContext(expr, ctx); };
  const show = (data = SAMPLE) => { run("DATA = __d; sampleMode = true; render()", { __d: data }); return app.innerHTML; };
  return { app, run, show, calls, click: () => buttons[0].click(), location: ctx.location };
}
const tables = (html) => (html.match(/<table class="reach">/g) || []).length;

test("by default the shorts are hidden and the button says how many there are", () => {
  const html = page().show();
  assert.equal(tables(html), 2);   // this week + the 28-day list, long-form only
  assert.ok(!html.includes("쇼츠 숨기기") && !html.includes("이번 주 올린 쇼츠"));
  assert.match(html, new RegExp(`<button type="button" class="tog" data-toggle="shorts" aria-expanded="false">쇼츠 보기 · ${SHORTS_COUNT}편</button>`));
  assert.ok(!html.includes('<span class="tag t-grey">쇼츠</span>'));   // no short row in the long-form tables
});

test("clicking the button shows the two shorts tables, clicking again hides them", () => {
  const p = page();
  p.show();
  p.click();
  const open = p.app.innerHTML;
  assert.equal(tables(open), 4);
  assert.ok(open.includes(`이번 주 올린 쇼츠 · ${R.this_week_shorts.length}편`) && open.includes("지난 28일 쇼츠 · 노출 많은 순"));
  assert.match(open, /data-toggle="shorts" aria-expanded="true">쇼츠 숨기기<\/button>/);
  assert.ok(open.includes('<span class="tag t-grey">쇼츠</span>'));
  p.click();
  assert.equal(tables(p.app.innerHTML), 2);
});

test("the open state survives moving to another channel and back, and a new page starts hidden", () => {
  const p = page();
  p.show();
  p.click();
  p.location.hash = "#ch/a2p";
  p.run("render()");
  p.location.hash = "#ch/soombi";
  p.run("render()");
  assert.equal(tables(p.app.innerHTML), 4);
  assert.equal(tables(page().show()), 2);   // a fresh sandbox is a reloaded page
});

test("without any shorts there is no button, and an empty shorts list says so", () => {
  const none = structuredClone(SAMPLE);
  none.detail.soombi.reach.this_week_shorts = [];
  none.detail.soombi.reach.all_shorts = [];
  const old = structuredClone(SAMPLE);   // a data.json from before the split has no shorts keys at all
  delete old.detail.soombi.reach.this_week_shorts;
  delete old.detail.soombi.reach.all_shorts;
  for (const data of [none, old]) {
    const html = page().show(data);
    assert.ok(!html.includes('data-toggle="shorts"') && !html.includes("쇼츠 보기"));
  }
  const only = structuredClone(SAMPLE);
  only.detail.soombi.reach.this_week_shorts = [];
  const p = page();
  p.show(only);
  p.click();
  assert.ok(p.app.innerHTML.includes("이번 주 올린 쇼츠 없음"));
});

test("redrawing from the button keeps the scroll position; a hash move still goes to the top", () => {
  const p = page();
  p.show();
  p.calls.scrollTo.length = 0;
  p.click();
  assert.deepEqual(p.calls.scrollTo, [[0, 120]]);
  p.calls.scrollTo.length = 0;
  p.run("render({ type: 'hashchange' })");   // what the hashchange listener passes
  assert.deepEqual(p.calls.scrollTo, [[0, 0]]);
});
