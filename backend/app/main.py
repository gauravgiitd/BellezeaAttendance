import csv
import io
import os
import re
import urllib.request
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import connection, initialize_schema


app = FastAPI(title="Nambiar Bellezea Election API")


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


class ElectionCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    quorum_percent: Decimal = Decimal("50.0")
    include_defaulters_in_quorum: bool = False
    allow_defaulters_to_vote: bool = False


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
    passing_rule: str = "simple_majority"
    passing_threshold_percent: Decimal | None = None
    display_order: int = 0
    choices: list[QuestionChoiceCreate] = Field(min_length=2)


class ProxyCreate(BaseModel):
    election_id: str | None = None
    grantor_house_id: str
    proxy_holder_user_id: str
    notes: str = ""


class DefaulterCreate(BaseModel):
    house_id: str
    reason: str = ""


class AttendanceQrRequest(BaseModel):
    qr_raw_data: str
    method: str = "qr_scan"
    source: str = "officer"


class AttendanceManualRequest(BaseModel):
    user_id: str | None = None
    house_id: str | None = None
    name: str | None = None
    source: str = "officer"


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


ELECTION_STATUSES = {
    "draft",
    "attendance_open",
    "discussion",
    "voting_open",
    "voting_closed",
    "results_published",
    "archived",
}

ATTENDANCE_METHODS = {"qr_scan", "qr_upload", "manual"}
PASSING_RULES = {"simple_majority", "two_thirds", "custom_threshold"}


def validate_choice(value: str, allowed: set[str], label: str) -> str:
    cleaned = clean(value)
    if cleaned not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid {label}: {cleaned}")
    return cleaned


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
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                      house_id = EXCLUDED.house_id,
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
            cur.execute(
                """
                INSERT INTO resident_source_syncs (source, row_count, metadata)
                VALUES (%s, %s, %s::jsonb)
                """,
                (source, imported, psycopg_json({"skipped": skipped})),
            )
        conn.commit()
    return {"imported": imported, "skipped": skipped}


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
        "include_defaulters_in_quorum": row["include_defaulters_in_quorum"],
        "allow_defaulters_to_vote": row["allow_defaulters_to_vote"],
        "voting_opens_at": row["voting_opens_at"],
        "voting_closes_at": row["voting_closes_at"],
        "represented_villas": represented_villas,
        "eligible_villas": eligible_villas,
        "quorum_reached": quorum_reached,
    }


def fetch_election_summary(cur, election_id: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT e.*,
          COUNT(DISTINCT vr.house_id) AS represented_villas,
          (
            SELECT COUNT(*)
            FROM villas v
            WHERE e.include_defaulters_in_quorum
               OR NOT EXISTS (
                 SELECT 1
                 FROM defaulters d
                 WHERE d.house_id = v.house_id AND d.status = 'active'
               )
          ) AS eligible_villas
        FROM elections e
        LEFT JOIN villa_representations vr ON vr.election_id = e.id
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
                "passing_rule": row["passing_rule"],
                "passing_threshold_percent": (
                    float(row["passing_threshold_percent"]) if row["passing_threshold_percent"] is not None else None
                ),
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


@app.on_event("startup")
def on_startup() -> None:
    if os.environ.get("AUTO_MIGRATE", "true").lower() not in {"0", "false", "no"}:
        initialize_schema()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/admin/migrate")
def migrate() -> dict[str, str]:
    initialize_schema()
    return {"status": "migrated"}


@app.post("/api/residents/sync-csv")
async def sync_residents_from_csv(file: UploadFile = File(...)) -> dict[str, int]:
    text = (await file.read()).decode("utf-8-sig")
    return upsert_residents(csv_rows_from_text(text), source=file.filename or "uploaded_csv")


@app.post("/api/residents/sync-from-google-sheet")
def sync_residents_from_google_sheet(csv_url: str | None = None) -> dict[str, int]:
    return sync_residents_from_google_sheet_url(csv_url)


@app.get("/api/residents/sync-from-google-sheet")
def sync_residents_from_google_sheet_browser(csv_url: str | None = None) -> dict[str, int]:
    return sync_residents_from_google_sheet_url(csv_url)


def sync_residents_from_google_sheet_url(csv_url: str | None = None) -> dict[str, int]:
    url = csv_url or os.environ.get("RESIDENT_MASTER_CSV_URL")
    if not url:
        raise HTTPException(status_code=400, detail="csv_url or RESIDENT_MASTER_CSV_URL is required")
    with urllib.request.urlopen(url, timeout=30) as response:
        text = response.read().decode("utf-8-sig")
    return upsert_residents(csv_rows_from_text(text), source=url)


@app.get("/api/residents/sync-status")
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
                """,
                (passcode,),
            )
            resident = cur.fetchone()
    if not resident:
        raise HTTPException(status_code=404, detail="No resident matched this passcode")
    if not is_owner(resident["user_type"]):
        raise HTTPException(status_code=403, detail="Only owner-type residents can attend or vote")
    return {"resident": resident_public(resident)}


@app.get("/api/elections")
def list_elections() -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.*,
                  COUNT(DISTINCT vr.house_id) AS represented_villas,
                  (
                    SELECT COUNT(*)
                    FROM villas v
                    WHERE e.include_defaulters_in_quorum
                       OR NOT EXISTS (
                         SELECT 1
                         FROM defaulters d
                         WHERE d.house_id = v.house_id AND d.status = 'active'
                       )
                  ) AS eligible_villas
                FROM elections e
                LEFT JOIN villa_representations vr ON vr.election_id = e.id
                GROUP BY e.id
                ORDER BY e.created_at DESC
                """
            )
            return [election_public(row) for row in cur.fetchall()]


@app.post("/api/elections")
def create_election(payload: ElectionCreate) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO elections (
                  title, description, quorum_percent,
                  include_defaulters_in_quorum, allow_defaulters_to_vote
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    payload.title,
                    payload.description,
                    payload.quorum_percent,
                    payload.include_defaulters_in_quorum,
                    payload.allow_defaulters_to_vote,
                ),
            )
            created = cur.fetchone()
            election = fetch_election_summary(cur, str(created["id"]))
        conn.commit()
    return election_public(election)


@app.get("/api/elections/{election_id}")
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


@app.post("/api/elections/{election_id}/questions")
def add_question(election_id: str, payload: QuestionCreate) -> dict[str, Any]:
    passing_rule = validate_choice(payload.passing_rule, PASSING_RULES, "passing rule")
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM elections WHERE id = %s", (election_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Election not found")
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
                    passing_rule,
                    payload.passing_threshold_percent,
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


@app.post("/api/elections/{election_id}/status")
def update_election_status(election_id: str, payload: ElectionStatusUpdate) -> dict[str, Any]:
    status = validate_choice(payload.status, ELECTION_STATUSES, "election status")
    with connection() as conn:
        with conn.cursor() as cur:
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


@app.post("/api/elections/{election_id}/attendance/qr")
def mark_qr_attendance(election_id: str, payload: AttendanceQrRequest) -> dict[str, Any]:
    passcode = extract_passcode(payload.qr_raw_data)
    if not passcode:
        raise HTTPException(status_code=400, detail="Could not extract passcode from QR")
    return mark_attendance(
        election_id=election_id,
        method=payload.method,
        source=payload.source,
        raw_qr_data=payload.qr_raw_data,
        passcode=passcode,
    )


@app.post("/api/elections/{election_id}/attendance/manual")
def mark_manual_attendance(election_id: str, payload: AttendanceManualRequest) -> dict[str, Any]:
    return mark_attendance(
        election_id=election_id,
        method="manual",
        source=payload.source,
        user_id=payload.user_id,
        house_id=payload.house_id,
        name=payload.name,
    )


@app.get("/api/elections/{election_id}/attendance/dashboard")
def attendance_dashboard(election_id: str) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            election = fetch_election_summary(cur, election_id)
            if not election:
                raise HTTPException(status_code=404, detail="Election not found")
            cur.execute(
                """
                SELECT ar.id, ar.method, ar.source, ar.attended_at,
                  r.user_id, r.name, r.user_type, r.status,
                  v.house_id, v.house_no
                FROM attendance_records ar
                JOIN residents r ON r.user_id = ar.resident_user_id
                JOIN villas v ON v.house_id = ar.house_id
                WHERE ar.election_id = %s
                ORDER BY ar.attended_at DESC
                """,
                (election_id,),
            )
            attendees = [
                {
                    "id": str(row["id"]),
                    "user_id": row["user_id"],
                    "house_id": row["house_id"],
                    "name": row["name"],
                    "flat": row["house_no"],
                    "userType": row["user_type"],
                    "status": row["status"],
                    "method": row["method"],
                    "source": row["source"],
                    "attendanceTime": row["attended_at"],
                }
                for row in cur.fetchall()
            ]
    election_data = election_public(election)
    represented = election_data["represented_villas"]
    eligible = election_data["eligible_villas"]
    return {
        "election": election_data,
        "totalVillas": eligible,
        "representedVillas": represented,
        "representationPct": (represented / eligible * 100) if eligible else 0,
        "attendees": attendees,
    }


@app.post("/api/proxies")
def create_proxy(payload: ProxyCreate) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT house_id FROM villas WHERE house_id = %s", (normalize_id(payload.grantor_house_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Grantor villa was not found")
            proxy_holder = fetch_resident_by_user_id(cur, payload.proxy_holder_user_id)
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
                INSERT INTO proxies (election_id, grantor_house_id, proxy_holder_user_id, notes)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (
                    payload.election_id,
                    normalize_id(payload.grantor_house_id),
                    normalize_id(payload.proxy_holder_user_id),
                    clean(payload.notes),
                ),
            )
            proxy = cur.fetchone()
        conn.commit()
    return proxy


@app.get("/api/proxies")
def list_proxies(election_id: str | None = None) -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.*, v.house_no AS grantor_house_no, r.name AS proxy_holder_name, rv.house_no AS proxy_holder_house_no
                FROM proxies p
                JOIN villas v ON v.house_id = p.grantor_house_id
                JOIN residents r ON r.user_id = p.proxy_holder_user_id
                JOIN villas rv ON rv.house_id = r.house_id
                WHERE %s IS NULL OR p.election_id = %s OR p.election_id IS NULL
                ORDER BY p.created_at DESC
                """,
                (election_id, election_id),
            )
            return cur.fetchall()


@app.post("/api/proxies/{proxy_id}/cancel")
def cancel_proxy(proxy_id: str) -> dict[str, str]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE proxies SET status = 'cancelled', updated_at = now()
                WHERE id = %s
                RETURNING id
                """,
                (proxy_id,),
            )
            proxy = cur.fetchone()
        conn.commit()
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    return {"status": "cancelled"}


@app.post("/api/defaulters")
def create_defaulter(payload: DefaulterCreate) -> dict[str, Any]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT house_id FROM villas WHERE house_id = %s", (normalize_id(payload.house_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Villa was not found")
            cur.execute(
                """
                INSERT INTO defaulters (house_id, reason)
                VALUES (%s, %s)
                RETURNING *
                """,
                (normalize_id(payload.house_id), clean(payload.reason)),
            )
            defaulter = cur.fetchone()
        conn.commit()
    return defaulter


@app.get("/api/defaulters")
def list_defaulters() -> list[dict[str, Any]]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.*, v.house_no
                FROM defaulters d
                JOIN villas v ON v.house_id = d.house_id
                WHERE d.status = 'active'
                ORDER BY v.house_no
                """
            )
            return cur.fetchall()


@app.post("/api/defaulters/{defaulter_id}/clear")
def clear_defaulter(defaulter_id: str) -> dict[str, str]:
    with connection() as conn:
        with conn.cursor() as cur:
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


@app.get("/api/elections/{election_id}/results")
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
            results = calculate_results(cur, election_id, questions)
    return {
        "election": election_public(election),
        "attended_villas": election["represented_villas"],
        "voted_villas": voted_villas,
        "questions": results,
    }


def mark_attendance(
    election_id: str,
    method: str,
    source: str,
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

            resident = find_resident_for_attendance(cur, passcode=passcode, user_id=user_id, house_id=house_id, name=name)
            if not resident:
                raise HTTPException(status_code=404, detail="No matching resident found")
            if not is_owner(resident["user_type"]):
                raise HTTPException(status_code=403, detail="Only owner-type residents can attend or vote")

            cur.execute(
                """
                INSERT INTO attendance_records (
                  election_id, resident_user_id, house_id, method, source, raw_qr_data
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, attended_at
                """,
                (election_id, resident["user_id"], resident["house_id"], method, source, raw_qr_data),
            )
            attendance = cur.fetchone()
            if election["include_defaulters_in_quorum"] or not is_active_defaulter(cur, resident["house_id"]):
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
            add_proxy_representations(cur, election, resident["user_id"], attendance["id"])
            conn.commit()
    return {"resident": resident_public(resident), "attended_at": attendance["attended_at"]}


def find_resident_for_attendance(cur, passcode=None, user_id=None, house_id=None, name=None):
    if passcode:
        cur.execute(
            """
            SELECT r.*, v.house_no
            FROM residents r
            JOIN villas v ON v.house_id = r.house_id
            WHERE r.passcode = %s
            """,
            (passcode,),
        )
        return cur.fetchone()
    if user_id:
        cur.execute(
            """
            SELECT r.*, v.house_no
            FROM residents r
            JOIN villas v ON v.house_id = r.house_id
            WHERE r.user_id = %s
            """,
            (normalize_id(user_id),),
        )
        return cur.fetchone()
    if house_id and name:
        cur.execute(
            """
            SELECT r.*, v.house_no
            FROM residents r
            JOIN villas v ON v.house_id = r.house_id
            WHERE r.house_id = %s AND lower(r.name) = lower(%s)
            ORDER BY r.updated_at DESC
            LIMIT 1
            """,
            (normalize_id(house_id), clean(name)),
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
            WHERE d.house_id = p.grantor_house_id AND d.status = 'active'
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
          AND (p.election_id IS NULL OR p.election_id = %s)
          {defaulter_filter}
        ON CONFLICT (election_id, house_id) DO NOTHING
        """,
        (election["id"], proxy_holder_user_id, attendance_record_id, proxy_holder_user_id, election["id"]),
    )


def fetch_resident_by_user_id(cur, user_id: str) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT r.*, v.house_no
        FROM residents r
        JOIN villas v ON v.house_id = r.house_id
        WHERE r.user_id = %s
        """,
        (normalize_id(user_id),),
    )
    return cur.fetchone()


def is_active_defaulter(cur, house_id: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM defaulters
        WHERE house_id = %s AND status = 'active'
        LIMIT 1
        """,
        (normalize_id(house_id),),
    )
    return bool(cur.fetchone())


def ensure_villa_can_vote(cur, election: dict[str, Any], house_id: str) -> None:
    cur.execute("SELECT house_id FROM villas WHERE house_id = %s", (house_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Voting villa was not found")
    if not election["allow_defaulters_to_vote"] and is_active_defaulter(cur, house_id):
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
    cur.execute("SELECT house_id FROM residents WHERE user_id = %s", (submitter_user_id,))
    submitter = cur.fetchone()
    if submitter and submitter["house_id"] == house_id:
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


def calculate_results(cur, election_id: str, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        threshold = passing_threshold(question)
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


def passing_threshold(question: dict[str, Any]) -> float:
    if question["passing_rule"] == "two_thirds":
        return 66.667
    if question["passing_rule"] == "custom_threshold":
        return float(question["passing_threshold_percent"] or 50)
    return 50.0
