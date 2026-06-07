import logging
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

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


def initialize_schema(
    *,
    skip_on_lock_timeout: bool = False,
    max_attempts: int | None = None,
    retry_delay_seconds: float | None = None,
) -> bool:
    if max_attempts is None:
        max_attempts = max(1, int(os.environ.get("SCHEMA_MIGRATE_MAX_ATTEMPTS", "1")))
    if retry_delay_seconds is None:
        retry_delay_seconds = float(os.environ.get("SCHEMA_MIGRATE_RETRY_SECONDS", "5"))

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    lock_timeout = _schema_lock_timeout()

    for attempt in range(1, max_attempts + 1):
        try:
            with connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql.SQL("SET lock_timeout TO {}").format(sql.Literal(lock_timeout)))
                    cur.execute(schema_sql)
                conn.commit()
            if attempt > 1:
                logger.info("Schema migration succeeded on attempt %s", attempt)
            return True
        except psycopg.errors.LockNotAvailable:
            logger.warning(
                "Schema migration lock timeout on attempt %s/%s",
                attempt,
                max_attempts,
            )
            if attempt < max_attempts:
                time.sleep(retry_delay_seconds)
                continue
            if skip_on_lock_timeout:
                logger.warning(
                    "Skipping schema migration after %s attempts due to lock timeout. "
                    "Run /api/admin/migrate when database traffic is quiet.",
                    max_attempts,
                )
                return False
            raise

    return False
