"""Postgres storage (Supabase): connection, idempotent upsert, small helpers."""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def db_url() -> str | None:
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    url = os.environ.get("SUPABASE_DB_URL")
    return url if url and "<" not in url else None


def connect():
    url = db_url()
    if not url:
        sys.exit("SUPABASE_DB_URL 이 .env 에 없다 — Supabase 대시보드 Settings → Database → Connection string(Session pooler) 을 넣을 것.")
    import psycopg

    # autocommit: otherwise a SELECT opens an implicit transaction that is never committed
    return psycopg.connect(url, connect_timeout=20, autocommit=True)


def upsert(conn, table: str, rows: list[dict], pk: list[str], keep: tuple[str, ...] = ()) -> int:
    """Insert rows; on pk conflict overwrite every non-pk column except `keep`."""
    if not rows:
        return 0
    cols = list(rows[0])
    assert all(list(r) == cols for r in rows), f"{table}: rows must share the same keys"
    update = [c for c in cols if c not in pk and c not in keep]
    action = (
        "do update set " + ", ".join(f"{c} = excluded.{c}" for c in update) if update else "do nothing"
    )
    sql = (
        f"insert into {table} ({', '.join(cols)}) values ({', '.join(f'%({c})s' for c in cols)}) "
        f"on conflict ({', '.join(pk)}) {action}"
    )
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


def fetch(conn, sql: str, params=()) -> list[dict]:
    from psycopg.rows import dict_row

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def apply_schema(conn, path) -> None:
    sql = Path(path).read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
