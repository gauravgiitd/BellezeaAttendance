from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from typing import Any, TypeVar

from backend.app.integrations.election_backup_sheet.constants import (
    REGRESSION_HARNESS_TITLE_PREFIX,
    is_regression_harness_election,
)

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SCOPES = [DRIVE_SCOPE, SHEETS_SCOPE]
ATTENDANCE_TAB_NAME = "Attendance"
SERVICE_ACCOUNT_STORAGE_ERROR = (
    "Google service accounts cannot create Drive files in personal Gmail folders anymore "
    "(storage limit is 0). Set GOOGLE_DRIVE_REFRESH_TOKEN using "
    "scripts/authorize_google_drive_backup.py, or use a Google Workspace Shared Drive."
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ElectionBackupSheetsClient:
    def __init__(self, credentials: Any, folder_id: str) -> None:
        self._credentials = credentials
        self.folder_id = folder_id

    @classmethod
    def from_env(cls) -> "ElectionBackupSheetsClient":
        folder_id = os.environ.get("ELECTION_BACKUP_DRIVE_FOLDER_ID", "").strip()
        if not folder_id:
            raise RuntimeError("ELECTION_BACKUP_DRIVE_FOLDER_ID is not configured")

        credentials = load_drive_credentials()
        if has_oauth_credentials():
            verify_oauth_refresh(credentials)
        return cls(credentials, folder_id)

    def _with_services(self, operation: Callable[[Any, Any], T]) -> T:
        from google.auth.transport.requests import AuthorizedSession
        from googleapiclient.discovery import build

        session = AuthorizedSession(self._credentials)
        try:
            drive = build("drive", "v3", http=session, cache_discovery=False)
            sheets = build("sheets", "v4", http=session, cache_discovery=False)
            return operation(drive, sheets)
        finally:
            session.close()

    def create_election_spreadsheet(self, title: str) -> dict[str, str]:
        if is_regression_harness_election(title) or REGRESSION_HARNESS_TITLE_PREFIX in title:
            raise RuntimeError(f"Refusing to create backup sheet for regression harness title: {title}")

        metadata = {
            "name": title,
            "mimeType": "application/vnd.google-apps.spreadsheet",
            "parents": [self.folder_id],
        }

        def create(drive: Any, sheets: Any) -> dict[str, str]:
            try:
                created = (
                    drive.files()
                    .create(body=metadata, fields="id, webViewLink")
                    .execute()
                )
            except Exception as exc:
                raise translate_drive_create_error(exc) from exc

            spreadsheet_id = created["id"]
            spreadsheet = sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            default_sheet_id = spreadsheet["sheets"][0]["properties"]["sheetId"]
            sheets.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": [
                        {
                            "updateSheetProperties": {
                                "properties": {
                                    "sheetId": default_sheet_id,
                                    "title": ATTENDANCE_TAB_NAME,
                                },
                                "fields": "title",
                            }
                        }
                    ]
                },
            ).execute()
            return {
                "spreadsheet_id": spreadsheet_id,
                "spreadsheet_url": created.get("webViewLink", ""),
            }

        return self._with_services(create)

    def update_attendance_tab(
        self,
        spreadsheet_id: str,
        headers: list[str],
        summary_row: list[str],
        rows: list[list[str]],
    ) -> None:
        values = [summary_row, headers, *rows]

        def update(_drive: Any, sheets: Any) -> None:
            sheets.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"{ATTENDANCE_TAB_NAME}!A:ZZ",
            ).execute()
            sheets.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{ATTENDANCE_TAB_NAME}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": values},
            ).execute()

        self._with_services(update)

    def delete_spreadsheet(self, spreadsheet_id: str) -> None:
        def delete(drive: Any, _sheets: Any) -> None:
            drive.files().delete(fileId=spreadsheet_id).execute()

        self._with_services(delete)


def oauth_client_credentials() -> tuple[str, str]:
    return (
        os.environ.get("GOOGLE_DRIVE_OAUTH_CLIENT_ID", "").strip(),
        os.environ.get("GOOGLE_DRIVE_OAUTH_CLIENT_SECRET", "").strip(),
    )


def oauth_configuration_error() -> str | None:
    refresh_token = os.environ.get("GOOGLE_DRIVE_REFRESH_TOKEN", "").strip()
    if not refresh_token:
        return None

    client_id, client_secret = oauth_client_credentials()
    if client_id and client_secret:
        return None

    return (
        "GOOGLE_DRIVE_REFRESH_TOKEN is set but GOOGLE_DRIVE_OAUTH_CLIENT_ID and "
        "GOOGLE_DRIVE_OAUTH_CLIENT_SECRET are missing. Backup sheets require a separate "
        "Desktop OAuth client; do not substitute GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET."
    )


def has_oauth_credentials() -> bool:
    client_id, client_secret = oauth_client_credentials()
    return bool(
        os.environ.get("GOOGLE_DRIVE_REFRESH_TOKEN", "").strip()
        and client_id
        and client_secret
    )


def has_service_account_credentials() -> bool:
    return bool(
        os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "").strip()
    )


def backup_sheets_enabled() -> bool:
    folder_id = os.environ.get("ELECTION_BACKUP_DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        return False
    return has_oauth_credentials() or has_service_account_credentials()


def load_drive_credentials():
    if has_oauth_credentials():
        return load_oauth_credentials()
    if has_service_account_credentials():
        logger.warning(
            "Using a Google service account for election backup sheets. "
            "This usually fails for personal Gmail folders; prefer GOOGLE_DRIVE_REFRESH_TOKEN."
        )
        return load_service_account_credentials()
    raise RuntimeError(
        "Election backup sheets are not configured. Set GOOGLE_DRIVE_REFRESH_TOKEN with "
        "GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET, or provide a service account JSON."
    )


def load_oauth_credentials():
    from google.oauth2.credentials import Credentials

    config_error = oauth_configuration_error()
    if config_error:
        raise RuntimeError(config_error)

    client_id, client_secret = oauth_client_credentials()
    return Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_DRIVE_REFRESH_TOKEN"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )


def verify_oauth_refresh(credentials) -> None:
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request

    try:
        credentials.refresh(Request())
    except RefreshError as exc:
        raise RuntimeError(
            "Google Drive OAuth refresh failed. The refresh token must be issued with the "
            "same Desktop OAuth client as GOOGLE_DRIVE_OAUTH_CLIENT_ID/SECRET. Re-run "
            "scripts/authorize_google_drive_backup.py, then copy all three GOOGLE_DRIVE_* "
            "values to Render with no surrounding quotes. If the OAuth consent screen is in "
            "Testing mode, publish it to Production or tokens expire after about 7 days. "
            f"Google error: {exc}"
        ) from exc


def load_service_account_credentials():
    from google.oauth2 import service_account

    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    json_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "").strip()

    if raw_json:
        info = json.loads(raw_json)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    if json_path:
        return service_account.Credentials.from_service_account_file(json_path, scopes=SCOPES)

    raise RuntimeError(
        "GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_JSON_PATH is required for election backup sheets"
    )


def translate_drive_create_error(exc: Exception) -> RuntimeError:
    message = str(exc)
    if "storageQuotaExceeded" in message or "storage quota" in message.casefold():
        if not has_oauth_credentials():
            return RuntimeError(SERVICE_ACCOUNT_STORAGE_ERROR)
        return RuntimeError(
            "Google Drive refused to create the election backup sheet because the "
            "authorized account is out of storage."
        )
    return RuntimeError(f"Could not create election backup Google Sheet: {message}")
