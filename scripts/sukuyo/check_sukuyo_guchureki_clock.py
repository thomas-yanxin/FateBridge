"""Check selected published clock readings without forcing symmetry or dates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT / "src"))

from fatebridge.core.sukuyo_guchureki_clock import (
    MODEL,
    SOURCE,
    clock_arithmetic_reference,
    decode_clock,
)
from fatebridge.core.sukuyo_sources import load_source

BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
POINT = re.compile(
    "[" + BRANCHES + r"](?:時正|初(?:[0-9]+分(?:半)?)?|[0-9]+刻(?:[0-9]+分(?:半)?)?)"
)


def _groups(raw: str) -> list[dict[str, Any]]:
    """Read the fixed Table 3 text, retaining both multiline alternatives."""
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending: dict[str, Any] | None = None

    def reading(text: str) -> dict[str, Any]:
        matches = list(POINT.finditer(text))
        if len(matches) != 2:
            raise ValueError("Table 3 reading does not contain two clock points")
        return {
            "sunrise": matches[0][0],
            "sunset": matches[1][0],
            "printed_sum": text[matches[1].end() :] or None,
        }

    for line in raw.splitlines()[1:]:
        text = "".join(line.split())
        if not text:
            continue
        if text.isdigit():
            if current is None:
                raise ValueError("Table 3 interval without a group")
            current["printed_interval_to_next"] = int(text)
            current = None
        elif match := re.match(r"(.+?日)([0-9]+)", text):
            current = {
                "id": f"table3_{len(groups)+1:02d}",
                "season_label": match[1],
                "nominal_seasonal_ordinal": int(match[2]),
                "readings": [],
            }
            groups.append(current)
            if pending:
                current["readings"].append(pending)
                pending = None
            if rest := text[match.end() :]:
                current["readings"].append(reading(rest))
        elif current is not None:
            current["readings"].append(reading(text))
        else:
            if pending is not None:
                raise ValueError("Multiple unattached Table 3 alternatives")
            pending = reading(text)
    if current is not None or pending is not None:
        raise ValueError("Unfinished Table 3 group")
    return groups


def _twice_fun(literal: str) -> int:
    """Independent integer half-fun arithmetic from the selected printed units."""
    text = "".join(literal.split())
    if text and text[0] in BRANCHES:
        text = text[1:]
    if text == "時正":
        return 25
    if text.startswith("初"):
        text = "0刻" + text[1:]
    match = re.fullmatch(r"([0-9]+)刻(?:([0-9]+)分(半)?)?", text)
    if not match:
        raise ValueError("Unsupported selected Table 3 literal")
    return 12 * int(match[1]) + 2 * int(match[2] or 0) + bool(match[3])


def verify_guchureki_clock(
    pdf_path: Path | None = None, table_capture: Path | None = None
) -> dict[str, Any]:
    source = load_source(SOURCE)
    bundle = source.data
    fixture = ROOT / "tests/data/sukuyo-guchureki-table3.txt"
    raw = fixture.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    errors: list[Any] = []
    if digest != bundle["table_capture"]["extracted_text_sha256"]:
        errors.append("selected_table_fixture_bytes_changed")
    groups = _groups(raw.decode())
    if groups != bundle["record_groups"]:
        errors.append("selected_published_groups_changed")
    checked = 0
    for group in groups:
        for row in group["readings"]:
            for name in ["sunrise", "sunset"]:
                actual = decode_clock(row[name], model=MODEL)
                ratio = actual["within_branch_fun"]
                if (
                    2 * ratio["numerator"]
                    != _twice_fun(row[name]) * ratio["denominator"]
                ):
                    errors.append(["clock_arithmetic", group["id"], name])
            if row["printed_sum"] is not None and _twice_fun(
                row["sunrise"]
            ) + _twice_fun(row["sunset"]) != _twice_fun(row["printed_sum"]):
                errors.append(["published_sum", group["id"]])
            checked += 1
    reference = clock_arithmetic_reference(include_all_rows=True)
    summary = reference["table_check"]
    errors.extend(summary["table_printed_sums_and_nominal_intervals_errors"])
    if len(groups) != 40 or checked != 42:
        errors.append("incomplete_selected_table")
    if summary["residual_counts_by_exact_fun"] != {"0": 34, "1": 4, "-1/2": 2, "-1": 2}:
        errors.append("source_residuals_changed_or_removed")
    if (
        pdf_path
        and hashlib.sha256(pdf_path.read_bytes()).hexdigest() != bundle["source_sha256"]
    ):
        raise ValueError("Selected publisher PDF bytes changed")
    if table_capture and table_capture.read_bytes() != raw:
        raise ValueError("Selected table capture bytes changed")
    return {
        "format": "sukuyo_guchureki_clock_check_v1",
        "source_bundle_sha256": source.sha256,
        "publisher_pdf_sha256": bundle["source_sha256"],
        "fixture_sha256": digest,
        "record_groups_checked": len(groups),
        "paired_readings_checked": checked,
        "residual_counts_by_exact_fun": summary["residual_counts_by_exact_fun"],
        "nonzero_residual_groups_retained": summary["nonzero_residual_groups_retained"],
        "nonzero_residual_readings_retained": summary[
            "nonzero_residual_readings_retained"
        ],
        "publisher_pdf_identity_checked": pdf_path is not None,
        "external_table_capture_bytes_checked": table_capture is not None,
        "PDF_text_extraction_reexecuted_by_this_checker": False,
        "fixture_is_derived_from_same_study": True,
        "independent_manuscript_or_human_collation": False,
        "physical_solar_comparison_reproduced": False,
        "civil_clock_or_hinoo_precedence_admitted": False,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-path", type=Path)
    parser.add_argument("--table-capture", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_guchureki_clock(args.pdf_path, args.table_capture)
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
