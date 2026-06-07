#!/usr/bin/env python3
"""Verify Google Drive OAuth credentials used for election backup sheets."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PREFERRED_PYTHON = ROOT / ".venv" / "bin" / "python3.14"
ENV_LOCAL = ROOT / ".env.local"


def ensure_supported_python() -> None:
    try:
        import google.auth  # noqa: F401
        return
    except ImportError:
        pass

    if PREFERRED_PYTHON.is_file() and Path(sys.executable).resolve() != PREFERRED_PYTHON.resolve():
        os.execv(str(PREFERRED_PYTHON), [str(PREFERRED_PYTHON), *sys.argv])

    print(
        f"Install dependencies for {sys.executable}:\n"
        f"  {sys.executable} -m pip install google-auth google-api-python-client",
        file=sys.stderr,
    )
    raise SystemExit(1)


def load_env_local() -> None:
    if not ENV_LOCAL.is_file():
        return
    for line in ENV_LOCAL.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    ensure_supported_python()
    load_env_local()

    from backend.app.integrations.election_backup_sheet.sheets_client import (
        oauth_configuration_error,
        oauth_client_credentials,
        verify_oauth_refresh,
        load_drive_credentials,
    )

    config_error = oauth_configuration_error()
    if config_error:
        print(f"FAIL: {config_error}", file=sys.stderr)
        return 1

    client_id, _ = oauth_client_credentials()
    folder_id = os.environ.get("ELECTION_BACKUP_DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        print("WARN: ELECTION_BACKUP_DRIVE_FOLDER_ID is not set.", file=sys.stderr)
    if not os.environ.get("GOOGLE_DRIVE_REFRESH_TOKEN", "").strip():
        print("FAIL: GOOGLE_DRIVE_REFRESH_TOKEN is not set.", file=sys.stderr)
        return 1

    print(f"OAuth client: {client_id}")
    print(f"Drive folder: {folder_id or '(not set)'}")

    credentials = load_drive_credentials()
    verify_oauth_refresh(credentials)
    print("OK: refresh token works.")

    if folder_id:
        from googleapiclient.discovery import build

        drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        folder = drive.files().get(fileId=folder_id, fields="id,name").execute()
        print(f"OK: can access folder {folder.get('name', folder_id)!r}.")

    print("\nCopy these exact env vars to Render → bellezea-elections-api:")
    print("  GOOGLE_DRIVE_OAUTH_CLIENT_ID")
    print("  GOOGLE_DRIVE_OAUTH_CLIENT_SECRET")
    print("  GOOGLE_DRIVE_REFRESH_TOKEN")
    print("  ELECTION_BACKUP_DRIVE_FOLDER_ID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
