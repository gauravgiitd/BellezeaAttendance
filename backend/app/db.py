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


@contextmanager
def connection():
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        yield conn


def initialize_schema() -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
