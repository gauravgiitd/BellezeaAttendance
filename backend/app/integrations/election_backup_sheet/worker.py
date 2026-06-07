from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

import psycopg
from psycopg.rows import dict_row

from backend.app.db import database_url
from backend.app.integrations.election_backup_sheet.constants import is_regression_harness_election
from backend.app.integrations.election_backup_sheet.queries import build_attendance_sheet_rows
from backend.app.integrations.election_backup_sheet.sheets_client import (
    ElectionBackupSheetsClient,
    backup_sheets_enabled,
)

logger = logging.getLogger(__name__)

NOTIFY_CHANNEL = "election_backup_sync"
BACKUP_SHEET_STATUSES = ("draft", "attendance_open", "voting_open", "voting_closed")
POLL_INTERVAL_SECONDS = float(os.environ.get("ELECTION_BACKUP_POLL_SECONDS", "30"))
DEBOUNCE_SECONDS = float(os.environ.get("ELECTION_BACKUP_DEBOUNCE_SECONDS", "2"))
BOOTSTRAP_INTERVAL_SECONDS = float(os.environ.get("ELECTION_BACKUP_BOOTSTRAP_SECONDS", "300"))
FAILURE_BACKOFF_SECONDS = float(os.environ.get("ELECTION_BACKUP_FAILURE_BACKOFF_SECONDS", "300"))

_background_thread: threading.Thread | None = None
_stop_event = threading.Event()


class ElectionBackupSheetWorker:
    def __init__(self, sheets_client: ElectionBackupSheetsClient) -> None:
        self.sheets_client = sheets_client
        self.pending_actions: dict[str, float] = {}
        self._failure_backoff_until: dict[str, float] = {}
        self._last_bootstrap_at = 0.0
        self._work_conn: psycopg.Connection | None = None

    def _get_work_conn(self) -> psycopg.Connection:
        if self._work_conn is None or self._work_conn.closed:
            self._work_conn = psycopg.connect(database_url(), row_factory=dict_row)
        return self._work_conn

    def _close_work_conn(self) -> None:
        if self._work_conn is not None and not self._work_conn.closed:
            self._work_conn.close()
        self._work_conn = None

    def _in_backoff(self, key: str) -> bool:
        return time.monotonic() < self._failure_backoff_until.get(key, 0)

    def _mark_failure(self, key: str) -> None:
        self._failure_backoff_until[key] = time.monotonic() + FAILURE_BACKOFF_SECONDS

    def _clear_failure(self, key: str) -> None:
        self._failure_backoff_until.pop(key, None)

    def _maybe_bootstrap_missing_sheets(self) -> None:
        now = time.monotonic()
        if now - self._last_bootstrap_at < BOOTSTRAP_INTERVAL_SECONDS:
            return
        self.bootstrap_missing_sheets()
        self._last_bootstrap_at = now

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        logger.info("Election backup sheet worker started")
        while not (stop_event and stop_event.is_set()):
            try:
                self._listen_loop(stop_event)
            except Exception:
                logger.exception("Election backup sheet worker error; retrying in 5 seconds")
                self._close_work_conn()
                if stop_event and stop_event.wait(5):
                    break
        logger.info("Election backup sheet worker stopped")

    def _listen_loop(self, stop_event: threading.Event | None = None) -> None:
        self.bootstrap()
        with psycopg.connect(database_url(), row_factory=dict_row, autocommit=True) as conn:
            conn.execute(f"LISTEN {NOTIFY_CHANNEL}")
            while not (stop_event and stop_event.is_set()):
                self.process_pending_deletions()
                self.process_due_actions()
                self._maybe_bootstrap_missing_sheets()

                for notify in conn.notifies(timeout=POLL_INTERVAL_SECONDS):
                    self.enqueue_payload(notify.payload)
                    if stop_event and stop_event.is_set():
                        break

                self.process_pending_deletions()
                self.process_due_actions()
        self._close_work_conn()

    def bootstrap(self) -> None:
        self.process_pending_deletions()
        self.bootstrap_missing_sheets()
        self._last_bootstrap_at = time.monotonic()

    def enqueue_payload(self, payload: str) -> None:
        try:
            message = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Ignoring invalid election backup notification: %s", payload)
            return

        action = message.get("action")
        if action == "delete":
            return

        election_id = message.get("election_id")
        if not election_id:
            return

        if self._should_ignore_election(str(election_id)):
            return

        election_key = str(election_id)
        if action == "create":
            self.pending_actions[f"create:{election_key}"] = time.monotonic()
        self.pending_actions[f"sync:{election_key}"] = time.monotonic() + DEBOUNCE_SECONDS

    def process_due_actions(self) -> None:
        now = time.monotonic()
        due_keys = [key for key, due_at in self.pending_actions.items() if due_at <= now]
        for key in due_keys:
            self.pending_actions.pop(key, None)
            action, election_id = key.split(":", 1)
            if self._in_backoff(election_id):
                self.pending_actions[key] = self._failure_backoff_until[election_id]
                continue
            try:
                if self._should_ignore_election(election_id):
                    continue
                if action == "create":
                    self.ensure_spreadsheet(election_id)
                self.sync_spreadsheet(election_id)
                self._clear_failure(election_id)
            except Exception:
                self._mark_failure(election_id)
                self.pending_actions[key] = self._failure_backoff_until[election_id]
                logger.exception("Failed election backup action %s for %s", action, election_id)

    def process_pending_deletions(self) -> None:
        conn = self._get_work_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, spreadsheet_id
                FROM election_backup_sheet_deletions
                WHERE deleted_at IS NULL
                ORDER BY queued_at
                """
            )
            pending = cur.fetchall()

        for row in pending:
            spreadsheet_id = row["spreadsheet_id"]
            try:
                self.sheets_client.delete_spreadsheet(spreadsheet_id)
                self.mark_deletion_complete(row["id"])
                logger.info("Deleted election backup spreadsheet %s", spreadsheet_id)
            except Exception as exc:
                self.mark_deletion_error(row["id"], str(exc))
                logger.exception("Failed deleting election backup spreadsheet %s", spreadsheet_id)

    def bootstrap_missing_sheets(self) -> None:
        conn = self._get_work_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.id
                FROM elections e
                LEFT JOIN election_backup_sheets s ON s.election_id = e.id
                WHERE e.status = ANY(%s)
                  AND s.election_id IS NULL
                  AND e.title NOT LIKE 'Regression Harness:%'
                ORDER BY e.created_at
                """,
                (list(BACKUP_SHEET_STATUSES),),
            )
            missing = [str(row["id"]) for row in cur.fetchall()]

        for election_id in missing:
            if self._in_backoff(election_id):
                continue
            try:
                self.ensure_spreadsheet(election_id)
                self.sync_spreadsheet(election_id)
                self._clear_failure(election_id)
            except Exception:
                self._mark_failure(election_id)
                logger.exception("Failed bootstrapping election backup sheet for %s", election_id)

    def ensure_spreadsheet(self, election_id: str) -> None:
        conn = self._get_work_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT spreadsheet_id FROM election_backup_sheets WHERE election_id = %s",
                (election_id,),
            )
            if cur.fetchone():
                return

            election = self.fetch_election(cur, election_id)
            if not election:
                return
            if is_regression_harness_election(election.get("title")):
                return
            if election["status"] not in BACKUP_SHEET_STATUSES:
                return

            title = self.spreadsheet_title(election)
            created = self.sheets_client.create_election_spreadsheet(title)
            cur.execute(
                """
                INSERT INTO election_backup_sheets (election_id, spreadsheet_id, spreadsheet_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (election_id) DO NOTHING
                """,
                (election_id, created["spreadsheet_id"], created["spreadsheet_url"]),
            )
        conn.commit()
        logger.info("Created election backup spreadsheet for %s", election_id)

    def sync_spreadsheet(self, election_id: str) -> None:
        conn = self._get_work_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.spreadsheet_id, e.*
                FROM election_backup_sheets s
                JOIN elections e ON e.id = s.election_id
                WHERE s.election_id = %s
                """,
                (election_id,),
            )
            row = cur.fetchone()
            if not row:
                return
            if is_regression_harness_election(row.get("title")):
                return
            if row["status"] not in BACKUP_SHEET_STATUSES:
                return

            headers, summary_row, sheet_rows = build_attendance_sheet_rows(cur, row)
            spreadsheet_id = row["spreadsheet_id"]

        try:
            self.sheets_client.update_attendance_tab(
                spreadsheet_id,
                headers,
                summary_row,
                sheet_rows,
            )
        except Exception as exc:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE election_backup_sheets
                    SET last_error = %s
                    WHERE election_id = %s
                    """,
                    (str(exc), election_id),
                )
            conn.commit()
            raise
        finally:
            del headers, summary_row, sheet_rows

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE election_backup_sheets
                SET last_synced_at = now(),
                    last_error = ''
                WHERE election_id = %s
                """,
                (election_id,),
            )
        conn.commit()

    def fetch_election(self, cur, election_id: str) -> dict[str, Any] | None:
        cur.execute("SELECT * FROM elections WHERE id = %s", (election_id,))
        return cur.fetchone()

    def _should_ignore_election(self, election_id: str) -> bool:
        conn = self._get_work_conn()
        with conn.cursor() as cur:
            election = self.fetch_election(cur, election_id)
        if not election:
            return True
        return is_regression_harness_election(election.get("title"))

    @staticmethod
    def spreadsheet_title(election: dict[str, Any]) -> str:
        title = str(election.get("title") or "Election").strip() or "Election"
        suffix = str(election["id"])[:8]
        full_title = f"{title} ({suffix})"
        return full_title[:120]

    def mark_deletion_complete(self, deletion_id: str) -> None:
        conn = self._get_work_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE election_backup_sheet_deletions
                SET deleted_at = now(),
                    last_error = ''
                WHERE id = %s
                """,
                (deletion_id,),
            )
        conn.commit()

    def mark_deletion_error(self, deletion_id: str, message: str) -> None:
        conn = self._get_work_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE election_backup_sheet_deletions
                SET last_error = %s
                WHERE id = %s
                """,
                (message[:2000], deletion_id),
            )
        conn.commit()


def backup_worker_enabled() -> bool:
    if os.environ.get("ELECTION_BACKUP_SHEET_WORKER_ENABLED", "true").lower() in {"0", "false", "no"}:
        return False
    return backup_sheets_enabled()


def start_in_background() -> bool:
    global _background_thread

    if not backup_worker_enabled():
        logger.info(
            "Election backup sheet worker not started. Configure ELECTION_BACKUP_DRIVE_FOLDER_ID and "
            "GOOGLE_DRIVE_REFRESH_TOKEN (recommended), or a service account JSON."
        )
        return False

    if _background_thread and _background_thread.is_alive():
        return True

    _stop_event.clear()
    worker = ElectionBackupSheetWorker(ElectionBackupSheetsClient.from_env())
    _background_thread = threading.Thread(
        target=worker.run_forever,
        args=(_stop_event,),
        name="election-backup-sheet-worker",
        daemon=True,
    )
    _background_thread.start()
    return True


def stop_background() -> None:
    global _background_thread

    _stop_event.set()
    if _background_thread and _background_thread.is_alive():
        _background_thread.join(timeout=POLL_INTERVAL_SECONDS + 5)
    _background_thread = None


def run_worker() -> None:
    logging.basicConfig(
        level=os.environ.get("ELECTION_BACKUP_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not backup_sheets_enabled():
        raise RuntimeError(
            "Election backup sheet worker is not configured. Set ELECTION_BACKUP_DRIVE_FOLDER_ID and "
            "GOOGLE_DRIVE_REFRESH_TOKEN, or a service account JSON path."
        )
    ElectionBackupSheetWorker(ElectionBackupSheetsClient.from_env()).run_forever()
