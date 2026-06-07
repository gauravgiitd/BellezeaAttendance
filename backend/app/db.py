import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "db" / "schema.sql"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return url


def _apply_session_settings(conn: psycopg.Connection) -> None:
    if os.environ.get("REGRESSION_HARNESS_ACTIVE", "").lower() in {"1", "true", "yes"}:
        with conn.cursor() as cur:
            cur.execute("SET app.regression_harness_active = 'true'")
            cur.execute("SET lock_timeout = '10s'")


@contextmanager
def connection():
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        _apply_session_settings(conn)
        yield conn


def initialize_schema() -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
