from __future__ import annotations

import logging

import psycopg
from psycopg.rows import dict_row

from backend.app.db import database_url

logger = logging.getLogger(__name__)

PAUSE_TABLE = "election_backup_sync_pause"


def set_backup_sync_paused(paused: bool) -> None:
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {PAUSE_TABLE} (id, paused, updated_at)
                VALUES (1, %s, now())
                ON CONFLICT (id) DO UPDATE
                SET paused = EXCLUDED.paused,
                    updated_at = now()
                """,
                (paused,),
            )
        conn.commit()
    logger.info("Election backup sync pause set to %s", paused)


def is_backup_sync_paused() -> bool:
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT paused FROM {PAUSE_TABLE} WHERE id = 1")
            row = cur.fetchone()
    return bool(row and row["paused"])
