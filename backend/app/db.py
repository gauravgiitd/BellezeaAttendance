import os
import re
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

_LOCK_TIMEOUT_PATTERN = re.compile(r"^\d+(?:ms|s|min|h|d)?$", re.IGNORECASE)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "db" / "schema.sql"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return url


def _schema_lock_timeout() -> str:
    configured = os.environ.get("SCHEMA_LOCK_TIMEOUT", "30s").strip()
    if _LOCK_TIMEOUT_PATTERN.fullmatch(configured):
        return configured
    return "30s"


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
    lock_timeout = _schema_lock_timeout()
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SET lock_timeout TO {}").format(sql.Literal(lock_timeout)))
            cur.execute(schema_sql)
        conn.commit()
