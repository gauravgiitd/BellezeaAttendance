#!/usr/bin/env bash
# Optional standalone runner. Normally the worker starts inside the API via ./scripts/start_local_api.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env.local" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env.local"
  set +a
fi

export DATABASE_URL="${DATABASE_URL:-postgresql://${USER}@127.0.0.1:5432/bellezea_elections}"

if [[ -z "${ELECTION_BACKUP_DRIVE_FOLDER_ID:-}" ]]; then
  echo "Error: set ELECTION_BACKUP_DRIVE_FOLDER_ID in .env.local" >&2
  echo "Copy .env.local.example to .env.local and add your Elections folder ID." >&2
  exit 1
fi

if [[ -z "${GOOGLE_SERVICE_ACCOUNT_JSON:-}" && -z "${GOOGLE_SERVICE_ACCOUNT_JSON_PATH:-}" ]]; then
  echo "Error: set GOOGLE_SERVICE_ACCOUNT_JSON_PATH (or GOOGLE_SERVICE_ACCOUNT_JSON) in .env.local" >&2
  exit 1
fi

if [[ -n "${GOOGLE_SERVICE_ACCOUNT_JSON_PATH:-}" && ! -f "${GOOGLE_SERVICE_ACCOUNT_JSON_PATH}" ]]; then
  echo "Error: service account file not found: ${GOOGLE_SERVICE_ACCOUNT_JSON_PATH}" >&2
  exit 1
fi

exec "$ROOT/.venv/bin/python" "$ROOT/scripts/election_backup_sheet_worker.py"
