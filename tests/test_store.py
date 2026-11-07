from ytops import store


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.many = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def executemany(self, sql, rows):
        self.many.append((sql, list(rows)))


class FakeTransaction:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.events.append("begin")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.conn.events.append("rollback" if exc_type else "commit")
        return False


class FakeConn:
    def __init__(self):
        self.cur = FakeCursor()
        self.events = []

    def transaction(self):
        return FakeTransaction(self)

    def cursor(self):
        return self.cur


def test_upsert_sql_has_on_conflict_and_keep():
    conn = FakeConn()
    rows = [{"video_id": "a", "title": "t", "first_seen_at": 1}]
    n = store.upsert(conn, "yt_video", rows, ["video_id"], keep=("first_seen_at",))
    sql, sent = conn.cur.many[0]
    assert n == 1 and sent == rows
    assert "insert into yt_video (video_id, title, first_seen_at)" in sql
    assert "on conflict (video_id) do update set title = excluded.title" in sql
    assert "first_seen_at = excluded" not in sql
    assert "%(video_id)s" in sql


def test_upsert_zero_rows_runs_no_sql():
    conn = FakeConn()
    assert store.upsert(conn, "yt_video", [], ["video_id"]) == 0
    assert conn.cur.many == [] and conn.cur.executed == []


def test_upsert_all_pk_columns_does_nothing_on_conflict():
    conn = FakeConn()
    store.upsert(conn, "t", [{"a": 1}], ["a"])
    assert "do nothing" in conn.cur.many[0][0]


def test_upsert_rejects_mismatched_keys():
    import pytest
    with pytest.raises(AssertionError):
        store.upsert(FakeConn(), "t", [{"a": 1}, {"b": 2}], ["a"])


def test_replace_channel_deletes_then_upserts():
    conn = FakeConn()
    rows = [{"channel_key": "soombi", "video_id": "v1", "title": "t"}]
    n = store.replace_channel(conn, "yt_schedule", "soombi", rows, ["channel_key", "video_id"])
    assert n == 1
    assert conn.cur.executed == [("delete from yt_schedule where channel_key = %s", ("soombi",))]
    assert conn.cur.many[0][1] == rows and "insert into yt_schedule" in conn.cur.many[0][0]


def test_replace_channel_empty_rows_still_deletes():
    conn = FakeConn()
    assert store.replace_channel(conn, "yt_schedule", "soombi", [], ["channel_key", "video_id"]) == 0
    assert conn.cur.executed == [("delete from yt_schedule where channel_key = %s", ("soombi",))]
    assert conn.cur.many == []


def test_replace_channel_is_atomic():
    import pytest

    conn = FakeConn()

    def boom(sql, rows):
        raise RuntimeError("upsert failed")

    conn.cur.executemany = boom
    with pytest.raises(RuntimeError):
        store.replace_channel(conn, "yt_schedule", "soombi",
                              [{"channel_key": "soombi", "video_id": "v1"}], ["channel_key", "video_id"])
    # delete ran inside a transaction that rolled back
    assert conn.cur.executed and conn.events == ["begin", "rollback"]
    ok = FakeConn()
    store.replace_channel(ok, "yt_schedule", "soombi", [], ["channel_key", "video_id"])
    assert ok.events == ["begin", "commit"]


def test_run_collectors_migration_adds_column_and_backfills_live_only_rows():
    from pathlib import Path
    db = Path(__file__).resolve().parent.parent / "db"
    for path in (db / "migrations" / "2026-11-08-run-collectors.sql", db / "schema.sql"):
        sql = " ".join(path.read_text(encoding="utf-8").split())
        assert "alter table yt_run_log add column if not exists collectors jsonb" in sql, path.name
        assert "update yt_run_log set collectors = '[\"live\"]'::jsonb where collectors is null" in sql, path.name
