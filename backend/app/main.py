import csv
import io
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .db import connection, initialize_schema
from .integrations.election_backup_sheet.worker import (
    start_in_background as start_election_backup_worker,
    stop_background as stop_election_backup_worker,
)


app = FastAPI(title="Nambiar Bellezea Election API")
DEFAULT_ATTENDANCE_MODES = ["Physical", "Virtual"]


def cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "*")
    if raw.strip() == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


OFFICER_EMAIL = os.environ.get("OFFICER_EMAIL", "bellezea.elections@gmail.com").casefold()


def require_officer(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if os.environ.get("OFFICER_AUTH_DISABLED", "").lower() in {"1", "true", "yes"}:
        return {"email": OFFICER_EMAIL}

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Officer login is required")

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(status_code=503, detail="Officer Google login is not configured")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Officer login is required")

    url = "https://oauth2.googleapis.com/tokeninfo?id_token=" + urllib.parse.quote(token)
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Officer login could not be verified") from exc

    email_verified = str(payload.get("email_verified", "")).casefold() == "true"
    if payload.get("aud") != client_id:
        raise HTTPException(status_code=401, detail="Officer login is for a different app")
    if not email_verified:
        raise HTTPException(status_code=403, detail="Google account email is not verified")
    if str(payload.get("email", "")).casefold() != OFFICER_EMAIL:
        raise HTTPException(status_code=403, detail="This Google account is not allowed for the officer console")
    return payload


class ElectionCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    quorum_percent: Decimal = Decimal("50.0")
    voting_enabled: bool = True
    attendance_modes: list[str] = Field(default_factory=lambda: DEFAULT_ATTENDANCE_MODES.copy())
    passing_rule: str = "simple_majority"
    passing_threshold_percent: Decimal | None = None
    include_defaulters_in_quorum: bool = False
    allow_defaulters_to_vote: bool = False


class ElectionUpdate(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    quorum_percent: Decimal = Decimal("50.0")
    voting_enabled: bool = True
    attendance_modes: list[str] = Field(default_factory=lambda: DEFAULT_ATTENDANCE_MODES.copy())
    passing_rule: str = "simple_majority"
    passing_threshold_percent: Decimal | None = None
    include_defaulters_in_quorum: bool = False
    allow_defaulters_to_vote: bool = False


class ElectionQuorumUpdate(BaseModel):
    quorum_percent: Decimal = Decimal("50.0")


class ElectionStatusUpdate(BaseModel):
    status: str
    voting_opens_at: datetime | None = None
    voting_closes_at: datetime | None = None


class QuestionChoiceCreate(BaseModel):
    choice_text: str = Field(min_length=1)
    image_url: str | None = None
    display_order: int = 0


class QuestionCreate(BaseModel):
    question_text: str = Field(min_length=1)
    image_url: str | None = None
    display_order: int = 0
    choices: list[QuestionChoiceCreate] = Field(min_length=2)


class QuestionUpdate(BaseModel):
    question_text: str = Field(min_length=1)
    image_url: str | None = None
    display_order: int = 0
    choices: list[QuestionChoiceCreate] = Field(min_length=2)


class ProxyCreate(BaseModel):
    election_id: str | None = None
    grantor_house_id: str
    proxy_holder_user_id: str
    proxy_holder_house_id: str
    proxy_holder_email: str = ""
    notes: str = ""


class DefaulterCreate(BaseModel):
    election_id: str
    house_id: str
    reason: str = ""


class AttendanceQrRequest(BaseModel):
    qr_raw_data: str
    method: str = "qr_scan"
    source: str = "officer"
    attendance_mode: str = "Physical"


class AttendanceManualRequest(BaseModel):
    user_id: str | None = None
    house_id: str | None = None
    name: str | None = None
    source: str = "officer"
    attendance_mode: str = "Physical"


class BallotAnswerRequest(BaseModel):
    question_id: str
    choice_id: str


class BallotSubmitRequest(BaseModel):
    submitted_by_user_id: str
    house_id: str
    answers: list[BallotAnswerRequest] = Field(min_length=1)


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_id(value: Any) -> str:
    text = clean(value)
    match = re.search(r"\d+", text)
    return str(int(match.group(0))) if match else text


def extract_passcode(qr_raw_data: str) -> str:
    first_token = clean(qr_raw_data).split(" ")[0] if clean(qr_raw_data) else ""
    match = re.search(r"\d+", first_token)
    return str(int(match.group(0))) if match else ""


def is_owner(user_type: str) -> bool:
    return "owner" in clean(user_type).casefold()


def normalize_attendance_modes(values: list[str] | str | None) -> list[str]:
    if isinstance(values, str):
        try:
            decoded = json.loads(values)
            values = decoded if isinstance(decoded, list) else []
        except json.JSONDecodeError:
            values = [values]
    modes: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        mode = clean(value)
        key = mode.casefold()
        if mode and key not in seen:
            modes.append(mode)
            seen.add(key)
    return modes or DEFAULT_ATTENDANCE_MODES.copy()


def normalize_attendance_mode(value: str | None, election: dict[str, Any]) -> str:
    modes = normalize_attendance_modes(election.get("attendance_modes"))
    requested = clean(value) or modes[0]
    for mode in modes:
        if mode.casefold() == requested.casefold():
            return mode
    raise HTTPException(status_code=400, detail="Attendance mode is not configured for this election")


ELECTION_STATUSES = {
    "draft",
    "attendance_open",
    "voting_open",
    "voting_closed",
    "results_published",
    "archived",
}

ATTENDANCE_METHODS = {"qr_scan", "qr_upload", "manual"}
PASSING_RULES = {"simple_majority", "two_thirds", "custom_threshold"}
RUN_STATUS_TRANSITIONS = {
    "draft": {"attendance_open"},
    "attendance_open": {"voting_open", "voting_closed"},
    "voting_open": {"voting_closed"},
    "voting_closed": {"attendance_open"},
}
ATTENDANCE_OPEN_STATUSES = {"attendance_open", "voting_open"}


def validate_choice(value: str, allowed: set[str], label: str) -> str:
    cleaned = clean(value)
    if cleaned not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid {label}: {cleaned}")
    return cleaned


def normalize_passing_threshold(rule: str, threshold: Decimal | None) -> Decimal | None:
    if rule != "custom_threshold":
        return None
    if threshold is None:
        raise HTTPException(status_code=400, detail="Custom passing threshold is required")
    if threshold <= 0 or threshold > 100:
        raise HTTPException(status_code=400, detail="Custom passing threshold must be between 0 and 100")
    return threshold


def csv_rows_from_text(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    return [dict(row) for row in reader]


def resident_from_row(row: dict[str, str]) -> dict[str, str]:
    user_id = normalize_id(row.get("User Id (Do Not Edit)"))
    house_id = normalize_id(row.get("House Id (Do Not Edit)"))
    if not user_id or not house_id:
        raise ValueError("Resident row is missing user ID or house ID")
    return {
        "user_id": user_id,
        "house_id": house_id,
        "house_no": clean(row.get("Flat") or row.get("House No")),
        "passcode": normalize_id(row.get("Passcode")),
        "name": clean(row.get("Name") or row.get("Resident Name")),
        "user_type": clean(row.get("User Type") or row.get("Resident Type")),
        "status": clean(row.get("Status") or "Active"),
        "mobile_no": clean(row.get("Mobile No")),
        "email": clean(row.get("Email")),
        "raw": row,
    }


def upsert_residents(rows: list[dict[str, str]], source: str) -> dict[str, int]:
    imported = 0
    skipped = 0
    imported_user_ids: list[str] = []
    imported_house_ids: list[str] = []
    with connection() as conn:
        with conn.cursor() as cur:
            for row in rows:
                try:
                    resident = resident_from_row(row)
                except ValueError:
                    skipped += 1
                    continue
                if not resident["name"] or not resident["house_no"]:
                    skipped += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO villas (house_id, house_no, updated_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (house_id)
                    DO UPDATE SET house_no = EXCLUDED.house_no, updated_at = now()
                    """,
                    (resident["house_id"], resident["house_no"]),
                )
                cur.execute(
                    """
                    INSERT INTO residents (
                      user_id, house_id, passcode, name, user_type, status,
                      mobile_no, email, raw_payload, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now())
                    ON CONFLICT (user_id, house_id)
                    DO UPDATE SET
                      passcode = EXCLUDED.passcode,
                      name = EXCLUDED.name,
                      user_type = EXCLUDED.user_type,
                      status = EXCLUDED.status,
                      mobile_no = EXCLUDED.mobile_no,
                      email = EXCLUDED.email,
                      raw_payload = EXCLUDED.raw_payload,
                      updated_at = now()
                    """,
                    (
                        resident["user_id"],
                        resident["house_id"],
                        resident["passcode"],
                        resident["name"],
                        resident["user_type"],
                        resident["status"],
                        resident["mobile_no"],
                        resident["email"],
                        psycopg_json(resident["raw"]),
                    ),
                )
                imported += 1
                imported_user_ids.append(resident["user_id"])
                imported_house_ids.append(resident["house_id"])

            cleanup = cleanup_residents_after_import(cur, imported_user_ids, imported_house_ids)
            cur.execute(
                """
                INSERT INTO resident_source_syncs (source, row_count, metadata)
                VALUES (%s, %s, %s::jsonb)
                """,
                (
                    source,
                    imported,
                    psycopg_json({"skipped": skipped, **cleanup}),
                ),
            )
        conn.commit()
    return {"imported": imported, "skipped": skipped, **cleanup}


def cleanup_residents_after_import(
    cur,
    imported_user_ids: list[str],
    imported_resident_house_ids: list[str],
) -> dict[str, int]:
    if not imported_user_ids:
        return {"removed_residents": 0, "removed_villas": 0}

    imported_house_id_list = sorted(set(imported_resident_house_ids))
    cur.execute(
        """
        DELETE FROM residents r
        WHERE NOT EXISTS (
            SELECT 1
            FROM unnest(%s::text[], %s::text[]) AS i(user_id, house_id)
            WHERE i.user_id = r.user_id
              AND i.house_id = r.house_id
        )
        """,
        (imported_user_ids, imported_resident_house_ids),
    )
    removed_residents = cur.rowcount

    cur.execute(
        """
        DELETE FROM villas v
        WHERE v.house_id <> ALL(%s)
          AND NOT EXISTS (SELECT 1 FROM residents r WHERE r.house_id = v.house_id)
          AND NOT EXISTS (SELECT 1 FROM attendance_records ar WHERE ar.house_id = v.house_id)
          AND NOT EXISTS (SELECT 1 FROM villa_representations vr WHERE vr.house_id = v.house_id)
          AND NOT EXISTS (SELECT 1 FROM ballots b WHERE b.house_id = v.house_id)
          AND NOT EXISTS (SELECT 1 FROM proxies p WHERE p.grantor_house_id = v.house_id OR p.proxy_holder_house_id = v.house_id)
          AND NOT EXISTS (SELECT 1 FROM defaulters d WHERE d.house_id = v.house_id)
        """,
        (imported_house_id_list,),
    )
    removed_villas = cur.rowcount
    return {"removed_residents": removed_residents, "removed_villas": removed_villas}


def psycopg_json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def resident_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "house_id": row["house_id"],
        "house_no": row["house_no"],
        "name": row["name"],
        "user_type": row["user_type"],
        "status": row["status"],
    }


def election_public(row: dict[str, Any]) -> dict[str, Any]:
    represented_villas = int(row.get("represented_villas", 0) or 0)
    eligible_villas = int(row.get("eligible_villas", 0) or 0)
    quorum_percent = float(row["quorum_percent"])
    quorum_reached = bool(eligible_villas and (represented_villas / eligible_villas * 100) >= quorum_percent)
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "quorum_percent": quorum_percent,
        "voting_enabled": row["voting_enabled"],
        "attendance_modes": normalize_attendance_modes(row.get("attendance_modes")),
        "passing_rule": row["passing_rule"],
        "passing_threshold_percent": (
            float(row["passing_threshold_percent"]) if row["passing_threshold_percent"] is not None else None
        ),
        "include_defaulters_in_quorum": row["include_defaulters_in_quorum"],
        "allow_defaulters_to_vote": row["allow_defaulters_to_vote"],
        "voting_opens_at": row["voting_opens_at"],
        "voting_closes_at": row["voting_closes_at"],
        "represented_villas": represented_villas,
        "eligible_villas": eligible_villas,
        "quorum_reached": quorum_reached,
        "question_count": int(row.get("question_count", 0) or 0),
    }


def fetch_election_summary(cur, election_id: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT e.*,
          COUNT(DISTINCT vr.house_id) AS represented_villas,
          COUNT(DISTINCT q.id) AS question_count,
          (
            SELECT COUNT(*)
            FROM villas v
            WHERE e.include_defaulters_in_quorum
               OR NOT EXISTS (
                 SELECT 1
                 FROM defaulters d
                 WHERE d.election_id = e.id
                   AND d.house_id = v.house_id
                   AND d.status = 'active'
               )
          ) AS eligible_villas
        FROM elections e
        LEFT JOIN villa_representations vr ON vr.election_id = e.id
        LEFT JOIN election_questions q ON q.election_id = e.id
        WHERE e.id = %s
        GROUP BY e.id
        """,
        (election_id,),
    )
    return cur.fetchone()


def fetch_questions(cur, election_id: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT q.*, c.id AS choice_id, c.choice_text, c.image_url AS choice_image_url, c.display_order AS choice_order
        FROM election_questions q
        LEFT JOIN election_choices c ON c.question_id = q.id
        WHERE q.election_id = %s
        ORDER BY q.display_order, q.created_at, c.display_order, c.created_at
        """,
        (election_id,),
    )
    questions: dict[str, dict[str, Any]] = {}
    for row in cur.fetchall():
        question_id = str(row["id"])
        if question_id not in questions:
            questions[question_id] = {
                "id": question_id,
                "question_text": row["question_text"],
                "image_url": row["image_url"],
                "display_order": row["display_order"],
                "choices": [],
            }
        if row["choice_id"]:
            questions[question_id]["choices"].append(
                {
                    "id": str(row["choice_id"]),
                    "choice_text": row["choice_text"],
                    "image_url": row["choice_image_url"],
                    "display_order": row["choice_order"],
                }
            )
    return list(questions.values())


def ensure_election_config_editable(cur, election_id: str) -> dict[str, Any]:
    cur.execute("SELECT * FROM elections WHERE id = %s", (election_id,))
    election = cur.fetchone()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    if election["status"] != "draft":
        raise HTTPException(status_code=409, detail="Election setup is locked after attendance starts")
    return election


def ensure_questions_editable(cur, election_id: str) -> dict[str, Any]:
    cur.execute("SELECT * FROM elections WHERE id = %s", (election_id,))
    election = cur.fetchone()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    if not election["voting_enabled"]:
        raise HTTPException(status_code=409, detail="Enable voting before managing questions")
    if election["status"] in {"voting_open", "voting_closed", "results_published", "archived"}:
        raise HTTPException(status_code=409, detail="Questions are locked once voting starts")
    return election


def ensure_proxy_editable(cur, election_id: str | None) -> None:
    if not election_id:
        return
    cur.execute("SELECT status FROM elections WHERE id = %s", (election_id,))
    election = cur.fetchone()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    if election["status"] not in {"draft", "attendance_open"}:
        raise HTTPException(status_code=409, detail="Proxy changes are locked after voting starts")


def ensure_status_transition_allowed(cur, election_id: str, next_status: str) -> dict[str, Any]:
    election = fetch_election_summary(cur, election_id)
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")

    current_status = election["status"]
    if next_status == current_status:
        return election
    if next_status not in RUN_STATUS_TRANSITIONS.get(current_status, set()):
        raise HTTPException(status_code=409, detail=f"Cannot move election from {current_status} to {next_status}")

    if current_status == "draft" and next_status == "attendance_open" and election["voting_enabled"]:
        cur.execute("SELECT COUNT(*) AS question_count FROM election_questions WHERE election_id = %s", (election_id,))
        if not cur.fetchone()["question_count"]:
            raise HTTPException(status_code=409, detail="Add at least one question before starting attendance")
    if next_status == "voting_open" and not election["voting_enabled"]:
        raise HTTPException(status_code=409, detail="Voting is disabled for this election")
    if next_status == "voting_closed" and current_status == "attendance_open" and election["voting_enabled"]:
        raise HTTPException(status_code=409, detail="Open voting before closing a voting-enabled election")
    if current_status == "voting_closed" and next_status == "attendance_open" and election["voting_enabled"]:
        raise HTTPException(status_code=409, detail="Attendance can be reopened only for attendance-only elections")
    if next_status == "voting_open" and not election_public(election)["quorum_reached"]:
        raise HTTPException(status_code=409, detail="Quorum must be reached before voting opens")
    return election


@app.on_event("startup")
def on_startup() -> None:
    if os.environ.get("AUTO_MIGRATE", "true").lower() not in {"0", "false", "no"}:
        initialize_schema()
    start_election_backup_worker()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_election_backup_worker()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/public-config")
def public_config() -> dict[str, str]:
    return {
        "googleClientId": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "officerEmail": OFFICER_EMAIL,
        "officerAuthDisabled": "true" if os.environ.get("OFFICER_AUTH_DISABLED", "").lower() in {"1", "true", "yes"} else "false",
    }


@app.get("/api/officer/me")
def officer_me(officer: dict[str, Any] = Depends(require_officer)) -> dict[str, Any]:
    return {
        "email": officer.get("email", OFFICER_EMAIL),
        "name": officer.get("name", ""),
        "picture": officer.get("picture", ""),
    }


@app.post("/api/admin/migrate", dependencies=[Depends(require_officer)])
def migrate() -> dict[str, str]:
    if not initialize_schema(skip_on_lock_timeout=False):
        raise HTTPException(
            status_code=503,
            detail="Schema migration could not acquire database locks. Retry when traffic is quiet.",
        )
    return {"status": "migrated"}


@app.post("/api/residents/sync-csv", dependencies=[Depends(require_officer)])
async def sync_residents_from_csv(file: UploadFile = File(...)) -> dict[str, int]:
    text = (await file.read()).decode("utf-8-sig")
    return upsert_residents(csv_rows_from_text(text), source=file.filename or "uploaded_csv")


@app.post("/api/residents/sync-from-google-sheet", dependencies=[Depends(require_officer)])
def sync_residents_from_google_sheet(csv_url: str | None = None) -> dict[str, int]:
    return sync_residents_from_google_sheet_url(csv_url)


@app.get("/api/residents/sync-from-google-sheet", dependencies=[Depends(require_officer)])
def sync_residents_from_google_sheet_browser(csv_url: str | None = None) -> dict[str, int]:
    return sync_residents_from_google_sheet_url(csv_url)


def fetch_remote_text(url: str, timeout: int = 30) -> str:
    try:
        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(url, timeout=timeout, context=context) as response:
            return response.read().decode("utf-8-sig")
    except urllib.error.URLError as exc:
        return fetch_remote_text_with_curl(url, timeout, exc)


def fetch_remote_text_with_curl(url: str, timeout: int, original_error: urllib.error.URLError | None = None) -> str:
    import shutil
    import subprocess

    if not shutil.which("curl"):
        reason = original_error.reason if original_error and original_error.reason else str(original_error or "download failed")
        raise HTTPException(status_code=502, detail=f"Could not download resident master CSV: {reason}") from original_error

    result = subprocess.run(
        ["curl", "-fsSL", "--max-time", str(timeout), url],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        detail = stderr or "curl failed to download resident master CSV"
        raise HTTPException(status_code=502, detail=detail) from original_error
    return result.stdout.decode("utf-8-sig")


def sync_residents_from_google_sheet_url(csv_url: str | None = None) -> dict[str, int]:
    url = csv_url or os.environ.get("RESIDENT_MASTER_CSV_URL")
    if url:
        text = fetch_remote_text(url)
        return upsert_residents(csv_rows_from_text(text), source=url)

    local_path = os.environ.get("RESIDENT_MASTER_CSV_PATH")
    if local_path:
        path = Path(local_path).expanduser()
        if not path.is_file():
            raise HTTPException(status_code=400, detail=f"Resident master CSV file not found: {path}")
        text = path.read_text(encoding="utf-8-sig")
        return upsert_residents(csv_rows_from_text(text), source=str(path))

    raise HTTPException(
        status_code=400,
        detail="csv_url, RESIDENT_MASTER_CSV_URL, or RESIDENT_MASTER_CSV_PATH is required",
    )


@app.get("/api/residents/sync-status", dependencies=[Depends(require_officer)])
def resident_sync_status() -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS residents FROM residents")
            residents = cur.fetchone()["residents"]
            cur.execute("SELECT COUNT(*) AS villas FROM villas")
            villas = cur.fetchone()["villas"]
            cur.execute("SELECT * FROM resident_source_syncs ORDER BY synced_at DESC LIMIT 1")
            latest = cur.fetchone()
    return {"residents": residents, "villas": villas, "latest_sync": latest}


@app.get("/api/resident-directory", dependencies=[Depends(require_officer)])
def resident_directory() -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT v.house_id, v.house_no,
                  COALESCE(
                    jsonb_agg(
                        jsonb_build_object(
                          'user_id', r.user_id,
                          'house_id', r.house_id,
                          'name', r.name,
                          'user_type', r.user_type,
                          'status', r.status
                      )
                      ORDER BY r.name
                    ) FILTER (WHERE r.user_id IS NOT NULL),
                    '[]'::jsonb
                  ) AS owners
                FROM villas v
                LEFT JOIN residents r
                  ON r.house_id = v.house_id
                 AND position('owner' in lower(r.user_type)) > 0
                GROUP BY v.house_id, v.house_no
                ORDER BY v.house_no
                """
            )
            rows = cur.fetchall()
    return [
        {
            "house_id": row["house_id"],
            "house_no": row["house_no"],
            "owners": row["owners"],
        }
        for row in rows
    ]


@app.post("/api/auth/qr-login")
def qr_login(payload: AttendanceQrRequest) -> dict[str, Any]:
    passcode = extract_passcode(payload.qr_raw_data)
    if not passcode:
        raise HTTPException(status_code=400, detail="Could not extract passcode from QR")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.*, v.house_no
                FROM residents r
                JOIN villas v ON v.house_id = r.house_id
                WHERE r.passcode = %s
                ORDER BY position('owner' in lower(r.user_type)) DESC, r.updated_at DESC
                LIMIT 1
                """,
                (passcode,),
            )
            resident = cur.fetchone()
    if not resident:
        raise HTTPException(status_code=404, detail="No resident matched this passcode")
    if not is_owner(resident["user_type"]):
        raise HTTPException(status_code=403, detail="Only owner-type residents can attend or vote")
    return {"resident": resident_public(resident)}


@app.get("/api/voters/{user_id}/dashboard")
def voter_dashboard(user_id: str) -> dict[str, Any]:
    normalized_user_id = normalize_id(user_id)
    with connection() as conn:
        with conn.cursor() as cur:
            resident = fetch_resident_by_user_id(cur, normalized_user_id)
            if not resident:
                raise HTTPException(status_code=404, detail="Voter was not found")
            if not is_owner(resident["user_type"]):
                raise HTTPException(status_code=403, detail="Only owner-type residents can vote")
            cur.execute(
                """
                SELECT id
                FROM elections
                WHERE status IN ('attendance_open', 'voting_open', 'voting_closed', 'results_published')
                ORDER BY created_at DESC
                """
            )
            election_ids = [str(row["id"]) for row in cur.fetchall()]
            elections = []
            for election_id in election_ids:
                election = fetch_election_summary(cur, election_id)
                if not election:
                    continue
                questions = fetch_questions(cur, election_id)
                represented_houses = voter_represented_houses(cur, election_id, normalized_user_id)
                cur.execute("SELECT COUNT(*) AS voted_villas FROM ballots WHERE election_id = %s", (election_id,))
                voted_villas = cur.fetchone()["voted_villas"]
                election_payload = {
                    "election": election_public(election),
                    "represented_houses": represented_houses,
                    "voted_villas": voted_villas,
                    "questions": questions,
                    "results": None,
                }
                if election["status"] in {"voting_closed", "results_published", "archived"}:
                    election_payload["results"] = calculate_results(cur, election_id, questions, election)
                elections.append(election_payload)
    return {"resident": resident_public(resident), "elections": elections}


@app.get("/api/elections", dependencies=[Depends(require_officer)])
def list_elections() -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*,
                  COUNT(DISTINCT vr.house_id) AS represented_villas,
                  COUNT(DISTINCT q.id) AS question_count,
                  (
                    SELECT COUNT(*)
                    FROM villas v
                    WHERE e.include_defaulters_in_quorum
                       OR NOT EXISTS (
                         SELECT 1
                         FROM defaulters d
                         WHERE d.election_id = e.id
                           AND d.house_id = v.house_id
                           AND d.status = 'active'
                       )
                  ) AS eligible_villas
                FROM elections e
                LEFT JOIN villa_representations vr ON vr.election_id = e.id
                LEFT JOIN election_questions q ON q.election_id = e.id
                GROUP BY e.id
                ORDER BY e.created_at DESC
                """
            )
            return [election_public(row) for row in cur.fetchall()]


@app.post("/api/elections", dependencies=[Depends(require_officer)])
def create_election(payload: ElectionCreate) -> dict[str, Any]:
    passing_rule = validate_choice(payload.passing_rule, PASSING_RULES, "passing rule")
    passing_threshold = normalize_passing_threshold(passing_rule, payload.passing_threshold_percent)
    attendance_modes = normalize_attendance_modes(payload.attendance_modes)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO elections (
                  title, description, quorum_percent, voting_enabled, attendance_modes, passing_rule, passing_threshold_percent,
                  include_defaulters_in_quorum, allow_defaulters_to_vote
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    payload.title,
                    payload.description,
                    payload.quorum_percent,
                    payload.voting_enabled,
                    json.dumps(attendance_modes),
                    passing_rule,
                    passing_threshold,
                    payload.include_defaulters_in_quorum,
                    payload.allow_defaulters_to_vote,
                ),
            )
            created = cur.fetchone()
            election = fetch_election_summary(cur, str(created["id"]))
        conn.commit()
    return election_public(election)


@app.get("/api/elections/{election_id}", dependencies=[Depends(require_officer)])
def get_election(election_id: str) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            election = fetch_election_summary(cur, election_id)
            questions = fetch_questions(cur, election_id) if election else []
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    response = election_public(election)
    response["questions"] = questions
    return response


@app.patch("/api/elections/{election_id}", dependencies=[Depends(require_officer)])
def update_election(election_id: str, payload: ElectionUpdate) -> dict[str, Any]:
    passing_rule = validate_choice(payload.passing_rule, PASSING_RULES, "passing rule")
    passing_threshold = normalize_passing_threshold(passing_rule, payload.passing_threshold_percent)
    attendance_modes = normalize_attendance_modes(payload.attendance_modes)
    with connection() as conn:
        with conn.cursor() as cur:
            ensure_election_config_editable(cur, election_id)
            cur.execute(
                """
                UPDATE elections
                SET title = %s,
                    description = %s,
                    quorum_percent = %s,
                    voting_enabled = %s,
                    attendance_modes = %s::jsonb,
                    passing_rule = %s,
                    passing_threshold_percent = %s,
                    include_defaulters_in_quorum = %s,
                    allow_defaulters_to_vote = %s,
                    updated_at = now()
                WHERE id = %s
                RETURNING id
                """,
                (
                    clean(payload.title),
                    clean(payload.description),
                    payload.quorum_percent,
                    payload.voting_enabled,
                    json.dumps(attendance_modes),
                    passing_rule,
                    passing_threshold,
                    payload.include_defaulters_in_quorum,
                    payload.allow_defaulters_to_vote,
                    election_id,
                ),
            )
            updated = cur.fetchone()
            election = fetch_election_summary(cur, election_id) if updated else None
        conn.commit()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    return election_public(election)


@app.patch("/api/elections/{election_id}/quorum", dependencies=[Depends(require_officer)])
def update_election_quorum(election_id: str, payload: ElectionQuorumUpdate) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM elections WHERE id = %s", (election_id,))
            election = cur.fetchone()
            if not election:
                raise HTTPException(status_code=404, detail="Election not found")
            if election["status"] in {"voting_open", "voting_closed", "results_published", "archived"}:
                raise HTTPException(status_code=409, detail="Quorum is locked after voting starts")
            cur.execute(
                """
                UPDATE elections
                SET quorum_percent = %s,
                    updated_at = now()
                WHERE id = %s
                RETURNING id
                """,
                (payload.quorum_percent, election_id),
            )
            updated = cur.fetchone()
            election = fetch_election_summary(cur, election_id) if updated else None
        conn.commit()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    return election_public(election)


@app.delete("/api/elections/{election_id}", dependencies=[Depends(require_officer)])
def delete_election(election_id: str) -> dict[str, str]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM elections WHERE id = %s RETURNING id", (election_id,))
            deleted = cur.fetchone()
        conn.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Election not found")
    return {"status": "deleted"}


@app.post("/api/elections/{election_id}/questions", dependencies=[Depends(require_officer)])
def add_question(election_id: str, payload: QuestionCreate) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            ensure_questions_editable(cur, election_id)
            cur.execute(
                """
                INSERT INTO election_questions (
                  election_id, question_text, image_url, passing_rule,
                  passing_threshold_percent, display_order
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    election_id,
                    clean(payload.question_text),
                    clean(payload.image_url),
                    "simple_majority",
                    None,
                    payload.display_order,
                ),
            )
            question = cur.fetchone()
            for index, choice in enumerate(payload.choices):
                cur.execute(
                    """
                    INSERT INTO election_choices (question_id, choice_text, image_url, display_order)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        question["id"],
                        clean(choice.choice_text),
                        clean(choice.image_url),
                        choice.display_order or index,
                    ),
                )
        conn.commit()
    with connection() as conn:
        with conn.cursor() as cur:
            questions = fetch_questions(cur, election_id)
    return next(item for item in questions if item["id"] == str(question["id"]))


@app.patch("/api/elections/{election_id}/questions/{question_id}", dependencies=[Depends(require_officer)])
def update_question(election_id: str, question_id: str, payload: QuestionUpdate) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            ensure_questions_editable(cur, election_id)
            cur.execute(
                """
                UPDATE election_questions
                SET question_text = %s,
                    image_url = %s,
                    passing_rule = %s,
                    passing_threshold_percent = %s,
                    display_order = %s,
                    updated_at = now()
                WHERE id = %s AND election_id = %s
                RETURNING id
                """,
                (
                    clean(payload.question_text),
                    clean(payload.image_url),
                    "simple_majority",
                    None,
                    payload.display_order,
                    question_id,
                    election_id,
                ),
            )
            question = cur.fetchone()
            if not question:
                raise HTTPException(status_code=404, detail="Question not found")
            cur.execute("DELETE FROM election_choices WHERE question_id = %s", (question_id,))
            for index, choice in enumerate(payload.choices):
                cur.execute(
                    """
                    INSERT INTO election_choices (question_id, choice_text, image_url, display_order)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        question_id,
                        clean(choice.choice_text),
                        clean(choice.image_url),
                        choice.display_order or index,
                    ),
                )
        conn.commit()
    with connection() as conn:
        with conn.cursor() as cur:
            questions = fetch_questions(cur, election_id)
    return next(item for item in questions if item["id"] == question_id)


@app.delete("/api/elections/{election_id}/questions/{question_id}", dependencies=[Depends(require_officer)])
def delete_question(election_id: str, question_id: str) -> dict[str, str]:
    with connection() as conn:
        with conn.cursor() as cur:
            ensure_questions_editable(cur, election_id)
            cur.execute(
                """
                DELETE FROM election_questions
                WHERE id = %s AND election_id = %s
                RETURNING id
                """,
                (question_id, election_id),
            )
            deleted = cur.fetchone()
        conn.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Question not found")
    return {"status": "deleted"}


@app.post("/api/elections/{election_id}/status", dependencies=[Depends(require_officer)])
def update_election_status(election_id: str, payload: ElectionStatusUpdate) -> dict[str, Any]:
    status = validate_choice(payload.status, ELECTION_STATUSES, "election status")
    with connection() as conn:
        with conn.cursor() as cur:
            ensure_status_transition_allowed(cur, election_id, status)
            cur.execute(
                """
                UPDATE elections
                SET status = %s,
                    voting_opens_at = COALESCE(%s, voting_opens_at),
                    voting_closes_at = COALESCE(%s, voting_closes_at),
                    updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (status, payload.voting_opens_at, payload.voting_closes_at, election_id),
            )
            updated = cur.fetchone()
            election = fetch_election_summary(cur, election_id) if updated else None
        conn.commit()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    return election_public(election)


@app.post("/api/elections/{election_id}/restart-voting", dependencies=[Depends(require_officer)])
def restart_voting(election_id: str) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM elections WHERE id = %s", (election_id,))
            election = cur.fetchone()
            if not election:
                raise HTTPException(status_code=404, detail="Election not found")
            if not election["voting_enabled"]:
                raise HTTPException(status_code=409, detail="Voting is disabled for this election")
            if election["status"] not in {"voting_open", "voting_closed", "results_published"}:
                raise HTTPException(status_code=409, detail="Voting can be restarted only after voting has opened")
            cur.execute("DELETE FROM ballots WHERE election_id = %s", (election_id,))
            cur.execute(
                """
                UPDATE elections
                SET status = 'voting_open',
                    voting_opens_at = now(),
                    voting_closes_at = NULL,
                    updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (election_id,),
            )
            updated = cur.fetchone()
            election = fetch_election_summary(cur, election_id) if updated else None
        conn.commit()
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    return election_public(election)


@app.post("/api/elections/{election_id}/attendance/qr", dependencies=[Depends(require_officer)])
def mark_qr_attendance(election_id: str, payload: AttendanceQrRequest) -> dict[str, Any]:
    passcode = extract_passcode(payload.qr_raw_data)
    if not passcode:
        raise HTTPException(status_code=400, detail="Could not extract passcode from QR")
    return mark_attendance(
        election_id=election_id,
        method=payload.method,
        source=payload.source,
        attendance_mode=payload.attendance_mode,
        raw_qr_data=payload.qr_raw_data,
        passcode=passcode,
    )


@app.post("/api/elections/{election_id}/attendance/manual", dependencies=[Depends(require_officer)])
def mark_manual_attendance(election_id: str, payload: AttendanceManualRequest) -> dict[str, Any]:
    return mark_attendance(
        election_id=election_id,
        method="manual",
        source=payload.source,
        attendance_mode=payload.attendance_mode,
        user_id=payload.user_id,
        house_id=payload.house_id,
        name=payload.name,
    )


@app.get("/api/elections/{election_id}/attendance/dashboard", dependencies=[Depends(require_officer)])
def attendance_dashboard(election_id: str) -> dict[str, Any]:
    return attendance_dashboard_payload(election_id)


@app.delete("/api/elections/{election_id}/attendance/{house_id}", dependencies=[Depends(require_officer)])
def remove_actual_attendance(election_id: str, house_id: str) -> dict[str, Any]:
    normalized_house_id = normalize_id(house_id)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM elections WHERE id = %s", (election_id,))
            election = cur.fetchone()
            if not election:
                raise HTTPException(status_code=404, detail="Election not found")
            if election["status"] not in ATTENDANCE_OPEN_STATUSES:
                raise HTTPException(status_code=409, detail="Attendance can be removed only during Attendance or Voting")

            cur.execute(
                """
                SELECT id
                FROM attendance_records
                WHERE election_id = %s
                  AND house_id = %s
                """,
                (election_id, normalized_house_id),
            )
            attendance_ids = [row["id"] for row in cur.fetchall()]
            if not attendance_ids:
                raise HTTPException(status_code=404, detail="Actual attendance was not found for this villa")

            cur.execute(
                """
                SELECT DISTINCT house_id
                FROM villa_representations
                WHERE election_id = %s
                  AND (
                    source_attendance_record_id = ANY(%s)
                    OR (house_id = %s AND representation_type = 'self')
                  )
                """,
                (election_id, attendance_ids, normalized_house_id),
            )
            represented_house_ids = [row["house_id"] for row in cur.fetchall()]
            if represented_house_ids:
                cur.execute(
                    """
                    SELECT COUNT(*) AS ballot_count
                    FROM ballots
                    WHERE election_id = %s
                      AND house_id = ANY(%s)
                    """,
                    (election_id, represented_house_ids),
                )
                if int(cur.fetchone()["ballot_count"] or 0):
                    raise HTTPException(
                        status_code=409,
                        detail="Cannot remove attendance after votes have been submitted for this villa or its proxies",
                    )

            cur.execute(
                """
                DELETE FROM villa_representations
                WHERE election_id = %s
                  AND (
                    source_attendance_record_id = ANY(%s)
                    OR (house_id = %s AND representation_type = 'self')
                  )
                RETURNING house_id, representation_type
                """,
                (election_id, attendance_ids, normalized_house_id),
            )
            removed_representations = cur.fetchall()

            cur.execute(
                """
                DELETE FROM attendance_records
                WHERE election_id = %s
                  AND house_id = %s
                RETURNING id
                """,
                (election_id, normalized_house_id),
            )
            removed_attendance = cur.fetchall()
        conn.commit()
    return {
        "removed_attendance_records": len(removed_attendance),
        "removed_representations": len(removed_representations),
        "removed_proxy_villas": sum(1 for row in removed_representations if row["representation_type"] == "proxy"),
    }


@app.get("/api/public/attendance-board")
def public_attendance_board() -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM elections
                WHERE status = 'attendance_open'
                ORDER BY created_at DESC
                """
            )
            election_ids = [str(row["id"]) for row in cur.fetchall()]
    return {
        "elections": [attendance_dashboard_payload(election_id) for election_id in election_ids],
    }


def attendance_dashboard_payload(election_id: str) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            election = fetch_election_summary(cur, election_id)
            if not election:
                raise HTTPException(status_code=404, detail="Election not found")
            attendees = attendance_villa_rows(cur, election)
            excluded_from_quorum = 0
            if not election["include_defaulters_in_quorum"]:
                cur.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM defaulters
                    WHERE election_id = %s
                      AND status = 'active'
                    """,
                    (election_id,),
                )
                excluded_from_quorum = int(cur.fetchone()["count"] or 0)
    election_data = election_public(election)
    represented = election_data["represented_villas"]
    eligible = election_data["eligible_villas"]
    return {
        "election": election_data,
        "totalVillas": eligible,
        "excludedFromQuorum": excluded_from_quorum,
        "representedVillas": represented,
        "representationPct": (represented / eligible * 100) if eligible else 0,
        "attendees": attendees,
    }


@app.get("/api/elections/{election_id}/reports/actual-attendees.csv", dependencies=[Depends(require_officer)])
def actual_attendee_report(election_id: str) -> Response:
    with connection() as conn:
        with conn.cursor() as cur:
            election = fetch_election_summary(cur, election_id)
            if not election:
                raise HTTPException(status_code=404, detail="Election not found")
            cur.execute(
                """
                SELECT DISTINCT
                  v.house_no AS flat,
                  r.name,
                  ar.attendance_mode,
                  r.user_id,
                  r.house_id
                FROM attendance_records ar
                JOIN residents r
                  ON r.user_id = ar.resident_user_id
                 AND r.house_id = ar.house_id
                JOIN villas v ON v.house_id = ar.house_id
                WHERE ar.election_id = %s
                  AND EXISTS (
                    SELECT 1
                    FROM villa_representations vr
                    WHERE vr.election_id = ar.election_id
                      AND vr.house_id = ar.house_id
                      AND vr.representation_type = 'self'
                  )
                ORDER BY v.house_no, r.name
                """,
                (election_id,),
            )
            rows = cur.fetchall()
    content = csv_text(
        ["Flat", "Name", "Attendance Mode", "User Id (Do Not Edit)", "House Id (Do Not Edit)"],
        [[row["flat"], row["name"], row["attendance_mode"], row["user_id"], row["house_id"]] for row in rows],
    )
    return csv_response(content, f"{slugify(election['title'])}-actual-attendees-mygate.csv")


@app.get("/api/elections/{election_id}/reports/proxy-holder-emails.csv", dependencies=[Depends(require_officer)])
def proxy_holder_email_report(election_id: str) -> Response:
    with connection() as conn:
        with conn.cursor() as cur:
            election = fetch_election_summary(cur, election_id)
            if not election:
                raise HTTPException(status_code=404, detail="Election not found")
            cur.execute(
                """
                SELECT DISTINCT
                  gv.house_no AS grantor_villa,
                  hv.house_no AS proxy_holder_villa,
                  r.name AS proxy_holder_name,
                  ar.attendance_mode AS attendance_mode,
                  p.proxy_holder_email AS proxy_holder_email
                FROM proxies p
                JOIN villas gv ON gv.house_id = p.grantor_house_id
                JOIN villas hv ON hv.house_id = p.proxy_holder_house_id
                JOIN residents r
                  ON r.user_id = p.proxy_holder_user_id
                 AND r.house_id = p.proxy_holder_house_id
                JOIN attendance_records ar
                  ON ar.election_id = p.election_id
                 AND ar.resident_user_id = p.proxy_holder_user_id
                 AND ar.house_id = p.proxy_holder_house_id
                JOIN villa_representations vr
                  ON vr.election_id = p.election_id
                 AND vr.house_id = p.grantor_house_id
                 AND vr.represented_by_user_id = p.proxy_holder_user_id
                 AND vr.representation_type = 'proxy'
                WHERE p.election_id = %s
                  AND p.status = 'active'
                  AND NULLIF(trim(p.proxy_holder_email), '') IS NOT NULL
                ORDER BY gv.house_no, hv.house_no, r.name, ar.attendance_mode, p.proxy_holder_email
                """,
                (election_id,),
            )
            rows = cur.fetchall()
    content = csv_text(
        ["Grantor Villa", "Proxy Holder Villa", "Proxy Holder Name", "Attendance Mode", "Proxy Holder Email"],
        [
            [
                row["grantor_villa"],
                row["proxy_holder_villa"],
                row["proxy_holder_name"],
                row["attendance_mode"],
                row["proxy_holder_email"],
            ]
            for row in rows
        ],
    )
    return csv_response(content, f"{slugify(election['title'])}-proxy-holder-emails-google-survey.csv")


def csv_text(headers: list[str], rows: list[list[Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()


def csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", clean(value).casefold()).strip("-")
    return slug or "election"


@app.post("/api/proxies", dependencies=[Depends(require_officer)])
def create_proxy(payload: ProxyCreate) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            ensure_proxy_editable(cur, payload.election_id)
            election = None
            if payload.election_id:
                cur.execute("SELECT * FROM elections WHERE id = %s", (payload.election_id,))
                election = cur.fetchone()
                if not election:
                    raise HTTPException(status_code=404, detail="Election not found")
            cur.execute("SELECT house_id FROM villas WHERE house_id = %s", (normalize_id(payload.grantor_house_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Grantor villa was not found")
            proxy_holder = fetch_resident_by_user_id(
                cur,
                payload.proxy_holder_user_id,
                payload.proxy_holder_house_id,
            )
            if not proxy_holder:
                raise HTTPException(status_code=404, detail="Proxy holder was not found")
            if not is_owner(proxy_holder["user_type"]):
                raise HTTPException(status_code=403, detail="Proxy holder must be an owner-type resident")
            cur.execute(
                """
                SELECT 1
                FROM proxies
                WHERE grantor_house_id = %s
                  AND COALESCE(election_id, '00000000-0000-0000-0000-000000000000'::uuid)
                    = COALESCE(%s::uuid, '00000000-0000-0000-0000-000000000000'::uuid)
                  AND status = 'active'
                LIMIT 1
                """,
                (normalize_id(payload.grantor_house_id), payload.election_id),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="An active proxy already exists for this villa")
            cur.execute(
                """
                INSERT INTO proxies (
                  election_id, grantor_house_id, proxy_holder_user_id, proxy_holder_house_id,
                  proxy_holder_email, notes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    payload.election_id,
                    normalize_id(payload.grantor_house_id),
                    normalize_id(payload.proxy_holder_user_id),
                    normalize_id(payload.proxy_holder_house_id),
                    clean(payload.proxy_holder_email).casefold(),
                    clean(payload.notes),
                ),
            )
            proxy = cur.fetchone()
            applied_representations = reconcile_proxy_representations(cur, election, proxy) if election else 0
        conn.commit()
    return {
        "id": str(proxy["id"]),
        "election_id": str(proxy["election_id"]) if proxy["election_id"] else None,
        "grantor_house_id": proxy["grantor_house_id"],
        "proxy_holder_user_id": proxy["proxy_holder_user_id"],
        "proxy_holder_house_id": proxy["proxy_holder_house_id"],
        "proxy_holder_email": proxy["proxy_holder_email"],
        "status": proxy["status"],
        "notes": proxy["notes"],
        "created_at": proxy["created_at"],
        "updated_at": proxy["updated_at"],
        "applied_representations": applied_representations,
    }


@app.get("/api/proxies", dependencies=[Depends(require_officer)])
def list_proxies(election_id: str | None = None) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.*, v.house_no AS grantor_house_no, r.name AS proxy_holder_name, rv.house_no AS proxy_holder_house_no
                FROM proxies p
                JOIN villas v ON v.house_id = p.grantor_house_id
                JOIN residents r
                  ON r.user_id = p.proxy_holder_user_id
                 AND r.house_id = p.proxy_holder_house_id
                JOIN villas rv ON rv.house_id = r.house_id
                WHERE p.status = 'active'
                  AND (%s::uuid IS NULL OR p.election_id = %s::uuid)
                ORDER BY p.created_at DESC
                """,
                (election_id, election_id),
            )
            rows = cur.fetchall()
    return [
        {
            "id": str(row["id"]),
            "election_id": str(row["election_id"]) if row["election_id"] else None,
            "grantor_house_id": row["grantor_house_id"],
            "grantor_house_no": row["grantor_house_no"],
            "proxy_holder_user_id": row["proxy_holder_user_id"],
            "proxy_holder_house_id": row["proxy_holder_house_id"],
            "proxy_holder_email": row["proxy_holder_email"],
            "proxy_holder_name": row["proxy_holder_name"],
            "proxy_holder_house_no": row["proxy_holder_house_no"],
            "status": row["status"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


@app.post("/api/proxies/{proxy_id}/cancel", dependencies=[Depends(require_officer)])
def cancel_proxy(proxy_id: str) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM proxies WHERE id = %s", (proxy_id,))
            proxy = cur.fetchone()
            if not proxy:
                raise HTTPException(status_code=404, detail="Proxy not found")
            ensure_proxy_editable(cur, str(proxy["election_id"]) if proxy["election_id"] else None)
            removed_representations = remove_proxy_representations(cur, proxy)
            cur.execute(
                """
                UPDATE proxies SET status = 'cancelled', updated_at = now()
                WHERE id = %s
                RETURNING id
                """,
                (proxy_id,),
            )
            cancelled = cur.fetchone()
        conn.commit()
    if not cancelled:
        raise HTTPException(status_code=404, detail="Proxy not found")
    return {"status": "cancelled", "removed_representations": removed_representations}


@app.post("/api/defaulters", dependencies=[Depends(require_officer)])
def create_defaulter(payload: DefaulterCreate) -> dict[str, Any]:
    house_id = normalize_id(payload.house_id)
    election_id = clean(payload.election_id)
    with connection() as conn:
        with conn.cursor() as cur:
            ensure_election_config_editable(cur, election_id)
            cur.execute("SELECT house_id, house_no FROM villas WHERE house_id = %s", (house_id,))
            villa = cur.fetchone()
            if not villa:
                raise HTTPException(status_code=404, detail="Villa was not found")
            cur.execute(
                """
                SELECT 1
                FROM defaulters
                WHERE election_id = %s
                  AND house_id = %s
                  AND status = 'active'
                LIMIT 1
                """,
                (election_id, house_id),
            )
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO defaulters (election_id, house_id, reason)
                    VALUES (%s, %s, %s)
                    RETURNING *
                    """,
                    (election_id, house_id, clean(payload.reason)),
                )
                defaulter = cur.fetchone()
            else:
                raise HTTPException(status_code=409, detail="This villa is already marked as a defaulter for this election")
        conn.commit()
    return defaulter_public(defaulter, villa["house_no"])


@app.get("/api/defaulters", dependencies=[Depends(require_officer)])
def list_defaulters(election_id: str) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM elections WHERE id = %s", (election_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Election not found")
            cur.execute(
                """
                SELECT d.*, v.house_no
                FROM defaulters d
                JOIN villas v ON v.house_id = d.house_id
                WHERE d.election_id = %s
                  AND d.status = 'active'
                ORDER BY v.house_no
                """,
                (election_id,),
            )
            rows = cur.fetchall()
    return [defaulter_public(row, row["house_no"]) for row in rows]


def defaulter_public(row: dict[str, Any], house_no: str) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "election_id": str(row["election_id"]) if row["election_id"] else None,
        "house_id": row["house_id"],
        "house_no": house_no,
        "reason": row["reason"],
        "status": row["status"],
        "effective_at": row["effective_at"],
        "cleared_at": row["cleared_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.post("/api/defaulters/{defaulter_id}/clear", dependencies=[Depends(require_officer)])
def clear_defaulter(defaulter_id: str) -> dict[str, str]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT election_id FROM defaulters WHERE id = %s", (defaulter_id,))
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Defaulter record not found")
            ensure_election_config_editable(cur, str(existing["election_id"]))
            cur.execute(
                """
                UPDATE defaulters
                SET status = 'cleared', cleared_at = now(), updated_at = now()
                WHERE id = %s
                RETURNING id
                """,
                (defaulter_id,),
            )
            defaulter = cur.fetchone()
        conn.commit()
    if not defaulter:
        raise HTTPException(status_code=404, detail="Defaulter record not found")
    return {"status": "cleared"}


@app.post("/api/elections/{election_id}/ballots")
def submit_ballot(election_id: str, payload: BallotSubmitRequest) -> dict[str, Any]:
    if not payload.answers:
        raise HTTPException(status_code=400, detail="At least one answer is required")
    with connection() as conn:
        with conn.cursor() as cur:
            election = fetch_election_summary(cur, election_id)
            if not election:
                raise HTTPException(status_code=404, detail="Election not found")
            if not election["voting_enabled"]:
                raise HTTPException(status_code=400, detail="Voting is disabled for this election")
            if election["status"] != "voting_open":
                raise HTTPException(status_code=400, detail="Voting is not open for this election")
            submitter = fetch_resident_by_user_id(cur, payload.submitted_by_user_id)
            if not submitter:
                raise HTTPException(status_code=404, detail="Submitting resident was not found")
            if not is_owner(submitter["user_type"]):
                raise HTTPException(status_code=403, detail="Only owner-type residents can vote")
            target_house_id = normalize_id(payload.house_id)
            ensure_villa_can_vote(cur, election, target_house_id)
            ensure_submitter_represents_house(cur, election_id, submitter["user_id"], target_house_id)
            validate_ballot_answers(cur, election_id, payload.answers)
            cur.execute(
                """
                SELECT 1
                FROM ballots
                WHERE election_id = %s AND house_id = %s
                LIMIT 1
                """,
                (election_id, target_house_id),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="A ballot has already been submitted for this villa")
            cur.execute(
                """
                INSERT INTO ballots (election_id, house_id, submitted_by_user_id)
                VALUES (%s, %s, %s)
                RETURNING id, submitted_at
                """,
                (election_id, target_house_id, submitter["user_id"]),
            )
            ballot = cur.fetchone()
            for answer in payload.answers:
                cur.execute(
                    """
                    INSERT INTO ballot_answers (ballot_id, question_id, choice_id)
                    VALUES (%s, %s, %s)
                    """,
                    (ballot["id"], answer.question_id, answer.choice_id),
                )
        conn.commit()
    return {"ballot_id": str(ballot["id"]), "submitted_at": ballot["submitted_at"]}


@app.get("/api/elections/{election_id}/results", dependencies=[Depends(require_officer)])
def election_results(election_id: str) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            election = fetch_election_summary(cur, election_id)
            if not election:
                raise HTTPException(status_code=404, detail="Election not found")
            if election["status"] not in {"voting_closed", "results_published", "archived"}:
                raise HTTPException(status_code=400, detail="Results are available after voting is closed")
            questions = fetch_questions(cur, election_id)
            cur.execute(
                """
                SELECT COUNT(*) AS voted_villas
                FROM ballots
                WHERE election_id = %s
                """,
                (election_id,),
            )
            voted_villas = cur.fetchone()["voted_villas"]
            results = calculate_results(cur, election_id, questions, election)
    return {
        "election": election_public(election),
        "attended_villas": election["represented_villas"],
        "voted_villas": voted_villas,
        "questions": results,
    }


@app.get("/api/elections/{election_id}/voting-status", dependencies=[Depends(require_officer)])
def election_voting_status(election_id: str) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            election = fetch_election_summary(cur, election_id)
            if not election:
                raise HTTPException(status_code=404, detail="Election not found")
            questions = fetch_questions(cur, election_id)
            cur.execute(
                """
                SELECT COUNT(*) AS voted_villas
                FROM ballots
                WHERE election_id = %s
                """,
                (election_id,),
            )
            voted_villas = int(cur.fetchone()["voted_villas"] or 0)
            results = None
            if election["status"] in {"voting_closed", "results_published", "archived"}:
                results = calculate_results(cur, election_id, questions, election)
    represented_villas = int(election.get("represented_villas", 0) or 0)
    return {
        "election": election_public(election),
        "represented_villas": represented_villas,
        "voted_villas": voted_villas,
        "pending_villas": max(represented_villas - voted_villas, 0),
        "results": results,
    }


def attendance_villa_rows(cur, election: dict[str, Any]) -> list[dict[str, Any]]:
    election_id = str(election["id"])
    include_defaulters = bool(election["include_defaulters_in_quorum"])
    rows: list[dict[str, Any]] = []

    cur.execute(
        """
        SELECT v.house_id, v.house_no,
          EXISTS (
            SELECT 1 FROM defaulters d
            WHERE d.election_id = %s
              AND d.house_id = v.house_id
              AND d.status = 'active'
          ) AS is_defaulter,
          MAX(ar.attended_at) AS last_attended_at,
          (array_agg(ar.attendance_mode ORDER BY ar.attended_at DESC))[1] AS attendance_mode,
          jsonb_agg(
              jsonb_build_object(
                'user_id', r.user_id,
                'name', r.name,
                'user_type', r.user_type,
                'status', r.status,
                'house_id', r.house_id,
                'house_no', v.house_no,
                'attended_at', ar.attended_at,
                'method', ar.method,
                'attendance_mode', ar.attendance_mode,
                'source', ar.source
            )
            ORDER BY ar.attended_at
          ) AS participants,
          b.submitted_at AS voted_at,
          submitter.name AS vote_submitted_by_name,
          submitter.user_id AS vote_submitted_by_user_id
        FROM attendance_records ar
        JOIN residents r
          ON r.user_id = ar.resident_user_id
         AND r.house_id = ar.house_id
        JOIN villas v ON v.house_id = ar.house_id
        LEFT JOIN ballots b
          ON b.election_id = ar.election_id
         AND b.house_id = ar.house_id
        LEFT JOIN LATERAL (
          SELECT sr.user_id, sr.name
          FROM residents sr
          WHERE sr.user_id = b.submitted_by_user_id
          ORDER BY position('owner' in lower(sr.user_type)) DESC, sr.updated_at DESC
          LIMIT 1
        ) submitter ON true
        WHERE ar.election_id = %s
        GROUP BY v.house_id, v.house_no, b.submitted_at,
          submitter.name, submitter.user_id
        """,
        (election_id, election_id),
    )
    for row in cur.fetchall():
        is_defaulter = bool(row["is_defaulter"])
        rows.append(attendance_villa_row_public(
            row,
            representation_type="self",
            participants=row["participants"] or [],
            is_defaulter=is_defaulter,
            counted=include_defaulters or not is_defaulter,
        ))

    cur.execute(
        """
        SELECT v.house_id, v.house_no,
          EXISTS (
            SELECT 1 FROM defaulters d
            WHERE d.election_id = %s
              AND d.house_id = v.house_id
              AND d.status = 'active'
          ) AS is_defaulter,
          ar.attended_at AS last_attended_at,
          ar.attendance_mode AS attendance_mode,
          jsonb_build_array(
            jsonb_build_object(
              'user_id', r.user_id,
              'name', r.name,
              'user_type', r.user_type,
              'status', r.status,
              'house_id', r.house_id,
              'house_no', rv.house_no,
              'attended_at', ar.attended_at,
              'method', ar.method,
              'attendance_mode', ar.attendance_mode,
              'source', ar.source
            )
          ) AS participants,
          b.submitted_at AS voted_at,
          submitter.name AS vote_submitted_by_name,
          submitter.user_id AS vote_submitted_by_user_id
        FROM villa_representations vr
        JOIN villas v ON v.house_id = vr.house_id
        JOIN attendance_records ar ON ar.id = vr.source_attendance_record_id
        JOIN villas rv ON rv.house_id = ar.house_id
        JOIN residents r
          ON r.user_id = ar.resident_user_id
         AND r.house_id = ar.house_id
        LEFT JOIN ballots b
          ON b.election_id = vr.election_id
         AND b.house_id = vr.house_id
        LEFT JOIN LATERAL (
          SELECT sr.user_id, sr.name
          FROM residents sr
          WHERE sr.user_id = b.submitted_by_user_id
          ORDER BY position('owner' in lower(sr.user_type)) DESC, sr.updated_at DESC
          LIMIT 1
        ) submitter ON true
        WHERE vr.election_id = %s
          AND vr.representation_type = 'proxy'
        """,
        (election_id, election_id),
    )
    for row in cur.fetchall():
        is_defaulter = bool(row["is_defaulter"])
        rows.append(attendance_villa_row_public(
            row,
            representation_type="proxy",
            participants=row["participants"] or [],
            is_defaulter=is_defaulter,
            counted=include_defaulters or not is_defaulter,
        ))

    if not include_defaulters:
        cur.execute(
            """
            SELECT v.house_id, v.house_no,
              true AS is_defaulter,
              MAX(ar.attended_at) AS last_attended_at,
              (array_agg(ar.attendance_mode ORDER BY ar.attended_at DESC))[1] AS attendance_mode,
              jsonb_agg(
                jsonb_build_object(
                  'user_id', r.user_id,
                  'name', r.name,
                  'user_type', r.user_type,
                  'status', r.status,
                  'house_id', r.house_id,
                  'house_no', rv.house_no,
                  'attended_at', ar.attended_at,
                  'method', ar.method,
                  'attendance_mode', ar.attendance_mode,
                  'source', ar.source
                )
                ORDER BY ar.attended_at
              ) AS participants,
              NULL::timestamptz AS voted_at,
              NULL::text AS vote_submitted_by_name,
              NULL::text AS vote_submitted_by_user_id
            FROM attendance_records ar
            JOIN proxies p
              ON p.proxy_holder_user_id = ar.resident_user_id
             AND p.status = 'active'
             AND p.election_id = ar.election_id
            JOIN villas v ON v.house_id = p.grantor_house_id
            JOIN villas rv ON rv.house_id = ar.house_id
            JOIN defaulters d
              ON d.house_id = p.grantor_house_id
             AND d.election_id = ar.election_id
             AND d.status = 'active'
            JOIN residents r
              ON r.user_id = ar.resident_user_id
             AND r.house_id = ar.house_id
            LEFT JOIN villa_representations vr
              ON vr.election_id = ar.election_id
             AND vr.house_id = p.grantor_house_id
            WHERE ar.election_id = %s
              AND vr.house_id IS NULL
            GROUP BY v.house_id, v.house_no
            """,
            (election_id,),
        )
        for row in cur.fetchall():
            rows.append(attendance_villa_row_public(
                row,
                representation_type="proxy",
                participants=row["participants"] or [],
                is_defaulter=True,
                counted=False,
            ))

    return sorted(
        rows,
        key=lambda item: (
            0 if item["counted"] else 1,
            -(item["lastAttendanceTime"].timestamp() if item["lastAttendanceTime"] else 0),
            item["flat"],
        ),
    )


def attendance_villa_row_public(
    row: dict[str, Any],
    representation_type: str,
    participants: list[dict[str, Any]],
    is_defaulter: bool,
    counted: bool,
) -> dict[str, Any]:
    return {
        "id": f"{representation_type}:{row['house_id']}",
        "house_id": row["house_id"],
        "flat": row["house_no"],
        "representationType": representation_type,
        "isProxy": representation_type == "proxy",
        "attendanceMode": row.get("attendance_mode") or "",
        "isDefaulter": is_defaulter,
        "counted": counted,
        "participants": participants,
        "lastAttendanceTime": row["last_attended_at"],
        "hasVoted": bool(row["voted_at"]),
        "votedAt": row["voted_at"],
        "voteSubmittedByName": row["vote_submitted_by_name"],
        "voteSubmittedByUserId": row["vote_submitted_by_user_id"],
    }


def mark_attendance(
    election_id: str,
    method: str,
    source: str,
    attendance_mode: str,
    raw_qr_data: str | None = None,
    passcode: str | None = None,
    user_id: str | None = None,
    house_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    method = validate_choice(method, ATTENDANCE_METHODS, "attendance method")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM elections WHERE id = %s", (election_id,))
            election = cur.fetchone()
            if not election:
                raise HTTPException(status_code=404, detail="Election not found")
            if election["status"] not in ATTENDANCE_OPEN_STATUSES:
                raise HTTPException(status_code=409, detail="Attendance can be marked only during Attendance or Voting")
            normalized_attendance_mode = normalize_attendance_mode(attendance_mode, election)

            resident = find_resident_for_attendance(cur, passcode=passcode, user_id=user_id, house_id=house_id, name=name)
            if not resident:
                raise HTTPException(status_code=404, detail="No matching resident found")
            if not is_owner(resident["user_type"]):
                raise HTTPException(status_code=403, detail="Only owner-type residents can attend or vote")

            ensure_villa_attendance_not_already_recorded(cur, election_id, resident["house_id"])

            attendance_rows = add_owner_attendance_records(
                cur,
                election_id=election_id,
                house_id=resident["house_id"],
                method=method,
                attendance_mode=normalized_attendance_mode,
                source=source,
                raw_qr_data=raw_qr_data,
            )
            attendance = next(
                (row for row in attendance_rows if row["resident_user_id"] == resident["user_id"]),
                attendance_rows[0],
            )
            if election["include_defaulters_in_quorum"] or not is_active_defaulter(cur, resident["house_id"], election_id):
                cur.execute(
                    """
                    INSERT INTO villa_representations (
                      election_id, house_id, represented_by_user_id, representation_type, source_attendance_record_id
                    )
                    VALUES (%s, %s, %s, 'self', %s)
                    ON CONFLICT (election_id, house_id) DO NOTHING
                    """,
                    (election_id, resident["house_id"], resident["user_id"], attendance["id"]),
                )
            for attendance_row in attendance_rows:
                add_proxy_representations(
                    cur,
                    election,
                    attendance_row["resident_user_id"],
                    attendance_row["id"],
                )
            conn.commit()
    return {"resident": resident_public(resident), "attended_at": attendance["attended_at"]}


def add_owner_attendance_records(
    cur,
    election_id: str,
    house_id: str,
    method: str,
    attendance_mode: str,
    source: str,
    raw_qr_data: str | None,
) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT user_id
        FROM residents
        WHERE house_id = %s
          AND position('owner' in lower(user_type)) > 0
        ORDER BY name
        """,
        (normalize_id(house_id),),
    )
    owners = [row["user_id"] for row in cur.fetchall()]
    if not owners:
        raise HTTPException(status_code=404, detail="No owner-type residents found for this villa")

    rows: list[dict[str, Any]] = []
    for owner_user_id in owners:
        cur.execute(
            """
            SELECT id, resident_user_id, house_id, attendance_mode, attended_at
            FROM attendance_records
            WHERE election_id = %s
              AND resident_user_id = %s
              AND house_id = %s
            ORDER BY attended_at DESC
            LIMIT 1
            """,
            (election_id, owner_user_id, normalize_id(house_id)),
        )
        existing = cur.fetchone()
        if existing:
            rows.append(existing)
            continue
        cur.execute(
            """
            INSERT INTO attendance_records (
              election_id, resident_user_id, house_id, method, attendance_mode, source, raw_qr_data
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, resident_user_id, house_id, attendance_mode, attended_at
            """,
            (election_id, owner_user_id, normalize_id(house_id), method, attendance_mode, source, raw_qr_data),
        )
        rows.append(cur.fetchone())
    return rows


def find_resident_for_attendance(cur, passcode=None, user_id=None, house_id=None, name=None):
    if passcode:
        cur.execute(
            """
            SELECT r.*, v.house_no
            FROM residents r
            JOIN villas v ON v.house_id = r.house_id
            WHERE r.passcode = %s
            ORDER BY position('owner' in lower(r.user_type)) DESC, r.updated_at DESC
            LIMIT 1
            """,
            (passcode,),
        )
        return cur.fetchone()
    if user_id:
        house_clause = "AND r.house_id = %s" if house_id else ""
        params = [normalize_id(user_id)]
        if house_id:
            params.append(normalize_id(house_id))
        cur.execute(
            f"""
            SELECT r.*, v.house_no
            FROM residents r
            JOIN villas v ON v.house_id = r.house_id
            WHERE r.user_id = %s
              {house_clause}
            ORDER BY position('owner' in lower(r.user_type)) DESC, r.updated_at DESC
            LIMIT 1
            """,
            tuple(params),
        )
        return cur.fetchone()
    if house_id and name:
        cur.execute(
            """
            SELECT r.*, v.house_no
            FROM residents r
            JOIN villas v ON v.house_id = r.house_id
            WHERE r.house_id = %s
              AND lower(r.name) = lower(%s)
              AND position('owner' in lower(r.user_type)) > 0
            ORDER BY r.updated_at DESC
            LIMIT 1
            """,
            (normalize_id(house_id), clean(name)),
        )
        return cur.fetchone()
    if house_id:
        cur.execute(
            """
            SELECT r.*, v.house_no
            FROM residents r
            JOIN villas v ON v.house_id = r.house_id
            WHERE r.house_id = %s
              AND position('owner' in lower(r.user_type)) > 0
            ORDER BY r.name, r.updated_at DESC
            LIMIT 1
            """,
            (normalize_id(house_id),),
        )
        return cur.fetchone()
    return None


def add_proxy_representations(
    cur, election: dict[str, Any], proxy_holder_user_id: str, attendance_record_id: str
) -> None:
    defaulter_filter = ""
    if not election["include_defaulters_in_quorum"]:
        defaulter_filter = """
          AND NOT EXISTS (
            SELECT 1
            FROM defaulters d
            WHERE d.election_id = %s
              AND d.house_id = p.grantor_house_id
              AND d.status = 'active'
          )
        """
    cur.execute(
        f"""
        INSERT INTO villa_representations (
          election_id, house_id, represented_by_user_id, representation_type, source_attendance_record_id
        )
        SELECT %s, p.grantor_house_id, %s, 'proxy', %s
        FROM proxies p
        WHERE p.status = 'active'
          AND p.proxy_holder_user_id = %s
          AND p.election_id = %s
          {defaulter_filter}
        ON CONFLICT (election_id, house_id) DO NOTHING
        """,
        (
            election["id"],
            proxy_holder_user_id,
            attendance_record_id,
            proxy_holder_user_id,
            election["id"],
            election["id"],
        ) if defaulter_filter else (
            election["id"],
            proxy_holder_user_id,
            attendance_record_id,
            proxy_holder_user_id,
            election["id"],
        ),
    )


def reconcile_proxy_representations(cur, election: dict[str, Any], proxy: dict[str, Any]) -> int:
    if not election or not proxy or proxy["status"] != "active":
        return 0
    defaulter_filter = ""
    params: tuple[Any, ...]
    if not election["include_defaulters_in_quorum"]:
        defaulter_filter = """
          AND NOT EXISTS (
            SELECT 1
            FROM defaulters d
            WHERE d.election_id = %s
              AND d.house_id = p.grantor_house_id
              AND d.status = 'active'
          )
        """
        params = (
            election["id"],
            proxy["grantor_house_id"],
            proxy["proxy_holder_user_id"],
            election["id"],
            proxy["id"],
            election["id"],
        )
    else:
        params = (
            election["id"],
            proxy["grantor_house_id"],
            proxy["proxy_holder_user_id"],
            election["id"],
            proxy["id"],
        )
    cur.execute(
        f"""
        INSERT INTO villa_representations (
          election_id, house_id, represented_by_user_id, representation_type, source_attendance_record_id
        )
        SELECT %s, p.grantor_house_id, p.proxy_holder_user_id, 'proxy', ar.id
        FROM proxies p
        JOIN attendance_records ar
          ON ar.election_id = p.election_id
         AND ar.resident_user_id = p.proxy_holder_user_id
         AND ar.house_id = p.proxy_holder_house_id
        WHERE p.status = 'active'
          AND p.grantor_house_id = %s
          AND p.proxy_holder_user_id = %s
          AND p.election_id = %s
          AND p.id = %s
          {defaulter_filter}
        ON CONFLICT (election_id, house_id) DO NOTHING
        """,
        params,
    )
    return cur.rowcount


def remove_proxy_representations(cur, proxy: dict[str, Any]) -> int:
    cur.execute(
        """
        SELECT 1
        FROM ballots
        WHERE election_id = %s
          AND house_id = %s
        LIMIT 1
        """,
        (proxy["election_id"], proxy["grantor_house_id"]),
    )
    if cur.fetchone():
        raise HTTPException(status_code=409, detail="Cannot delete proxy after votes have been submitted for this villa")

    cur.execute(
        """
        DELETE FROM villa_representations vr
        USING attendance_records ar
        WHERE vr.source_attendance_record_id = ar.id
          AND vr.election_id = %s
          AND vr.house_id = %s
          AND vr.represented_by_user_id = %s
          AND vr.representation_type = 'proxy'
          AND ar.house_id = %s
        """,
        (
            proxy["election_id"],
            proxy["grantor_house_id"],
            proxy["proxy_holder_user_id"],
            proxy["proxy_holder_house_id"],
        ),
    )
    return cur.rowcount


def fetch_resident_by_user_id(cur, user_id: str, house_id: str | None = None) -> dict[str, Any] | None:
    house_clause = "AND r.house_id = %s" if house_id else ""
    params = [normalize_id(user_id)]
    if house_id:
        params.append(normalize_id(house_id))
    cur.execute(
        f"""
        SELECT r.*, v.house_no
        FROM residents r
        JOIN villas v ON v.house_id = r.house_id
        WHERE r.user_id = %s
          {house_clause}
        ORDER BY position('owner' in lower(r.user_type)) DESC, r.updated_at DESC
        LIMIT 1
        """,
        tuple(params),
    )
    return cur.fetchone()


def is_active_defaulter(cur, house_id: str, election_id: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM defaulters
        WHERE election_id = %s
          AND house_id = %s
          AND status = 'active'
        LIMIT 1
        """,
        (election_id, normalize_id(house_id)),
    )
    return bool(cur.fetchone())


def villa_has_recorded_attendance(cur, election_id: str, house_id: str) -> bool:
    normalized_house_id = normalize_id(house_id)
    cur.execute(
        """
        SELECT 1
        FROM villa_representations
        WHERE election_id = %s
          AND house_id = %s
        LIMIT 1
        """,
        (election_id, normalized_house_id),
    )
    if cur.fetchone():
        return True
    cur.execute(
        """
        SELECT 1
        FROM attendance_records
        WHERE election_id = %s
          AND house_id = %s
        LIMIT 1
        """,
        (election_id, normalized_house_id),
    )
    return bool(cur.fetchone())


def ensure_villa_attendance_not_already_recorded(cur, election_id: str, house_id: str) -> None:
    if villa_has_recorded_attendance(cur, election_id, house_id):
        raise HTTPException(status_code=409, detail="Attendance has already been recorded for this villa")


def ensure_villa_can_vote(cur, election: dict[str, Any], house_id: str) -> None:
    cur.execute("SELECT house_id FROM villas WHERE house_id = %s", (house_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Voting villa was not found")
    if not election["allow_defaulters_to_vote"] and is_active_defaulter(cur, house_id, str(election["id"])):
        raise HTTPException(status_code=403, detail="This villa is not eligible to vote for this election")
    cur.execute(
        """
        SELECT 1
        FROM villa_representations
        WHERE election_id = %s AND house_id = %s
        LIMIT 1
        """,
        (election["id"], house_id),
    )
    if not cur.fetchone():
        raise HTTPException(status_code=403, detail="Attendance has not been marked for this villa")


def ensure_submitter_represents_house(cur, election_id: str, submitter_user_id: str, house_id: str) -> None:
    cur.execute(
        """
        SELECT 1
        FROM residents
        WHERE user_id = %s AND house_id = %s
        LIMIT 1
        """,
        (submitter_user_id, house_id),
    )
    if cur.fetchone():
        return
    cur.execute(
        """
        SELECT 1
        FROM villa_representations
        WHERE election_id = %s
          AND house_id = %s
          AND represented_by_user_id = %s
          AND representation_type = 'proxy'
        LIMIT 1
        """,
        (election_id, house_id, submitter_user_id),
    )
    if not cur.fetchone():
        raise HTTPException(status_code=403, detail="This voter does not represent the selected villa")


def voter_represented_houses(cur, election_id: str, user_id: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT DISTINCT v.house_id, v.house_no,
          CASE WHEN own.user_id IS NOT NULL THEN 'own' ELSE 'proxy' END AS representation_type,
          b.id AS ballot_id,
          b.submitted_at
        FROM villa_representations vr
        JOIN villas v ON v.house_id = vr.house_id
        LEFT JOIN residents own
          ON own.user_id = %s
         AND own.house_id = vr.house_id
         AND position('owner' in lower(own.user_type)) > 0
        LEFT JOIN ballots b
          ON b.election_id = vr.election_id
         AND b.house_id = vr.house_id
        WHERE vr.election_id = %s
          AND (
            own.user_id IS NOT NULL
            OR vr.represented_by_user_id = %s
          )
        ORDER BY v.house_no
        """,
        (normalize_id(user_id), election_id, normalize_id(user_id)),
    )
    return [
        {
            "house_id": row["house_id"],
            "house_no": row["house_no"],
            "representation_type": row["representation_type"],
            "ballot_id": str(row["ballot_id"]) if row["ballot_id"] else None,
            "submitted_at": row["submitted_at"],
            "has_voted": bool(row["ballot_id"]),
        }
        for row in cur.fetchall()
    ]


def validate_ballot_answers(cur, election_id: str, answers: list[BallotAnswerRequest]) -> None:
    question_ids = [answer.question_id for answer in answers]
    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(status_code=400, detail="Only one answer is allowed per question")
    cur.execute(
        """
        SELECT q.id AS question_id, c.id AS choice_id
        FROM election_questions q
        JOIN election_choices c ON c.question_id = q.id
        WHERE q.election_id = %s
        """,
        (election_id,),
    )
    valid_pairs = {(str(row["question_id"]), str(row["choice_id"])) for row in cur.fetchall()}
    election_question_ids = {question_id for question_id, _choice_id in valid_pairs}
    answer_pairs = {(answer.question_id, answer.choice_id) for answer in answers}
    if {answer.question_id for answer in answers} != election_question_ids:
        raise HTTPException(status_code=400, detail="A ballot must answer every election question")
    invalid = answer_pairs - valid_pairs
    if invalid:
        raise HTTPException(status_code=400, detail="One or more choices do not belong to their question")


def calculate_results(
    cur, election_id: str, questions: list[dict[str, Any]], election: dict[str, Any]
) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT ba.question_id, ba.choice_id, COUNT(*) AS vote_count
        FROM ballot_answers ba
        JOIN ballots b ON b.id = ba.ballot_id
        WHERE b.election_id = %s
        GROUP BY ba.question_id, ba.choice_id
        """,
        (election_id,),
    )
    counts = {(str(row["question_id"]), str(row["choice_id"])): int(row["vote_count"]) for row in cur.fetchall()}
    results = []
    for question in questions:
        total_votes = sum(counts.get((question["id"], choice["id"]), 0) for choice in question["choices"])
        choice_results = []
        for choice in question["choices"]:
            vote_count = counts.get((question["id"], choice["id"]), 0)
            choice_results.append({**choice, "vote_count": vote_count})
        winning_choice = max(choice_results, key=lambda item: item["vote_count"], default=None)
        threshold = passing_threshold(election)
        winning_percent = (winning_choice["vote_count"] / total_votes * 100) if winning_choice and total_votes else 0
        results.append(
            {
                **question,
                "total_votes": total_votes,
                "choices": choice_results,
                "winning_choice_id": winning_choice["id"] if winning_choice else None,
                "winning_percent": winning_percent,
                "passed": bool(winning_choice and winning_percent >= threshold),
                "passing_threshold_percent": threshold,
            }
        )
    return results


def passing_threshold(election: dict[str, Any]) -> float:
    if election["passing_rule"] == "two_thirds":
        return 66.667
    if election["passing_rule"] == "custom_threshold":
        return float(election["passing_threshold_percent"] or 50)
    return 50.0
