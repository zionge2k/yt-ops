// Run with: node --test tests/test_site_stale.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const { staleDays } = createRequire(import.meta.url)("../site/stale.js");
const NOW = Date.parse("2026-11-08T00:00:00Z");

test("fresh within 48 hours is 0", () => {
  assert.equal(staleDays("2026-11-06T01:00:00Z", NOW), 0);
});

test("older than 48 hours counts whole days", () => {
  assert.equal(staleDays("2026-11-05T00:00:00Z", NOW), 3);
});

test("unparsable or missing is 0", () => {
  assert.equal(staleDays("nope", NOW), 0);
  assert.equal(staleDays(undefined, NOW), 0);
});
