// Pure helper for the "not refreshed" band; loaded before app.js (and imported by node --test).
"use strict";

const STALE_HOURS = 48;

/** Whole days since `iso` when older than STALE_HOURS, else 0 (fresh or unparsable). */
function staleDays(iso, nowMs) {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return 0;
  const hours = (nowMs - t) / 3600000;
  return hours > STALE_HOURS ? Math.floor(hours / 24) : 0;
}

if (typeof module !== "undefined" && module.exports) module.exports = { staleDays, STALE_HOURS };
