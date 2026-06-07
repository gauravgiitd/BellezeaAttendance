#!/usr/bin/env python3
"""Background worker for per-election Google Sheet attendance backups."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.integrations.election_backup_sheet.worker import run_worker


if __name__ == "__main__":
    run_worker()
