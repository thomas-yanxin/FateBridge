"""Compare independently frozen readings, preserving disagreements and errata.

This checks the records and their joins. It is not a machine certification that
every glyph was read correctly or that a printed rule predicts real events.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/data/ziwei_independent"


def audit_independent_readings(fixtures: Path = FIXTURES) -> dict[str, Any]:
    folder = fixtures / "independent_readings_r22_v1"
    manifest = json.loads((folder / "manifest.json").read_text())
    for row in manifest["files"]:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe independent reading path")
        if (
            hashlib.sha256((folder / relative).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("Independent reading checksum mismatch: " + row["path"])
    raw = json.loads((folder / "reports/day-review.json").read_text())
    errata = json.loads((folder / "reports/day-review-errata-01.json").read_text())
    clock = json.loads((folder / "reports/source-review.json").read_text())
    if (
        errata["frozen_original"]["sha256"]
        != hashlib.sha256((folder / "reports/day-review.json").read_bytes()).hexdigest()
    ):
        raise ValueError("Erratum does not identify the retained first reading")

    expected_keys = {(bureau, day) for bureau in range(2, 7) for day in range(1, 31)}
    first = {(r["bureau"], r["day"]): r for r in raw["day_to_branch_rows"]}
    if len(raw["day_to_branch_rows"]) != 150 or set(first) != expected_keys:
        raise ValueError("Independent day-reading denominator changed")
    corrected = deepcopy(first)
    correction = errata["corrected_day_to_branch_row"]
    key = (correction["bureau"], correction["day"])
    corrected[key] = correction
    selected_source = json.loads(
        (ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-days.json").read_text()
    )
    selected = {(r["bureau"], r["day"]): r for r in selected_source["records"]}
    if set(selected) != expected_keys:
        raise ValueError("Selected transcription denominator changed")

    agreed = []
    differences = []
    unconfirmed = []
    conflicts = []
    unknown = []
    rival_candidates = []
    for key in sorted(expected_keys):
        review = corrected[key]
        branches = review["branches_from_direct_labels"]
        old = selected[key]
        identity = dict(bureau=key[0], day=key[1])
        if len(branches) == 1:
            if old["branch"] is not None and old["branch"] != branches[0]:
                differences.append(
                    dict(**identity, selected=old["branch"], independent=branches[0])
                )
            elif old["source_kind"] == "direct_grid_cell":
                agreed.append(identity)
        elif branches:
            conflicts.append(dict(**identity, branches=branches))
        else:
            unknown.append(identity)
            if old["branch"] is not None:
                unconfirmed.append(
                    dict(
                        **identity,
                        selected_branch=old["branch"],
                        selected_evidence_kind=old["source_kind"],
                        review_status=review["status"],
                    )
                )
        if candidates := review.get("candidate_branches_from_unresolved_labels"):
            rival_candidates.append(dict(**identity, candidates=candidates))

    frames = {(r["item_id"], r["image_number_one_based"]) for r in clock["read_images"]}
    coverage = clock["coverage"]
    if len(frames) != coverage["unique_whole_frames_visually_read"]:
        raise ValueError("Reported image coverage does not match the frozen image list")
    if coverage["exhaustive_whole_book_reading"]:
        raise ValueError("The selected review must not become a whole-book claim")
    findings = {r["id"]: r for r in clock["findings"]}
    return dict(
        method_id="ziwei_independent_source_readings_r22_v1",
        frozen_files_verified=len(manifest["files"]),
        requested_day_inputs=150,
        original_report_single_direct_inputs=raw["coverage"][
            "inputs_with_single_directly_readable_branch"
        ],
        original_overstatement_withdrawn=errata["withdrawn_claim"],
        corrected_single_direct_inputs=sum(
            len(r["branches_from_direct_labels"]) == 1 for r in corrected.values()
        ),
        directly_read_positions_agreeing_with_selected_transcription=agreed,
        direct_position_differences=differences,
        selected_expectations_not_directly_confirmed=unconfirmed,
        conflicting_direct_inputs=conflicts,
        inputs_without_directly_readable_label=unknown,
        inputs_with_unresolved_rival_labels=rival_candidates,
        clock_review_reported_distinct_full_frames=len(frames),
        clock_review_reported_acquisition_attempts=coverage[
            "download_or_reuse_attempt_count"
        ],
        clock_review_reported_failed_attempts=coverage["failed_attempt_count"],
        source_clock_passage=findings["F2"],
        modern_clock_mapping_established=False,
        lunar_year_age_boundary_established=False,
        whole_book_acceptance_passed=False,
        independent_external_experts=0,
        new_source_editions=0,
        new_independent_calendar_observations=0,
        all_150_day_inputs_uniquely_confirmed=False,
        scope="Record integrity and same-witness reading comparison only. All 150 inputs remain in the denominator; unknowns and the failed first reading are retained. No calculation rule or glyph is repaired using the production algorithm.",
    )
