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


class FakeConn:
    def __init__(self):
        self.cur = FakeCursor()

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
