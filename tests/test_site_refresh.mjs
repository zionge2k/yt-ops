// Cheap source guards for the refresh button (no DOM). Run with: node --test tests/test_site_refresh.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const src = readFileSync(new URL("../site/app.js", import.meta.url), "utf8");

test("REFRESH_URL constant exists", () => {
  assert.match(src, /^const REFRESH_URL = /m);
});

test("polling fetches data.enc with a cache-busting query", () => {
  assert.ok(src.includes("data.enc?r="));
});

test("request body key is password", () => {
  assert.match(src, /JSON\.stringify\(\{ password:/);
});
