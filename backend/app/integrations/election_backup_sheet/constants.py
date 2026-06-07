from __future__ import annotations

# Keep in sync with notify_election_backup_sync() in backend/db/schema.sql
REGRESSION_HARNESS_TITLE_PREFIX = "Regression Harness:"


def is_regression_harness_election(title: str | None) -> bool:
    return str(title or "").startswith(REGRESSION_HARNESS_TITLE_PREFIX)
