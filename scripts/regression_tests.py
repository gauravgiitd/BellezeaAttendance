#!/usr/bin/env python3
"""Regression harness for the Nambiar Bellezea Elections backend.

The harness runs directly against the configured Postgres database and calls the
FastAPI endpoint functions in-process. It creates synthetic villas, residents,
and elections with a stable prefix, then removes them after the run.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import io
import os
import sys
import traceback
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_DATABASE_URL = f"postgresql://{getpass.getuser()}@127.0.0.1:5432/bellezea_elections"
TEST_PREFIX = "Regression Harness"
PROXY_REPORT_HEADER = "Grantor Villa,Proxy Holder Villa,Proxy Holder Name,Attendance Mode,Proxy Holder Email"

VILLA_A = "990001"
VILLA_B = "990002"
VILLA_C = "990003"
VILLA_TENANT_ONLY = "990004"
VILLA_MULTI_HOME = "990005"

OWNER_A1 = "980001"
OWNER_A2 = "980002"
OWNER_B1 = "980003"
OWNER_C1 = "980004"
TENANT_ONLY = "980005"

PASSCODE_A1 = "970001"
PASSCODE_TENANT_ONLY = "970005"

TEST_HOUSE_IDS = [VILLA_A, VILLA_B, VILLA_C, VILLA_TENANT_ONLY, VILLA_MULTI_HOME]
TEST_USER_IDS = [OWNER_A1, OWNER_A2, OWNER_B1, OWNER_C1, TENANT_ONLY]

SYNTHETIC_VILLAS = [
    (VILLA_A, "Harness Villa A"),
    (VILLA_B, "Harness Villa B"),
    (VILLA_C, "Harness Villa C"),
    (VILLA_TENANT_ONLY, "Harness Tenant Only"),
    (VILLA_MULTI_HOME, "Harness Multi Home"),
]

SYNTHETIC_RESIDENTS = [
    (OWNER_A1, VILLA_A, PASSCODE_A1, "Harness Owner A1", "Owner", "Active"),
    (OWNER_A2, VILLA_A, "970002", "Harness Owner A2", "Co-Owner", "Active"),
    (OWNER_B1, VILLA_B, "970003", "Harness Proxy Holder", "Owner", "Active"),
    (OWNER_C1, VILLA_C, "970004", "Harness Owner C", "Owner", "Active"),
    (TENANT_ONLY, VILLA_TENANT_ONLY, PASSCODE_TENANT_ONLY, "Harness Tenant", "Tenant", "Active"),
    (OWNER_A1, VILLA_MULTI_HOME, "970006", "Harness Owner A1 Second Home", "Owner", "Active"),
]

DEFAULT_CHOICES = ("Choice A", "Choice B", "Choice C")


def configure_environment(database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    os.environ["OFFICER_AUTH_DISABLED"] = "true"
    os.environ["AUTO_MIGRATE"] = "false"


def import_api():
    from backend.app import main as api
    from backend.app.db import connection, initialize_schema

    return api, connection, initialize_schema


@dataclass
class TestResult:
    name: str
    passed: bool
    error: str = ""


def delete_test_elections(cur: Any) -> None:
    cur.execute("DELETE FROM elections WHERE title LIKE %s", (f"{TEST_PREFIX}:%",))


def question_choices(api: Any, choices: tuple[str, ...] = DEFAULT_CHOICES, with_images: bool = False) -> list[Any]:
    return [
        api.QuestionChoiceCreate(
            choice_text=choice,
            image_url=f"https://example.com/{index + 1}.png" if with_images else None,
        )
        for index, choice in enumerate(choices)
    ]


class RegressionHarness:
    def __init__(self, keep_data: bool = False) -> None:
        self.api, self.connection, self.initialize_schema = import_api()
        self.keep_data = keep_data

    def run(self) -> int:
        self.initialize_schema()
        self.cleanup_all()
        self.seed_residents()

        tests: list[Callable[[], None]] = [
            self.test_resident_directory_and_qr_rules,
            self.test_resident_sync_cleanup,
            self.test_election_backup_sheet_rows,
            self.test_election_lifecycle_and_locks,
            self.test_attendance_marks_all_owners_and_is_idempotent,
            self.test_attendance_stage_rules_and_qr_validation,
            self.test_defaulter_exclusion_and_inclusion,
            self.test_grantor_cannot_be_marked_directly_after_proxy_representation,
            self.test_proxy_management_and_reports,
            self.test_proxy_changes_during_attendance_reconcile_attendees,
            self.test_proxy_holder_can_be_any_owner_in_attending_villa,
            self.test_remove_actual_attendance_removes_owner_and_proxy_villas,
            self.test_defaulter_proxy_report_exclusion,
            self.test_voting_ballots_results_and_restart,
            self.test_public_attendance_board,
        ]

        results: list[TestResult] = []
        try:
            for test in tests:
                self.cleanup_test_elections()
                try:
                    test()
                    results.append(TestResult(test.__name__, True))
                    print(f"PASS {test.__name__}")
                except Exception:
                    results.append(TestResult(test.__name__, False, traceback.format_exc()))
                    print(f"FAIL {test.__name__}")
                    print(results[-1].error)
        finally:
            if self.keep_data:
                print("Keeping synthetic test data because --keep-data was supplied.")
            else:
                self.cleanup_all()

        failed = [result for result in results if not result.passed]
        print()
        print(f"{len(results) - len(failed)}/{len(results)} tests passed")
        return 1 if failed else 0

    def seed_residents(self) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                for house_id, house_no in SYNTHETIC_VILLAS:
                    cur.execute(
                        """
                        INSERT INTO villas (house_id, house_no, updated_at)
                        VALUES (%s, %s, now())
                        ON CONFLICT (house_id)
                        DO UPDATE SET house_no = EXCLUDED.house_no, updated_at = now()
                        """,
                        (house_id, house_no),
                    )
                for user_id, house_id, passcode, name, user_type, status in SYNTHETIC_RESIDENTS:
                    cur.execute(
                        """
                        INSERT INTO residents (
                          user_id, house_id, passcode, name, user_type, status,
                          mobile_no, email, raw_payload, updated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, '', '', '{}'::jsonb, now())
                        ON CONFLICT (user_id, house_id)
                        DO UPDATE SET
                          passcode = EXCLUDED.passcode,
                          name = EXCLUDED.name,
                          user_type = EXCLUDED.user_type,
                          status = EXCLUDED.status,
                          updated_at = now()
                        """,
                        (user_id, house_id, passcode, name, user_type, status),
                    )
            conn.commit()

    def cleanup_test_elections(self) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                delete_test_elections(cur)
            conn.commit()

    def cleanup_all(self) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                delete_test_elections(cur)
                cur.execute(
                    "DELETE FROM residents WHERE house_id = ANY(%s) OR user_id = ANY(%s)",
                    (TEST_HOUSE_IDS, TEST_USER_IDS),
                )
                cur.execute("DELETE FROM villas WHERE house_id = ANY(%s)", (TEST_HOUSE_IDS,))
            conn.commit()

    def create_election(
        self,
        name: str,
        *,
        voting_enabled: bool = False,
        quorum_percent: str = "0.1",
        include_defaulters: bool = False,
        allow_defaulters_to_vote: bool = False,
        passing_rule: str = "simple_majority",
        passing_threshold_percent: str | None = None,
        attendance_modes: list[str] | None = None,
    ) -> dict[str, Any]:
        election = self.api.create_election(
            self.api.ElectionCreate(
                title=f"{TEST_PREFIX}: {name}",
                description="Created by scripts/regression_tests.py",
                quorum_percent=Decimal(quorum_percent),
                voting_enabled=voting_enabled,
                attendance_modes=attendance_modes or ["Physical", "Virtual"],
                passing_rule=passing_rule,
                passing_threshold_percent=(
                    Decimal(passing_threshold_percent) if passing_threshold_percent is not None else None
                ),
                include_defaulters_in_quorum=include_defaulters,
                allow_defaulters_to_vote=allow_defaulters_to_vote,
            )
        )
        return election

    def add_question(
        self,
        election_id: str,
        question_text: str = "Choose an option",
        choices: tuple[str, ...] = DEFAULT_CHOICES,
    ) -> dict[str, Any]:
        return self.api.add_question(
            election_id,
            self.api.QuestionCreate(
                question_text=question_text,
                image_url="https://example.com/question.png",
                choices=question_choices(self.api, choices, with_images=True),
            ),
        )

    def set_status(self, election_id: str, status: str) -> dict[str, Any]:
        return self.api.update_election_status(election_id, self.api.ElectionStatusUpdate(status=status))

    def mark_manual(self, election_id: str, house_id: str, attendance_mode: str = "Physical") -> dict[str, Any]:
        return self.api.mark_manual_attendance(
            election_id,
            self.api.AttendanceManualRequest(house_id=house_id, source="regression", attendance_mode=attendance_mode),
        )

    def mark_qr(self, election_id: str, qr_raw_data: str, attendance_mode: str = "Physical") -> dict[str, Any]:
        return self.api.mark_qr_attendance(
            election_id,
            self.api.AttendanceQrRequest(
                qr_raw_data=qr_raw_data,
                method="qr_scan",
                source="regression",
                attendance_mode=attendance_mode,
            ),
        )

    def remove_attendance(self, election_id: str, house_id: str) -> dict[str, Any]:
        return self.api.remove_actual_attendance(election_id, house_id)

    def create_proxy(
        self,
        election_id: str,
        grantor_house_id: str,
        proxy_holder_user_id: str = OWNER_B1,
        proxy_holder_house_id: str = VILLA_B,
        email: str = "Proxy.Holder@Example.COM",
    ) -> dict[str, Any]:
        return self.api.create_proxy(
            self.api.ProxyCreate(
                election_id=election_id,
                grantor_house_id=grantor_house_id,
                proxy_holder_user_id=proxy_holder_user_id,
                proxy_holder_house_id=proxy_holder_house_id,
                proxy_holder_email=email,
            )
        )

    def cancel_proxy(self, proxy_id: str) -> dict[str, Any]:
        return self.api.cancel_proxy(proxy_id)

    def add_defaulter(self, election_id: str, house_id: str) -> dict[str, Any]:
        return self.api.create_defaulter(
            self.api.DefaulterCreate(election_id=election_id, house_id=house_id, reason="regression")
        )

    def submit_ballot(
        self,
        election_id: str,
        submitted_by_user_id: str,
        house_id: str,
        question: dict[str, Any],
        choice_index: int,
    ) -> dict[str, Any]:
        choice = question["choices"][choice_index]
        return self.api.submit_ballot(
            election_id,
            self.api.BallotSubmitRequest(
                submitted_by_user_id=submitted_by_user_id,
                house_id=house_id,
                answers=[
                    self.api.BallotAnswerRequest(question_id=question["id"], choice_id=choice["id"]),
                ],
            ),
        )

    def csv_rows(self, response: Any) -> list[dict[str, str]]:
        body = response.body.decode("utf-8")
        return list(csv.DictReader(io.StringIO(body)))

    def csv_lines(self, response: Any) -> list[str]:
        return response.body.decode("utf-8").strip().splitlines()

    def expect_http_error(
        self,
        status_code: int,
        fn: Callable[[], Any],
        expected_detail: str | None = None,
    ) -> None:
        try:
            fn()
        except HTTPException as exc:
            assert exc.status_code == status_code, f"expected {status_code}, got {exc.status_code}: {exc.detail}"
            if expected_detail:
                assert expected_detail in str(exc.detail), f"expected detail containing {expected_detail!r}, got {exc.detail!r}"
            return
        raise AssertionError(f"expected HTTPException {status_code}")

    def dashboard_row(self, election_id: str, house_id: str, representation_type: str = "self") -> dict[str, Any]:
        dashboard = self.api.attendance_dashboard(election_id)
        for row in dashboard["attendees"]:
            if row["house_id"] == house_id and row["representationType"] == representation_type:
                return row
        raise AssertionError(f"dashboard row not found: {house_id} {representation_type}")

    def test_resident_directory_and_qr_rules(self) -> None:
        directory = self.api.resident_directory()
        by_house = {row["house_id"]: row for row in directory}

        assert len(by_house[VILLA_A]["owners"]) == 2
        assert by_house[VILLA_TENANT_ONLY]["owners"] == []

        login = self.api.qr_login(self.api.AttendanceQrRequest(qr_raw_data=f"{PASSCODE_A1} mygate payload"))
        assert login["resident"]["user_id"] == OWNER_A1

        self.expect_http_error(
            403,
            lambda: self.api.qr_login(self.api.AttendanceQrRequest(qr_raw_data=f"{PASSCODE_TENANT_ONLY} mygate payload")),
            "Only owner-type",
        )

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS count FROM residents WHERE user_id = %s", (OWNER_A1,))
                assert int(cur.fetchone()["count"]) == 2

    def test_resident_sync_cleanup(self) -> None:
        stale_house_id = "888888"
        stale_user_id = "888001"
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO villas (house_id, house_no, updated_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (house_id) DO UPDATE SET house_no = EXCLUDED.house_no, updated_at = now()
                    """,
                    (stale_house_id, "Harness Stale Villa"),
                )
                cur.execute(
                    """
                    INSERT INTO residents (
                      user_id, house_id, passcode, name, user_type, status,
                      mobile_no, email, raw_payload, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, '', '', '{}'::jsonb, now())
                    ON CONFLICT (user_id, house_id) DO UPDATE SET
                      name = EXCLUDED.name,
                      updated_at = now()
                    """,
                    (stale_user_id, stale_house_id, "888001", "Harness Stale Resident", "Owner", "Active"),
                )
                cur.execute(
                    """
                    SELECT user_id, house_id
                    FROM residents
                    WHERE NOT (user_id = %s AND house_id = %s)
                    """,
                    (stale_user_id, stale_house_id),
                )
                keep_rows = cur.fetchall()
                imported_user_ids = [row["user_id"] for row in keep_rows]
                imported_house_ids = [row["house_id"] for row in keep_rows]

                cleanup = self.api.cleanup_residents_after_import(
                    cur, imported_user_ids, imported_house_ids
                )
                cur.execute("SELECT 1 FROM residents WHERE user_id = %s AND house_id = %s", (stale_user_id, stale_house_id))
                assert cur.fetchone() is None
                cur.execute("SELECT 1 FROM villas WHERE house_id = %s", (stale_house_id,))
                assert cur.fetchone() is None
                cur.execute("SELECT 1 FROM residents WHERE user_id = %s AND house_id = %s", (OWNER_A1, VILLA_A))
                assert cur.fetchone() is not None
                assert cleanup["removed_residents"] == 1
                assert cleanup["removed_villas"] == 1
            conn.rollback()

    def test_election_backup_sheet_rows(self) -> None:
        from backend.app.integrations.election_backup_sheet.queries import (
            DATA_START_ROW,
            build_attendance_sheet_rows,
        )

        election = self.create_election("backup sheet rows")
        election_id = election["id"]
        self.add_defaulter(election_id, VILLA_C)
        self.set_status(election_id, "attendance_open")
        self.create_proxy(election_id, VILLA_A)
        self.mark_manual(election_id, VILLA_B, attendance_mode="Virtual")
        self.mark_manual(election_id, VILLA_C, attendance_mode="Physical")

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM elections WHERE id = %s", (election_id,))
                election_row = cur.fetchone()
                headers, summary_row, rows = build_attendance_sheet_rows(cur, election_row)

        assert headers == [
            "Villa #",
            "Proxy?",
            "Proxy Villa",
            "Defaulter?",
            "Physical",
            "Virtual",
            "Attended",
            "Attendance %",
        ]
        last_row = DATA_START_ROW + len(rows) - 1

        assert summary_row[0] == f"=COUNTA(A{DATA_START_ROW}:A{last_row})"
        assert summary_row[1] == f'=COUNTIF(B{DATA_START_ROW}:B{last_row},"Yes")'
        assert summary_row[3] == f'=COUNTIF(D{DATA_START_ROW}:D{last_row},"Yes")'
        assert summary_row[4] == f'=COUNTIF(E{DATA_START_ROW}:E{last_row},"Yes")'
        assert summary_row[5] == f'=COUNTIF(F{DATA_START_ROW}:F{last_row},"Yes")'
        assert summary_row[6] == f'=COUNTIF(G{DATA_START_ROW}:G{last_row},"Yes")'
        assert summary_row[7] == "=IF(A1-D1=0,0,G1/(A1-D1)*100)"

        rows_by_villa = {row[0]: row for row in rows}

        def sheet_row_number(villa_name: str) -> int:
            row_index = next(index for index, row in enumerate(rows) if row[0] == villa_name)
            return DATA_START_ROW + row_index

        grantor_row = rows_by_villa["Harness Villa A"]
        assert grantor_row[1:6] == ["Yes", "Harness Villa B", "", "", "Yes"]
        grantor_row_number = sheet_row_number("Harness Villa A")
        assert grantor_row[6] == f'=IF(OR(E{grantor_row_number}="Yes",F{grantor_row_number}="Yes"),"Yes","")'

        holder_row = rows_by_villa["Harness Villa B"]
        assert holder_row[1:6] == ["", "", "", "", "Yes"]
        holder_row_number = sheet_row_number("Harness Villa B")
        assert holder_row[6] == f'=IF(OR(E{holder_row_number}="Yes",F{holder_row_number}="Yes"),"Yes","")'

        defaulter_row = rows_by_villa["Harness Villa C"]
        assert defaulter_row[1:6] == ["", "", "Yes", "Excluded", ""]
        defaulter_row_number = sheet_row_number("Harness Villa C")
        assert defaulter_row[6] == f'=IF(OR(E{defaulter_row_number}="Yes",F{defaulter_row_number}="Yes"),"Yes","")'

        untouched_row = rows_by_villa["Harness Tenant Only"]
        assert untouched_row[1:6] == ["", "", "", "", ""]
        untouched_row_number = sheet_row_number("Harness Tenant Only")
        assert untouched_row[6] == f'=IF(OR(E{untouched_row_number}="Yes",F{untouched_row_number}="Yes"),"Yes","")'

        included = self.create_election("backup sheet rows included defaulters", include_defaulters=True)
        included_id = included["id"]
        self.add_defaulter(included_id, VILLA_C)
        self.set_status(included_id, "attendance_open")
        self.mark_manual(included_id, VILLA_C, attendance_mode="Physical")

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM elections WHERE id = %s", (included_id,))
                included_row = cur.fetchone()
                _, included_summary, included_rows = build_attendance_sheet_rows(cur, included_row)

        included_last_row = DATA_START_ROW + len(included_rows) - 1
        assert included_summary[7] == "=IF(A1=0,0,G1/A1*100)"
        included_by_villa = {row[0]: row for row in included_rows}
        assert included_by_villa["Harness Villa C"][1:6] == ["", "", "Yes", "Yes", ""]
        assert included_summary[0] == f"=COUNTA(A{DATA_START_ROW}:A{included_last_row})"

        direct_grantor = self.create_election("backup sheet grantor direct with proxy")
        direct_id = direct_grantor["id"]
        self.set_status(direct_id, "attendance_open")
        self.mark_manual(direct_id, VILLA_A, attendance_mode="Physical")
        self.create_proxy(direct_id, VILLA_A)
        self.mark_manual(direct_id, VILLA_B, attendance_mode="Virtual")

        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM elections WHERE id = %s", (direct_id,))
                direct_row = cur.fetchone()
                _, _, direct_rows = build_attendance_sheet_rows(cur, direct_row)

        direct_by_villa = {row[0]: row for row in direct_rows}
        assert direct_by_villa["Harness Villa A"][1:6] == ["Yes", "Harness Villa B", "", "Yes", ""]
        assert direct_by_villa["Harness Villa B"][1:6] == ["", "", "", "", "Yes"]

    def test_election_lifecycle_and_locks(self) -> None:
        voting_election = self.create_election("lifecycle locks", voting_enabled=True, quorum_percent="99")
        election_id = voting_election["id"]

        self.expect_http_error(409, lambda: self.set_status(election_id, "attendance_open"), "Add at least one question")
        question = self.add_question(election_id)
        assert len(question["choices"]) == 3
        assert question["image_url"] == "https://example.com/question.png"

        self.set_status(election_id, "attendance_open")

        updated_question = self.api.update_question(
            election_id,
            question["id"],
            self.api.QuestionUpdate(
                question_text="Updated during attendance",
                image_url="https://example.com/updated.png",
                choices=question_choices(self.api),
            ),
        )
        assert updated_question["question_text"] == "Updated during attendance"

        self.expect_http_error(
            409,
            lambda: self.api.update_election(
                election_id,
                self.api.ElectionUpdate(
                    title=f"{TEST_PREFIX}: should not update",
                    quorum_percent=Decimal("25"),
                    voting_enabled=True,
                ),
            ),
            "locked",
        )
        proxy_during_attendance = self.create_proxy(election_id, VILLA_A)
        assert proxy_during_attendance["grantor_house_id"] == VILLA_A
        self.expect_http_error(409, lambda: self.add_defaulter(election_id, VILLA_C), "locked")
        self.expect_http_error(409, lambda: self.set_status(election_id, "voting_open"), "Quorum")

        patched = self.api.update_election_quorum(
            election_id,
            self.api.ElectionQuorumUpdate(quorum_percent=Decimal("0.1")),
        )
        assert patched["quorum_percent"] == 0.1

        self.mark_manual(election_id, VILLA_A)
        self.set_status(election_id, "voting_open")
        self.expect_http_error(
            409,
            lambda: self.api.update_question(
                election_id,
                question["id"],
                self.api.QuestionUpdate(
                    question_text="Blocked",
                    choices=question_choices(self.api, DEFAULT_CHOICES[:2]),
                ),
            ),
            "locked",
        )
        self.expect_http_error(
            409,
            lambda: self.api.update_election_quorum(
                election_id,
                self.api.ElectionQuorumUpdate(quorum_percent=Decimal("1")),
            ),
            "locked",
        )
        self.expect_http_error(409, lambda: self.create_proxy(election_id, VILLA_C), "locked")

    def test_attendance_marks_all_owners_and_is_idempotent(self) -> None:
        election = self.create_election("actual attendance", attendance_modes=["Physical", "Virtual", "Clubhouse"])
        assert election["attendance_modes"] == ["Physical", "Virtual", "Clubhouse"]
        election_id = election["id"]
        self.set_status(election_id, "attendance_open")

        self.mark_manual(election_id, VILLA_A, attendance_mode="Virtual")
        self.expect_http_error(
            409,
            lambda: self.mark_manual(election_id, VILLA_A, attendance_mode="Virtual"),
            "already been recorded",
        )
        self.expect_http_error(
            409,
            lambda: self.mark_manual(election_id, VILLA_A, attendance_mode="Physical"),
            "already been recorded",
        )

        row = self.dashboard_row(election_id, VILLA_A)
        assert row["counted"] is True
        assert row["attendanceMode"] == "Virtual"
        assert len(row["participants"]) == 2
        assert {person["attendance_mode"] for person in row["participants"]} == {"Virtual"}

        dashboard = self.api.attendance_dashboard(election_id)
        assert dashboard["representedVillas"] == 1

        rows = self.csv_rows(self.api.actual_attendee_report(election_id))
        assert {(row["Name"], row["Attendance Mode"], row["House Id (Do Not Edit)"]) for row in rows} == {
            ("Harness Owner A1", "Virtual", VILLA_A),
            ("Harness Owner A2", "Virtual", VILLA_A),
        }

    def test_attendance_stage_rules_and_qr_validation(self) -> None:
        election = self.create_election("attendance rules")
        election_id = election["id"]

        self.expect_http_error(409, lambda: self.mark_manual(election_id, VILLA_A), "Attendance can be marked")
        self.set_status(election_id, "attendance_open")

        self.mark_qr(election_id, f"{PASSCODE_A1} online qr payload")
        self.expect_http_error(400, lambda: self.mark_qr(election_id, "no-passcode-here"), "extract passcode")
        self.expect_http_error(400, lambda: self.mark_manual(election_id, VILLA_B, attendance_mode="Phone"), "Attendance mode")
        self.expect_http_error(403, lambda: self.mark_qr(election_id, f"{PASSCODE_TENANT_ONLY} payload"), "Only owner-type")
        self.set_status(election_id, "voting_closed")
        self.expect_http_error(409, lambda: self.mark_manual(election_id, VILLA_B), "Attendance can be marked")
        reopened = self.set_status(election_id, "attendance_open")
        assert reopened["status"] == "attendance_open"
        self.mark_manual(election_id, VILLA_B)

        voting_election = self.create_election("attendance during voting", voting_enabled=True, quorum_percent="0.1")
        voting_election_id = voting_election["id"]
        self.add_question(voting_election_id)
        self.set_status(voting_election_id, "attendance_open")
        self.mark_manual(voting_election_id, VILLA_A)
        self.set_status(voting_election_id, "voting_open")
        self.mark_manual(voting_election_id, VILLA_B)
        assert self.dashboard_row(voting_election_id, VILLA_B)["counted"] is True

        self.set_status(election_id, "voting_closed")
        self.expect_http_error(409, lambda: self.mark_manual(election_id, VILLA_B), "Attendance can be marked")

    def test_defaulter_exclusion_and_inclusion(self) -> None:
        excluded = self.create_election("defaulter excluded", include_defaulters=False)
        excluded_id = excluded["id"]
        self.add_defaulter(excluded_id, VILLA_C)
        self.set_status(excluded_id, "attendance_open")
        self.mark_manual(excluded_id, VILLA_C)

        row = self.dashboard_row(excluded_id, VILLA_C)
        assert row["isDefaulter"] is True
        assert row["counted"] is False
        assert self.api.attendance_dashboard(excluded_id)["representedVillas"] == 0
        assert self.csv_rows(self.api.actual_attendee_report(excluded_id)) == []

        included = self.create_election("defaulter included", include_defaulters=True)
        included_id = included["id"]
        self.add_defaulter(included_id, VILLA_C)
        self.set_status(included_id, "attendance_open")
        self.mark_manual(included_id, VILLA_C)

        included_row = self.dashboard_row(included_id, VILLA_C)
        assert included_row["isDefaulter"] is True
        assert included_row["counted"] is True
        assert self.api.attendance_dashboard(included_id)["representedVillas"] == 1
        rows = self.csv_rows(self.api.actual_attendee_report(included_id))
        assert [row["Name"] for row in rows] == ["Harness Owner C"]

    def test_grantor_cannot_be_marked_directly_after_proxy_representation(self) -> None:
        election = self.create_election("grantor direct blocked after proxy")
        election_id = election["id"]
        self.create_proxy(election_id, VILLA_A)
        self.set_status(election_id, "attendance_open")
        self.mark_manual(election_id, VILLA_B)

        proxy_row = self.dashboard_row(election_id, VILLA_A, "proxy")
        assert proxy_row["counted"] is True
        assert proxy_row["isProxy"] is True

        self.expect_http_error(
            409,
            lambda: self.mark_manual(election_id, VILLA_A),
            "already been recorded",
        )

        dashboard = self.api.attendance_dashboard(election_id)
        grantor_rows = [
            row for row in dashboard["attendees"]
            if row["house_id"] == VILLA_A
        ]
        assert len(grantor_rows) == 1
        assert grantor_rows[0]["representationType"] == "proxy"

    def test_proxy_management_and_reports(self) -> None:
        election = self.create_election("proxy reports")
        election_id = election["id"]

        proxy = self.create_proxy(election_id, VILLA_A)
        assert proxy["proxy_holder_email"] == "proxy.holder@example.com"
        self.expect_http_error(409, lambda: self.create_proxy(election_id, VILLA_A), "active proxy")
        self.expect_http_error(
            403,
            lambda: self.create_proxy(
                election_id,
                VILLA_C,
                proxy_holder_user_id=TENANT_ONLY,
                proxy_holder_house_id=VILLA_TENANT_ONLY,
            ),
            "owner-type",
        )

        listed = self.api.list_proxies(election_id)
        assert len(listed) == 1
        assert listed[0]["proxy_holder_email"] == "proxy.holder@example.com"

        self.set_status(election_id, "attendance_open")
        self.mark_manual(election_id, VILLA_B)

        proxy_row = self.dashboard_row(election_id, VILLA_A, "proxy")
        assert proxy_row["counted"] is True
        assert proxy_row["isProxy"] is True

        actual_rows = self.csv_rows(self.api.actual_attendee_report(election_id))
        assert [row["Name"] for row in actual_rows] == ["Harness Proxy Holder"]
        proxy_rows = self.csv_rows(self.api.proxy_holder_email_report(election_id))
        assert proxy_rows == [
            {
                "Grantor Villa": "Harness Villa A",
                "Proxy Holder Villa": "Harness Villa B",
                "Proxy Holder Name": "Harness Proxy Holder",
                "Attendance Mode": "Physical",
                "Proxy Holder Email": "proxy.holder@example.com",
            }
        ]

    def test_proxy_changes_during_attendance_reconcile_attendees(self) -> None:
        election = self.create_election("proxy changes during attendance")
        election_id = election["id"]
        self.set_status(election_id, "attendance_open")
        self.mark_manual(election_id, VILLA_B)

        proxy = self.create_proxy(election_id, VILLA_A)
        proxy_row = self.dashboard_row(election_id, VILLA_A, "proxy")
        assert proxy_row["counted"] is True
        assert proxy_row["participants"][0]["user_id"] == OWNER_B1

        cancelled = self.cancel_proxy(proxy["id"])
        assert cancelled["status"] == "cancelled"
        dashboard = self.api.attendance_dashboard(election_id)
        assert not any(row["house_id"] == VILLA_A and row["representationType"] == "proxy" for row in dashboard["attendees"])

    def test_proxy_holder_can_be_any_owner_in_attending_villa(self) -> None:
        election = self.create_election("proxy holder second owner")
        election_id = election["id"]
        self.create_proxy(
            election_id,
            grantor_house_id=VILLA_C,
            proxy_holder_user_id=OWNER_A2,
            proxy_holder_house_id=VILLA_A,
            email="Second.Owner.Proxy@Example.COM",
        )

        self.set_status(election_id, "attendance_open")
        self.mark_manual(election_id, VILLA_A)

        proxy_row = self.dashboard_row(election_id, VILLA_C, "proxy")
        assert proxy_row["counted"] is True
        assert proxy_row["participants"][0]["user_id"] == OWNER_A2
        assert self.csv_rows(self.api.proxy_holder_email_report(election_id)) == [
            {
                "Grantor Villa": "Harness Villa C",
                "Proxy Holder Villa": "Harness Villa A",
                "Proxy Holder Name": "Harness Owner A2",
                "Attendance Mode": "Physical",
                "Proxy Holder Email": "second.owner.proxy@example.com",
            }
        ]

    def test_remove_actual_attendance_removes_owner_and_proxy_villas(self) -> None:
        election = self.create_election("remove actual attendance")
        election_id = election["id"]
        self.create_proxy(election_id, grantor_house_id=VILLA_C, proxy_holder_user_id=OWNER_A2, proxy_holder_house_id=VILLA_A)

        self.set_status(election_id, "attendance_open")
        self.mark_manual(election_id, VILLA_A)
        assert self.dashboard_row(election_id, VILLA_A, "self")["counted"] is True
        assert self.dashboard_row(election_id, VILLA_C, "proxy")["counted"] is True

        removed = self.remove_attendance(election_id, VILLA_A)
        assert removed["removed_attendance_records"] == 2
        assert removed["removed_representations"] == 2
        assert removed["removed_proxy_villas"] == 1

        dashboard = self.api.attendance_dashboard(election_id)
        assert dashboard["representedVillas"] == 0
        assert not any(row["house_id"] in {VILLA_A, VILLA_C} for row in dashboard["attendees"])
        assert self.csv_rows(self.api.actual_attendee_report(election_id)) == []
        assert self.csv_lines(self.api.proxy_holder_email_report(election_id)) == [PROXY_REPORT_HEADER]

    def test_defaulter_proxy_report_exclusion(self) -> None:
        election = self.create_election("defaulter proxy excluded")
        election_id = election["id"]
        self.add_defaulter(election_id, VILLA_C)
        self.create_proxy(election_id, VILLA_C, email="Defaulter.Proxy@Example.COM")

        self.set_status(election_id, "attendance_open")
        self.mark_manual(election_id, VILLA_B)

        proxy_row = self.dashboard_row(election_id, VILLA_C, "proxy")
        assert proxy_row["isDefaulter"] is True
        assert proxy_row["counted"] is False
        assert self.csv_lines(self.api.proxy_holder_email_report(election_id)) == [PROXY_REPORT_HEADER]

    def test_voting_ballots_results_and_restart(self) -> None:
        election = self.create_election("voting", voting_enabled=True, quorum_percent="0.1")
        election_id = election["id"]
        question = self.add_question(election_id)
        self.create_proxy(election_id, VILLA_C)

        self.set_status(election_id, "attendance_open")
        self.mark_manual(election_id, VILLA_A)
        self.mark_manual(election_id, VILLA_B)
        self.set_status(election_id, "voting_open")

        self.expect_http_error(
            403,
            lambda: self.submit_ballot(election_id, OWNER_A1, VILLA_C, question, 0),
            "does not represent",
        )
        self.submit_ballot(election_id, OWNER_A1, VILLA_A, question, 0)
        self.submit_ballot(election_id, OWNER_B1, VILLA_C, question, 1)
        self.expect_http_error(
            409,
            lambda: self.submit_ballot(election_id, OWNER_A2, VILLA_A, question, 2),
            "already been submitted",
        )
        self.expect_http_error(400, lambda: self.api.election_results(election_id), "after voting is closed")

        voter_dashboard = self.api.voter_dashboard(OWNER_B1)
        election_payload = next(item for item in voter_dashboard["elections"] if item["election"]["id"] == election_id)
        represented = {row["house_id"]: row["representation_type"] for row in election_payload["represented_houses"]}
        assert represented[VILLA_B] == "own"
        assert represented[VILLA_C] == "proxy"

        status = self.api.election_voting_status(election_id)
        assert status["voted_villas"] == 2

        self.set_status(election_id, "voting_closed")
        results = self.api.election_results(election_id)
        assert results["voted_villas"] == 2
        assert results["questions"][0]["total_votes"] == 2
        assert results["questions"][0]["passed"] is True

        restarted = self.api.restart_voting(election_id)
        assert restarted["status"] == "voting_open"
        assert self.api.election_voting_status(election_id)["voted_villas"] == 0

    def test_public_attendance_board(self) -> None:
        open_election = self.create_election("public board open")
        closed_election = self.create_election("public board closed")
        self.set_status(open_election["id"], "attendance_open")
        self.set_status(closed_election["id"], "attendance_open")
        self.set_status(closed_election["id"], "voting_closed")

        board = self.api.public_attendance_board()
        ids = {item["election"]["id"] for item in board["elections"]}
        assert open_election["id"] in ids
        assert closed_election["id"] not in ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Bellezea Elections backend regression tests.")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="Postgres DATABASE_URL to test against. Defaults to DATABASE_URL or a local bellezea_elections database.",
    )
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="Keep synthetic residents/villas and test elections after the run for debugging.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_environment(args.database_url)
    print(f"Running regression tests against {args.database_url}")
    print("Synthetic test elections are prefixed with 'Regression Harness:'.")
    return RegressionHarness(keep_data=args.keep_data).run()


if __name__ == "__main__":
    raise SystemExit(main())
