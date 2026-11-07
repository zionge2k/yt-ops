# Fix wave 2 report

Final: `pytest tests -q -W error` -> 109 passed, 0 warnings (101 + 8 new).

## F1 ghost schedule rows (fb82947)
- `store.replace_channel(conn, table, channel_key, rows, pk)`: `delete ... where channel_key = %s` then `upsert`. Runner uses it for `yt_schedule` only (`REPLACE_PER_CHANNEL`), inside the per-channel store step, after collection succeeded. A channel whose schedule collector raised never reaches the DELETE (old rows kept).
- Tests: `test_replace_channel_deletes_then_upserts`, `test_replace_channel_empty_rows_still_deletes`, `test_runner_replaces_schedule_rows`, `test_runner_empty_schedule_still_replaces`.
- RED: `4 failed, 15 passed` (AttributeError: no attribute 'replace_channel'). GREEN: `19 passed`.
- Concern: delete + upsert are not atomic (autocommit); a crash between them leaves the channel empty until next run.

## F2 + F3 live (d21c81b)
- `live.http_error_reason(e)`: uses `e.error_details` if it is a list of dicts, else parses `e.content` JSON `error.errors[0].reason`. Note: in the installed googleapiclient `error_details` is a string (`''`) for this body shape, so the JSON parse path is the one actually used. Only `liveStreamingNotEnabled` -> none row; other 403 (and 403 without reason) re-raise.
- `yt_live_snapshot` PK `(channel_key, taken_at, broadcast_id)`, `broadcast_id text not null default 'none'`; none row stores `"none"`. Updated schema.sql + migration (identical apart from header), runner PK map, `commands.py --save` pk. render.py/site do not read broadcast_id, so no change needed.
- `tests/fakes.py` `http_error(status, reason=None)`.
- Tests: updated none-row / not-live / 403 / commands pk; added `test_live_403_quota_propagates`, `test_live_403_without_reason_propagates`, `test_http_error_reason`, `test_live_two_broadcasts_two_rows`.
- RED: `7 failed, 102 passed`. GREEN: `109 passed`. (`two_broadcasts` passes pre-fix by itself since logic already emits two rows; it guards the distinct-key triple.)
- Concern: render `_latest_per_channel` still shows one broadcast per channel when two are active.

## F5 collect_failed (7c50b67)
- render: `_failed(stage)` = client / channel_daily / `store:*`. Test extended with groovewav `store:yt_channel_daily`. RED: 1 failed; GREEN: pass.

## F4 backfill 185 (4faaf7d)
- CLI default 185, `test_cli_all_and_backfill_defaults`, runbook, daily.yml input description, MAX_ROWS comment (185 x 5 = 925 < 1000). RED: test_cli failed (180 != 185); GREEN pass.

## Real checks
- `collect --channel soombi --dry-run --days 3`: `run 99ce977f... latest_day=2026-11-04 errors=0 counts={... 'yt_schedule': 5, 'yt_live_snapshot': 1}`
- `live --channel all` head:
```
channel           state  life_cycle  concurrent  health  stream_status
숨비찰나          🟢     live        -           good    active
MORROW            ⚪     none        -           -       -
BACK THEN         🟢     live        -           good    active
Adagio to Presto  ⚪     none
pli.wav / groove.wav / 숨비카페  ⚪ none
JustSoombi        🟡     live        -           ok      active
```
(urachacha/groovewav stay none via is_live=False.)
