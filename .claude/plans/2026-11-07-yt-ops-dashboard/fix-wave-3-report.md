# Fix wave 3 report

## F2 — per-channel failure state (commit fix(render))
- `yt_run_log.channels jsonb` added to schema.sql and the migration (edited in place; schema not applied anywhere yet).
- `runner.run_collect` writes `channels = keys` of the run.
- `render._channel_errors`: per channel, the newest of the last 50 run_log rows whose `channels` contains the key (NULL = covers all); `collect_failed` and `errors[]` derive from it, each entry gets `run_started_at`.
- `site/app.js` errors list shows `(MM/DD HH:mm)` KST; `sample.json` updated.
- Tests: `test_collect_failed_uses_last_run_covering_channel`, `test_run_without_channels_value_covers_every_channel`, `test_run_log_records_channels`. RED: 3 failed (incl. updated shape test), GREEN: 112 passed.

## F1 — 60-day schedule disable (commit fix(ci))
- daily.yml: `actions: write`; keep-alive step (`if: always()`, `gh api -X PUT .../workflows/daily.yml/enable`) placed after deploy and before the exit-1 failure step. YAML validated.
- app.js: `staleDays(generatedAtIso, nowMs)` (0 when fresh, <=48h or unparsable); band `.stale-band` (warn colors) shown unless in sample mode. Checked with node: 24h -> 0, 3.5 days -> 3.
- runbook ③-2 documents the band and the Actions-tab check.

## Notes
- Page `errors[]` now only holds errors tied to configured channels (the "-" run_log-write error is never persisted anyway).
- Dry run: `run b5d2d8b0... latest_day=2026-11-04 errors=0`.
