from __future__ import annotations

import json
from typing import Any

DEFAULT_ATTENDANCE_MODES = ["Physical", "Virtual"]

BASE_HEADERS = ("Villa #", "Proxy?", "Proxy Villa", "Defaulter?")
ATTENDED_HEADER = "Attended"
ATTENDANCE_PCT_HEADER = "Attendance %"
DATA_START_ROW = 3


def normalize_attendance_modes(values: list[str] | str | None) -> list[str]:
    if values is None:
        return DEFAULT_ATTENDANCE_MODES.copy()
    if isinstance(values, str):
        try:
            parsed = json.loads(values)
            if isinstance(parsed, list):
                values = parsed
            else:
                values = values.split(",")
        except json.JSONDecodeError:
            values = values.split(",")
    modes = [str(item).strip() for item in values if str(item).strip()]
    return modes or DEFAULT_ATTENDANCE_MODES.copy()


def attendance_sheet_headers(attendance_modes: list[str]) -> list[str]:
    return list(BASE_HEADERS) + list(attendance_modes) + [ATTENDED_HEADER, ATTENDANCE_PCT_HEADER]


def column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def first_mode_column_index() -> int:
    return len(BASE_HEADERS) + 1


def attended_column_index(mode_count: int) -> int:
    return len(BASE_HEADERS) + mode_count + 1


def attendance_pct_column_index(mode_count: int) -> int:
    return attended_column_index(mode_count) + 1


def mode_cell_value(
    attended_mode: str | None,
    mode: str,
    is_defaulter: bool,
    *,
    include_defaulters_in_quorum: bool,
) -> str:
    if not attended_mode:
        return ""
    if attended_mode.casefold() != mode.casefold():
        return ""
    if is_defaulter and not include_defaulters_in_quorum:
        return "Excluded"
    return "Yes"


def attended_row_formula(row_number: int, mode_count: int) -> str:
    if mode_count == 0:
        return ""
    mode_start = first_mode_column_index()
    checks = ",".join(
        f'{column_letter(mode_start + index)}{row_number}="Yes"'
        for index in range(mode_count)
    )
    return f'=IF(OR({checks}),"Yes","")'


def resolve_proxy_attendance(
    grantor_house_id: str,
    proxy: dict[str, Any],
    attendance_mode_by_house: dict[str, str],
    defaulter_house_ids: set[str],
) -> tuple[str | None, bool]:
    grantor_attended_mode = attendance_mode_by_house.get(grantor_house_id)
    if grantor_attended_mode:
        return grantor_attended_mode, grantor_house_id in defaulter_house_ids

    holder_house_id = proxy["proxy_holder_house_id"]
    holder_attended_mode = attendance_mode_by_house.get(holder_house_id)
    return holder_attended_mode, holder_house_id in defaulter_house_ids


def build_summary_row(
    villa_count: int,
    mode_count: int,
    *,
    include_defaulters_in_quorum: bool,
) -> list[str]:
    if villa_count == 0:
        return [""] * attendance_pct_column_index(mode_count)

    last_data_row = DATA_START_ROW + villa_count - 1
    attended_col = column_letter(attended_column_index(mode_count))

    summary: list[str] = [
        f"=COUNTA(A{DATA_START_ROW}:A{last_data_row})",
        f'=COUNTIF(B{DATA_START_ROW}:B{last_data_row},"Yes")',
        "",
        f'=COUNTIF(D{DATA_START_ROW}:D{last_data_row},"Yes")',
    ]
    for index in range(mode_count):
        mode_col = column_letter(first_mode_column_index() + index)
        summary.append(f'=COUNTIF({mode_col}{DATA_START_ROW}:{mode_col}{last_data_row},"Yes")')
    summary.append(f'=COUNTIF({attended_col}{DATA_START_ROW}:{attended_col}{last_data_row},"Yes")')
    if include_defaulters_in_quorum:
        summary.append(f"=IF(A1=0,0,{attended_col}1/A1*100)")
    else:
        summary.append(f"=IF(A1-D1=0,0,{attended_col}1/(A1-D1)*100)")
    return summary


def build_attendance_sheet_rows(
    cur,
    election: dict[str, Any],
) -> tuple[list[str], list[str], list[list[str]]]:
    election_id = str(election["id"])
    include_defaulters_in_quorum = bool(election.get("include_defaulters_in_quorum"))
    attendance_modes = normalize_attendance_modes(election.get("attendance_modes"))
    headers = attendance_sheet_headers(attendance_modes)
    mode_count = len(attendance_modes)

    cur.execute(
        """
        SELECT house_id, house_no
        FROM villas
        ORDER BY house_no
        """
    )
    villas = cur.fetchall()

    cur.execute(
        """
        SELECT p.grantor_house_id,
               p.proxy_holder_house_id,
               hv.house_no AS proxy_holder_house_no
        FROM proxies p
        JOIN villas hv ON hv.house_id = p.proxy_holder_house_id
        WHERE p.election_id = %s
          AND p.status = 'active'
        """,
        (election_id,),
    )
    proxies_by_grantor = {
        row["grantor_house_id"]: row
        for row in cur.fetchall()
    }

    cur.execute(
        """
        SELECT house_id
        FROM defaulters
        WHERE election_id = %s
          AND status = 'active'
        """,
        (election_id,),
    )
    defaulter_house_ids = {row["house_id"] for row in cur.fetchall()}

    cur.execute(
        """
        SELECT house_id,
               (array_agg(attendance_mode ORDER BY attended_at DESC))[1] AS attendance_mode
        FROM attendance_records
        WHERE election_id = %s
        GROUP BY house_id
        """,
        (election_id,),
    )
    attendance_mode_by_house = {
        row["house_id"]: row["attendance_mode"]
        for row in cur.fetchall()
    }

    data_rows: list[list[str]] = []
    for row_index, villa in enumerate(villas):
        house_id = villa["house_id"]
        proxy = proxies_by_grantor.get(house_id)
        if proxy:
            proxy_label = "Yes"
            proxy_villa = proxy["proxy_holder_house_no"]
            attended_mode, mode_defaulter = resolve_proxy_attendance(
                house_id,
                proxy,
                attendance_mode_by_house,
                defaulter_house_ids,
            )
        else:
            proxy_label = ""
            proxy_villa = ""
            attended_mode = attendance_mode_by_house.get(house_id)
            mode_defaulter = house_id in defaulter_house_ids
        defaulter_label = "Yes" if house_id in defaulter_house_ids else ""
        sheet_row_number = DATA_START_ROW + row_index
        row = [
            villa["house_no"],
            proxy_label,
            proxy_villa,
            defaulter_label,
        ]
        row.extend(
            mode_cell_value(
                attended_mode,
                mode,
                mode_defaulter,
                include_defaulters_in_quorum=include_defaulters_in_quorum,
            )
            for mode in attendance_modes
        )
        row.append(attended_row_formula(sheet_row_number, mode_count))
        row.append("")
        data_rows.append(row)

    summary_row = build_summary_row(
        len(data_rows),
        mode_count,
        include_defaulters_in_quorum=include_defaulters_in_quorum,
    )
    return headers, summary_row, data_rows
