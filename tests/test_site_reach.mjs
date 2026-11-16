// Thumbnail reach on the page: sample.json carries the new keys, and the board card / channel panels render them.
// app.js is a browser script, so it is evaluated in a vm sandbox with a stub DOM. Run: node --test tests/test_site_reach.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const SAMPLE = JSON.parse(read("../site/sample.json"));
const ROW_KEYS = ["video_id", "title", "published_at", "kind", "impressions", "ctr", "views", "verdict"];

function sandbox() {
  const ctx = vm.createContext({
    document: { getElementById: () => ({}) },
    window: { addEventListener() {}, scrollTo() {} },
    location: { hash: "" },
    fetch: () => Promise.reject(new Error("no network in tests")),
    console, Intl, Date, setTimeout, clearTimeout, setInterval, clearInterval,
  });
  vm.runInContext(read("../site/app.js"), ctx, { filename: "app.js" });
  return ctx;
}

const CTX = sandbox();
function run(data, expr) {
  CTX.__data = data;
  return vm.runInContext(`DATA = __data; ${expr}`, CTX);
}
const clone = () => structuredClone(SAMPLE);
const board = (data = SAMPLE) => run(data, "renderBoard()");
const channel = (key, data = SAMPLE) => run(data, `renderChannel(${JSON.stringify(key)})`);
const card = (html, display) => html.split("<article").find((a) => a.includes(`<h2>${display}</h2>`));

test("sample.json: two board entries carry reach7, one of them null", () => {
  const withKey = Object.entries(SAMPLE.board).filter(([, b]) => "reach7" in b);
  assert.equal(withKey.length, 2);
  const nulls = withKey.filter(([, b]) => b.reach7 === null);
  assert.equal(nulls.length, 1);
  const filled = withKey.find(([, b]) => b.reach7 !== null)[1].reach7;
  assert.deepEqual(Object.keys(filled).sort(),
    ["as_of", "ctr", "ctr_pp", "ctr_status", "impressions", "impressions_pct", "impressions_status", "window_days"]);
});

test("sample.json: one channel has detail.reach with the row shape the renderer reads", () => {
  const withReach = Object.entries(SAMPLE.detail).filter(([, d]) => d.reach);
  assert.equal(withReach.length, 1);
  const r = withReach[0][1].reach;
  assert.equal(r.days, 28);
  for (const k of ["impressions", "ctr", "impressions_pct", "ctr_pp", "impressions_status", "ctr_status", "as_of", "window_days",
    "this_week", "all", "this_week_shorts", "all_shorts", "shorts_ctr", "long_ctr"]) assert.ok(k in r, k);
  assert.ok(r.this_week.length > 0 && r.all.length > 0 && r.all.length <= 12);
  assert.ok(r.this_week_shorts.length > 0 && r.all_shorts.length > 0);
  for (const row of [...r.this_week, ...r.all, ...r.this_week_shorts, ...r.all_shorts]) assert.deepEqual(Object.keys(row).sort(), [...ROW_KEYS].sort());
  // shorts are listed apart: the long-form lists hold none, the shorts lists only shorts
  assert.ok([...r.this_week, ...r.all].every((v) => v.kind !== "short") && [...r.this_week_shorts, ...r.all_shorts].every((v) => v.kind === "short"));
  assert.ok(["fix", "ok"].every((x) => r.all.some((v) => v.verdict === x)) && r.all_shorts.some((v) => v.verdict === "push"));
});

// The compact card (2026-11-09) shows the two reach figures as plain cells: the value alone, coloured by its
// status. The impressions cell sits right before the ctr cell, so it is found from there, not by its label.
const CTR_CELL = '<span class="k">클릭률</span>';
const GREY_DASH = '<span class="v n t-grey">—</span>';
const bothDashes = (html) => new RegExp(`${GREY_DASH}</div>\\s*<div class="cell">${CTR_CELL}${GREY_DASH}`).test(html);

test("board card shows the 7-day impressions and ctr cells after the 48-hour cell, coloured by status", () => {
  const data = clone();
  data.board.soombi.reach7 = { impressions: 123456, ctr: 0.041, impressions_pct: 18.04, ctr_pp: -1.23,
    impressions_status: "red", ctr_status: "blue", as_of: "2026-11-03" };
  const html = card(board(data), "숨비찰나");
  const h48 = html.indexOf('<span class="k">48시간');
  assert.ok(h48 >= 0 && h48 < html.indexOf(CTR_CELL));
  assert.ok(html.indexOf(CTR_CELL) < html.indexOf('class="live'));
  assert.match(html, /<span class="v n t-red">12\.3<small>만<\/small><\/span><\/div>\s*<div class="cell"><span class="k">클릭률<\/span><span class="v n t-blue">4\.1<small>%<\/small><\/span>/);
  assert.ok(!bothDashes(html));
});

test("a stopped reach feed shows grey dashes on the card and the last day in the detail", () => {
  const data = clone();
  data.board.soombi.reach7 = { stale: true, as_of: "2026-10-01" };
  data.detail.soombi.reach = { stale: true, as_of: "2026-10-01" };
  const html = card(board(data), "숨비찰나");
  assert.ok(bothDashes(html));
  assert.ok(!html.includes("NaN") && !html.includes("undefined"));
  const detail = channel("soombi", data);
  assert.ok(detail.includes('<h3>썸네일 성적</h3><p class="note-grey">보고서가 멈췄어요 · 마지막 10/1</p>'));
  assert.ok(!detail.includes("쇼츠 vs 롱폼") && !detail.includes("NaN") && !detail.includes("undefined"));
});

test("channel detail: a short window is labelled with its real days", () => {
  const data = clone();
  data.detail.soombi.reach.window_days = 5;
  const html = channel("soombi", data);
  assert.ok(html.includes('<span class="asof">5일 · 11/3까지</span>') && html.includes("5일 노출 합계"));
});

test("board card: under ten thousand stays a plain number, the ctr keeps one decimal", () => {
  const data = clone();
  data.board.soombi.reach7 = { impressions: 9876, ctr: 0.0523, impressions_pct: 4.26, ctr_pp: 0.4,
    impressions_status: "purple", ctr_status: "purple", as_of: "2026-11-03" };
  const html = card(board(data), "숨비찰나");
  assert.ok(html.includes('<span class="v n t-purple">9,876</span>'));
  assert.ok(html.includes(`${CTR_CELL}<span class="v n t-purple">5.2<small>%</small></span>`));
});

test("board card without reach data shows grey dashes", () => {
  const data = clone();
  data.board.a2p.reach7 = null;
  delete data.board.soombi.reach7;   // a data.json from before this feature has no key at all
  for (const display of ["Adagio to Presto", "숨비찰나"]) {
    const html = card(board(data), display);
    assert.ok(bothDashes(html), display);
    assert.ok(!html.includes("NaN") && !html.includes("undefined"), display);
  }
});

test("board card: impressions without a ctr show the number and a grey dash", () => {
  const data = clone();
  data.board.soombi.reach7 = { impressions: 5000, ctr: null, impressions_pct: null, ctr_pp: null,
    impressions_status: "grey", ctr_status: "grey", as_of: "2026-11-03" };
  const html = card(board(data), "숨비찰나");
  assert.ok(html.includes('<span class="v n t-grey">5,000</span>'));
  assert.ok(html.includes(`${CTR_CELL}${GREY_DASH}`));
});

test("a failed-collection card has no reach cells", () => {
  const html = card(board(), "groove.wav");
  assert.ok(!html.includes(CTR_CELL) && !html.includes('class="cell"'));
});

test("channel detail: reach panels come right after 수익창출", () => {
  const html = channel("soombi");
  const at = (t) => html.indexOf(`<h3>${t}`);
  assert.ok(at("수익창출") >= 0 && at("수익창출") < at("썸네일 성적"));
  assert.ok(at("썸네일 성적") < at("쇼츠 vs 롱폼 클릭률") && at("쇼츠 vs 롱폼 클릭률") < at("구독자 현황"));
  assert.ok(html.includes('<h3>썸네일 성적<span class="asof">28일 · 11/3까지</span></h3>'));
});

test("channel detail: summary stats, both tables and the note", () => {
  const r = SAMPLE.detail.soombi.reach;
  const html = channel("soombi");
  assert.ok(html.includes("28일 노출 합계") && html.includes("채널 클릭률"));
  assert.ok(html.includes(`<h4 class="sub">이번 주 올린 영상 · ${r.this_week.length}편</h4>`));
  assert.ok(html.includes('<h4 class="sub">지난 28일 전체 · 노출 많은 순</h4>'));
  assert.equal((html.match(/<table class="reach">/g) || []).length, 2);
  assert.ok(html.includes("<th>영상</th><th>올린 날</th><th class=\"n\">노출</th><th class=\"n\">클릭률</th><th class=\"n\">조회</th><th>한마디</th>"));
  assert.ok(html.includes('<p class="qwhen n">클릭률 = 썸네일을 본 사람 중 누른 비율'));
  assert.ok(!html.includes("NaN") && !html.includes("undefined"));
});

test("channel detail: verdict wording and colours, short tag only on short videos", () => {
  const data = clone();
  const mk = (title, kind, verdict) => ({ video_id: title, title, published_at: "2026-10-05", kind, impressions: 24000,
    ctr: 0.0256, views: 1234, verdict });
  data.detail.soombi.reach.all = [mk("A", "long", "fix"), mk("B", "long", "push"), mk("C", "short", "ok"), mk("D", "long", null)];
  const html = channel("soombi", data);
  assert.ok(html.includes('<td class="t-red">노출 많은데 클릭 적음 → 썸네일·제목 바꿔 볼 후보</td>'));
  assert.ok(html.includes('<td class="t-purple">클릭률 높은데 노출 적음 → 다시 밀어 볼 후보</td>'));
  assert.ok(html.includes('<td class="muted">괜찮아요</td>'));
  assert.ok(html.includes("<td></td></tr>"));   // no verdict: an empty cell
  assert.ok(html.includes('<td>C <span class="tag t-grey">쇼츠</span></td>'));
  assert.ok(html.includes("<td>A</td>") && html.includes("<td>D</td>"));
  assert.ok(html.includes('<td class="n">2.4<small>만</small></td>') || html.includes('<td class="n">2.4만</td>'));
  assert.ok(html.includes('<td class="n">2.6%</td>') && html.includes('<td class="n">1,234</td>') && html.includes('<td class="n">10/5</td>'));
});

test("channel detail: titles are escaped, a missing title falls back to the video id, missing numbers are dashes", () => {
  const data = clone();
  data.detail.soombi.reach.all = [{ video_id: "vid123", title: null, published_at: null, kind: null, impressions: null, ctr: null, views: null, verdict: null },
    { video_id: "x", title: "<img src=x onerror=alert(1)>", published_at: "2026-10-05", kind: "long", impressions: 500, ctr: 0.1, views: 3, verdict: null }];
  const html = channel("soombi", data);
  assert.ok(html.includes("<td>vid123</td>") && !html.includes("<img src=x"));
  assert.ok(html.includes("&lt;img src=x onerror=alert(1)&gt;"));
  assert.ok(html.includes('<td class="n">—</td><td class="n">—</td><td class="n">—</td><td class="n">—</td><td></td></tr>'));
});

test("channel detail: an empty week says so", () => {
  const data = clone();
  data.detail.soombi.reach.this_week = [];
  const html = channel("soombi", data);
  assert.match(html, /<h4 class="sub">이번 주 올린 영상 · 0편<\/h4>\s*<p class="note-grey">이번 주 올린 영상 없음<\/p>/);
  assert.equal((html.match(/<table class="reach">/g) || []).length, 1);   // only the 28-day table is left
});

test("channel detail: shorts vs long bars", () => {
  const data = clone();
  data.detail.soombi.reach.shorts_ctr = 0.068;
  data.detail.soombi.reach.long_ctr = 0.039;
  const html = channel("soombi", data);
  const panel = html.slice(html.indexOf("<h3>쇼츠 vs 롱폼 클릭률"));
  assert.ok(panel.includes('aria-label="쇼츠 6.8%"') && panel.includes('aria-label="롱폼 3.9%"'));
  assert.ok(panel.includes('<span class="hv n">6.8%</span>') && panel.includes('<span class="hv n">3.9%</span>'));
  data.detail.soombi.reach.shorts_ctr = null;
  assert.ok(channel("soombi", data).includes('aria-label="쇼츠 —"'));
});

test("channel detail without reach: one waiting line, no shorts-vs-long panel", () => {
  for (const key of ["backthen", "pliwav"]) {    // no detail.reach key in the sample
    const html = channel(key);
    assert.ok(html.includes('<h3>썸네일 성적</h3><p class="note-grey">보고서 쌓이는 중 · 유튜브가 하루 한 번 내놓아요</p>'), key);
    assert.ok(!html.includes("쇼츠 vs 롱폼"), key);
  }
  const data = clone();
  data.detail.soombi.reach = null;
  assert.ok(channel("soombi", data).includes("보고서 쌓이는 중 · 유튜브가 하루 한 번 내놓아요"));
});

test("the schedule cell shows the last booked day as a Korean date, not the UTC one", () => {
  const data = clone();
  data.board.soombi.schedule = {
    long: { n: 2, last: "2026-12-03T21:00:00+00:00", status: "blue" },  // KST 12/4 06:00
    short: { n: 1, last: "2026-12-03T10:00:00+00:00", status: "blue" },  // KST 12/3 19:00
  };
  const html = card(board(data), "숨비찰나");
  assert.ok(html.includes("(12/4까지)") && html.includes("(12/3까지)"));
});
