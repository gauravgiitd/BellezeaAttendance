#!/usr/bin/env bash
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
export OFFICER_AUTH_DISABLED="${OFFICER_AUTH_DISABLED:-true}"
export AUTO_MIGRATE="${AUTO_MIGRATE:-true}"

if [[ -z "${RESIDENT_MASTER_CSV_URL:-}" && -z "${RESIDENT_MASTER_CSV_PATH:-}" ]]; then
  echo "Warning: set RESIDENT_MASTER_CSV_URL or RESIDENT_MASTER_CSV_PATH in .env.local before syncing residents." >&2
  echo "Copy .env.local.example to .env.local to get started." >&2
fi

exec "$ROOT/.venv/bin/uvicorn" backend.app.main:app --host 127.0.0.1 --port 8000 --reload
