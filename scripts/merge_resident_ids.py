#!/usr/bin/env python3
import csv
import re
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path


MASTER_CSV = Path("/Users/gaurav.gupta/Downloads/resident_details.csv")
LOOKUP_CSV = Path("/Users/gaurav.gupta/Downloads/resident_list_file_1779523827.csv_d25d15152f75926a7a9964d7cc30b19f.csv")
OUTPUT_CSV = Path("/Users/gaurav.gupta/Code/Attendance/resident_details_with_ids.csv")
ACTIVE_ONLY_OUTPUT_CSV = Path("/Users/gaurav.gupta/Code/Attendance/resident_details_with_ids_active_only.csv")
SUMMARY_CSV = Path("/Users/gaurav.gupta/Code/Attendance/resident_details_with_ids_match_summary.csv")

USER_ID_COLUMN = "User Id (Do Not Edit)"
HOUSE_ID_COLUMN = "House Id (Do Not Edit)"


def clean_spaces(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_name(value):
    text = clean_spaces(value).casefold()
    text = re.sub(r"[^a-z0-9& ]+", " ", text)
    text = re.sub(r"\b(mr|mrs|ms|miss|dr|prof)\b\.?", " ", text)
    text = text.replace("&", " and ")
    return clean_spaces(text)


def normalize_flat(value):
    text = clean_spaces(value).casefold()
    text = text.replace("extension", "extn")
    text = re.sub(r"\bphase([0-9])\b", r"phase \1", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return clean_spaces(text)


def flat_similarity(left, right):
    return SequenceMatcher(None, normalize_flat(left), normalize_flat(right)).ratio()


def parse_approved_on(row):
    value = clean_spaces(row.get("Approved On"))
    for pattern in ("%d-%b-%Y %I:%M %p", "%d-%b-%Y %I:%M%p", "%d-%m-%Y"):
        try:
            return datetime.strptime(value.upper(), pattern)
        except ValueError:
            continue
    return datetime.max


def numeric_user_id(row):
    value = clean_spaces(row.get(USER_ID_COLUMN))
    return int(value) if value.isdigit() else 10**18


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def build_lookup(rows):
    by_exact_key = defaultdict(list)
    by_name = defaultdict(list)

    for row in rows:
        key = (normalize_flat(row.get("House No")), normalize_name(row.get("Resident Name")))
        by_exact_key[key].append(row)
        by_name[key[1]].append(row)

    return by_exact_key, by_name


def select_match(master_row, by_exact_key, by_name):
    flat = master_row.get("Flat")
    name = master_row.get("Name")
    exact_key = (normalize_flat(flat), normalize_name(name))
    exact_matches = by_exact_key.get(exact_key, [])

    if len(exact_matches) == 1:
        return exact_matches[0], "exact_normalized", 1.0

    if len(exact_matches) > 1:
        return None, "ambiguous_exact_normalized", 1.0

    name_matches = by_name.get(exact_key[1], [])
    if not name_matches:
        return None, "no_name_match", 0.0

    scored = sorted(
        ((flat_similarity(flat, candidate.get("House No")), candidate) for candidate in name_matches),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score = scored[0][0]
    best_matches = [candidate for score, candidate in scored if abs(score - best_score) < 0.00001]

    if best_score >= 0.82 and len(best_matches) == 1:
        return best_matches[0], "fuzzy_flat_same_name", best_score

    if best_score >= 0.82:
        return None, "ambiguous_fuzzy_flat_same_name", best_score

    return None, "low_confidence_flat_match", best_score


def main():
    master_headers, master_rows = read_csv(MASTER_CSV)
    _, lookup_rows = read_csv(LOOKUP_CSV)
    by_exact_key, by_name = build_lookup(lookup_rows)

    output_headers = [header for header in master_headers if header not in {USER_ID_COLUMN, HOUSE_ID_COLUMN}]
    output_headers.extend([USER_ID_COLUMN, HOUSE_ID_COLUMN])

    output_rows = []
    match_infos = []
    ambiguous_groups = defaultdict(list)

    for row_index, master_row in enumerate(master_rows):
        match, status, score = select_match(master_row, by_exact_key, by_name)
        output_row = {header: master_row.get(header, "") for header in output_headers}

        if match:
            output_row[USER_ID_COLUMN] = match.get(USER_ID_COLUMN, "")
            output_row[HOUSE_ID_COLUMN] = match.get(HOUSE_ID_COLUMN, "")
        else:
            output_row[USER_ID_COLUMN] = ""
            output_row[HOUSE_ID_COLUMN] = ""

        output_rows.append(output_row)
        match_info = {
            "Flat": master_row.get("Flat", ""),
            "Name": master_row.get("Name", ""),
            "Match Status": status,
            "Match Score": f"{score:.3f}",
            "Matched House No": match.get("House No", "") if match else "",
            "Matched Resident Name": match.get("Resident Name", "") if match else "",
            USER_ID_COLUMN: match.get(USER_ID_COLUMN, "") if match else "",
            HOUSE_ID_COLUMN: match.get(HOUSE_ID_COLUMN, "") if match else "",
        }
        match_infos.append(match_info)

        if status == "ambiguous_exact_normalized":
            key = (normalize_flat(master_row.get("Flat")), normalize_name(master_row.get("Name")))
            ambiguous_groups[key].append((row_index, master_row))

    for key, indexed_master_rows in ambiguous_groups.items():
        candidates = sorted(by_exact_key[key], key=numeric_user_id)
        sorted_master_rows = sorted(indexed_master_rows, key=lambda item: (parse_approved_on(item[1]), item[0]))
        if len(candidates) != len(sorted_master_rows):
            continue

        for candidate, (row_index, _) in zip(candidates, sorted_master_rows):
            output_rows[row_index][USER_ID_COLUMN] = candidate.get(USER_ID_COLUMN, "")
            output_rows[row_index][HOUSE_ID_COLUMN] = candidate.get(HOUSE_ID_COLUMN, "")
            match_infos[row_index].update({
                "Match Status": "resolved_by_approved_on_sequence",
                "Matched House No": candidate.get("House No", ""),
                "Matched Resident Name": candidate.get("Resident Name", ""),
                USER_ID_COLUMN: candidate.get(USER_ID_COLUMN, ""),
                HOUSE_ID_COLUMN: candidate.get(HOUSE_ID_COLUMN, ""),
            })

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_headers)
        writer.writeheader()
        writer.writerows(output_rows)

    active_rows = [
        row for row in output_rows
        if clean_spaces(row.get("Status")).casefold() != "inactive"
    ]
    with ACTIVE_ONLY_OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_headers)
        writer.writeheader()
        writer.writerows(active_rows)

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "Flat",
            "Name",
            "Match Status",
            "Match Score",
            "Matched House No",
            "Matched Resident Name",
            USER_ID_COLUMN,
            HOUSE_ID_COLUMN,
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(match_infos)

    matched = sum(1 for row in output_rows if row[USER_ID_COLUMN] and row[HOUSE_ID_COLUMN])
    status_counts = defaultdict(int)
    for row in match_infos:
        status_counts[row["Match Status"]] += 1

    print(f"master_rows={len(master_rows)}")
    print(f"lookup_rows={len(lookup_rows)}")
    print(f"matched_rows={matched}")
    print(f"unmatched_or_ambiguous_rows={len(master_rows) - matched}")
    print(f"active_rows={len(active_rows)}")
    print(f"active_blank_id_rows={sum(1 for row in active_rows if not row[USER_ID_COLUMN] and not row[HOUSE_ID_COLUMN])}")
    for status in sorted(status_counts):
        print(f"{status}={status_counts[status]}")
    print(f"output_csv={OUTPUT_CSV}")
    print(f"active_only_output_csv={ACTIVE_ONLY_OUTPUT_CSV}")
    print(f"summary_csv={SUMMARY_CSV}")


if __name__ == "__main__":
    main()
