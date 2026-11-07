# fix: uploads() duplicate ids

- Symptom: soombi uploads() gave 489 items, 440 unique; pliwav 90/90.
- Pagination loop is correct: new test_uploads_pages_do_not_repeat (3 pages 50/50/20) passed on the old code with exactly 3 playlistItems calls.
- Root cause: the uploads playlist returns some videoIds more than once (repeats across pages); they were passed unchanged to videos.list, which echoes duplicate ids back.
- Fix: ytops/data.py dedupes ids (order-preserving) in uploads() and videos(), and videos() dedupes returned items by id.
- Tests: test_uploads_dedupes_ids was RED before the fix; full suite 114 passed (-W error).
- Real check: soombi 440 440, pliwav 90 90.
