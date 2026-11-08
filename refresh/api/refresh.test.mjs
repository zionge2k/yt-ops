// Run with: cd refresh && node --test
import { test } from "node:test";
import assert from "node:assert/strict";
import { refresh } from "./refresh.js";

const NOW = Date.parse("2026-11-08T12:00:00Z");
const ENV = { DASH_PASSWORD: "pw-secret", GITHUB_TOKEN: "ghp_token" };
const iso = (minAgo) => new Date(NOW - minAgo * 60_000).toISOString();

// Fake fetch: records calls; `runs` answers the list call, `dispatch` the POST.
function fake({ runs, dispatch = { status: 204 } }) {
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    calls.push({ url, init });
    const r = init.method === "POST" ? dispatch : runs;
    return { status: r.status, ok: r.status >= 200 && r.status < 300, json: async () => r.body ?? {} };
  };
  return { calls, fetchImpl };
}
const runsOf = (minAgo) => ({ status: 200, body: { workflow_runs: minAgo == null ? [] : [{ created_at: iso(minAgo) }] } });
const go = (body, f, env = ENV) => refresh({ body, env, fetchImpl: f.fetchImpl, now: () => NOW });

test("wrong password is 401 and never reaches GitHub", async () => {
  const f = fake({ runs: runsOf(null) });
  const r = await go({ password: "nope" }, f);
  assert.equal(r.status, 401);
  assert.deepEqual(r.json, { error: "wrong_password" });
  assert.equal(f.calls.length, 0);
});

test("non-object body or non-string password is 401", async () => {
  const f = fake({ runs: runsOf(null) });
  assert.equal((await go(null, f)).status, 401);
  assert.equal((await go({ password: 1 }, f)).status, 401);
  assert.equal(f.calls.length, 0);
});

test("missing env is 500 server_not_configured", async () => {
  const f = fake({ runs: runsOf(null) });
  assert.deepEqual((await go({ password: "x" }, f, { GITHUB_TOKEN: "t" })).json, { error: "server_not_configured" });
  assert.equal((await go({ password: "x" }, f, { DASH_PASSWORD: "p" })).status, 500);
  assert.equal(f.calls.length, 0);
});

test("run 3 minutes ago is 429 with retry_after_s about 420 and no dispatch", async () => {
  const f = fake({ runs: runsOf(3) });
  const r = await go({ password: "pw-secret" }, f);
  assert.equal(r.status, 429);
  assert.equal(r.json.error, "too_soon");
  assert.equal(r.json.retry_after_s, 420);
  assert.equal(r.json.started_at, iso(3));
  assert.ok(f.calls.every((c) => c.init.method !== "POST"));
});

test("run 20 minutes ago dispatches main and is 202", async () => {
  const f = fake({ runs: runsOf(20) });
  const r = await go({ password: "pw-secret" }, f);
  assert.equal(r.status, 202);
  assert.equal(r.json.ok, true);
  assert.equal(r.json.started_at, new Date(NOW).toISOString());
  const list = f.calls[0];
  assert.match(list.url, /\/actions\/workflows\/refresh\.yml\/runs\?per_page=1&event=workflow_dispatch$/);
  assert.equal(list.init.headers.Authorization, "Bearer ghp_token");
  const post = f.calls[1];
  assert.match(post.url, /zionge2k\/yt-ops\/actions\/workflows\/refresh\.yml\/dispatches$/);
  assert.deepEqual(JSON.parse(post.init.body), { ref: "main" });
});

test("no previous run dispatches", async () => {
  const f = fake({ runs: runsOf(null) });
  assert.equal((await go({ password: "pw-secret" }, f)).status, 202);
});

test("GitHub 500 on the runs list is 502 github_unavailable", async () => {
  const f = fake({ runs: { status: 500 } });
  const r = await go({ password: "pw-secret" }, f);
  assert.equal(r.status, 502);
  assert.deepEqual(r.json, { error: "github_unavailable" });
});

test("dispatch 403 is 502 dispatch_failed and leaks no secrets", async () => {
  const f = fake({ runs: runsOf(20), dispatch: { status: 403 } });
  const r = await go({ password: "pw-secret" }, f);
  assert.equal(r.status, 502);
  assert.deepEqual(r.json, { error: "dispatch_failed", status: 403 });
  assert.ok(!JSON.stringify(r.json).includes("ghp_token"));
});
