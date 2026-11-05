"""Couple elapsed days and numbered days without repairing an old source."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from fatebridge.validation.taiyi_epoch import (
    decode_day_counter,
    lunar_day_counter_views,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v34"
FREEZE_SHA256 = "c4f30775d179daef799cbbcd56724d54928a70fb3627b3b2a1c095460dd65189"


def _read(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"V34 object required: {path.name}")
    return data


def verify_sources(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    if (
        hashlib.sha256((corpus / "freeze.json").read_bytes()).hexdigest()
        != FREEZE_SHA256
    ):
        raise ValueError("V34 pinned source freeze changed")
    frozen = _read(corpus / "freeze.json")
    for base, key in ((corpus, "files"), (root, "prior_sources")):
        for name, digest in frozen[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"V34 source or prior evidence changed: {name}")
    return frozen


def _board(day_number: int, expected: dict[str, Any]) -> dict[str, Any]:
    if len(expected) != 10:
        raise ValueError("V34 requires all ten original board fields")
    core = cyclic_core(day_number)
    rows = [
        {
            "field": field,
            "source": value,
            "actual": core[field],
            "matches": core[field] == value,
        }
        for field, value in expected.items()
    ]
    return {
        "one_based_input_to_current_cyclic_core": day_number,
        "observations": rows,
        "matching_fields": sum(r["matches"] for r in rows),
        "all_ten_match": all(r["matches"] for r in rows),
        "scope": "Current numeric core applied to a normalized day number under the declared hypothesis; no source epoch proof.",
    }


def audit(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    frozen = verify_sources(corpus, root=root)
    source = _read(corpus / "readings.json")
    literature = _read(corpus / "literature-controls.json")
    axes = source["predeclared_axes"]
    encodings = axes["count_encodings"]
    epoch = axes["epoch_ganzhi_for_liang_hypothesis"]
    external = []
    for paper, rows in (
        ("lin2008", literature["lin2008"]["rows"]),
        ("gao2009", literature["gao2009"]["rows"]),
    ):
        for row in rows:
            start = row.get("epoch_ganzhi", literature[paper].get("epoch_ganzhi"))
            phase = row["phase_remainder"]
            pair = [
                decode_day_counter(
                    phase, encoding="completed_days", epoch_ganzhi=start
                ),
                decode_day_counter(
                    phase + 1, encoding="one_based_day_number", epoch_ganzhi=start
                ),
            ]
            external.append(
                {
                    "paper": paper,
                    "source": row,
                    "coupled_views": pair,
                    "both_match_published_label": all(
                        v["day_ganzhi"] == row["expected_ganzhi"] for v in pair
                    ),
                }
            )

    if __package__:
        from scripts.audit_taiyi_day_epoch import audit as day_epoch_audit
        from scripts.audit_taiyi_lunation_chain import audit as lunation_audit
    else:
        from audit_taiyi_day_epoch import audit as day_epoch_audit
        from audit_taiyi_lunation_chain import audit as lunation_audit

    old28 = day_epoch_audit()
    old32 = lunation_audit(root=root)
    printed = old28["calendar_cohort"]["records"]
    board_source = _read(root / "tests/fixtures/taiyi_jinjing_v31/readings.json")[
        "board"
    ]
    if len(printed) != 355 or len(old32["full_lunation_cohort_hypotheses"]) != 8:
        raise ValueError("V34 must retain all355 days and8 legacy cohorts")

    candidates = []
    calendar_series = []
    for cohort_index, cohort in enumerate(old32["full_lunation_cohort_hypotheses"]):
        june = next(r for r in cohort["records"] if r["month"] == 6)
        for initial_encoding in encodings:
            calendar_rows = []
            month_firsts = []
            for month in cohort["records"]:
                first = decode_day_counter(
                    month["candidate"]["day_accumulation"],
                    encoding=initial_encoding,
                    epoch_ganzhi=epoch,
                )
                month_firsts.append(
                    {
                        "month": month["month"],
                        "year": month["lunar_year"],
                        "reference_ganzhi": month["printed_first_ganzhi"],
                        "actual_ganzhi": first["day_ganzhi"],
                        "matches": first["day_ganzhi"] == month["printed_first_ganzhi"],
                    }
                )
            for row in printed:
                month = next(r for r in cohort["records"] if r["month"] == row["month"])
                normalized = lunar_day_counter_views(
                    month["candidate"]["day_accumulation"],
                    row["day"],
                    month_start_encoding=initial_encoding,
                    epoch_ganzhi=epoch,
                )
                exists = row["day"] <= month["candidate"]["next_month_days"]
                label_matches = normalized["day_ganzhi"] == row["day_ganzhi"]
                calendar_rows.append(
                    {
                        "month": row["month"],
                        "day": row["day"],
                        "gregorian_reference": row["gregorian"],
                        "reference_ganzhi": row["day_ganzhi"],
                        "completed_days": normalized["completed_days"],
                        "one_based_day_number": normalized["one_based_day_number"],
                        "actual_ganzhi": normalized["day_ganzhi"],
                        "representations_agree": normalized[
                            "both_views_preserve_same_day"
                        ],
                        "candidate_month_days": month["candidate"]["next_month_days"],
                        "ordinal_exists_in_hypothesis": exists,
                        "day_label_matches": label_matches,
                        "calendar_day_matches": exists and label_matches,
                    }
                )
            month_lengths = [
                r["month_length_matches"]
                for r in cohort["records"]
                if r["month_length_matches"] is not None
            ]
            all_days = all(r["calendar_day_matches"] for r in calendar_rows)
            typed_calendar = (
                all(month_lengths)
                and all(r["matches"] for r in month_firsts)
                and all_days
            )
            calendar_series.append(
                {
                    "cohort_index": cohort_index,
                    "initial_encoding": initial_encoding,
                    "required_days": 355,
                    "matching_day_labels": sum(
                        r["day_label_matches"] for r in calendar_rows
                    ),
                    "valid_matching_dates": sum(
                        r["calendar_day_matches"] for r in calendar_rows
                    ),
                    "all_days_match": all_days,
                    "month_firsts": month_firsts,
                    "all12_month_lengths_match": all(month_lengths),
                    "all_typed_calendar_observations_match": typed_calendar,
                    "legacy_joint_flag_is_not_reused_as_typed_gate": True,
                    "records": calendar_rows,
                }
            )
            for day in axes["selected_days"]:
                normalized = lunar_day_counter_views(
                    june["candidate"]["day_accumulation"],
                    day,
                    month_start_encoding=initial_encoding,
                    epoch_ganzhi=epoch,
                )
                board = _board(normalized["one_based_day_number"], board_source)
                views = []
                for encoding in encodings:
                    view = normalized["views"][encoding]
                    views.append(
                        {
                            "encoding": encoding,
                            "value": view["value"],
                            "day_ganzhi": view["day_ganzhi"],
                            "matches_quoted_original_integer": view["value"]
                            == source["given_original_accumulation"],
                            "source_encoding_adjudicated": False,
                        }
                    )
                # In-cycle22 is retained under the earlier same-quotient reading,
                # without pretending Xing supplied a corrected absolute count.
                residue = normalized["one_based_day_number"] % 60
                observations = {
                    "is_original_literal_day8": day == source["source_literal_day"],
                    "is_xing_corrected_day9": day == source["xing_corrected_day"],
                    "matches_ming_explicit_day": normalized["day_ganzhi"]
                    == source["given_ming_day_ganzhi"],
                    "matches_quoted_original_integer_under_an_encoding": any(
                        r["matches_quoted_original_integer"] for r in views
                    ),
                    "all_ten_board_fields_match": board["all_ten_match"],
                    "all_typed_calendar_observations_match": typed_calendar,
                    "matches_shoushi22_under_same_raw_remainder_assumption": residue
                    == source["xing_shoushi_in_cycle"],
                }
                xing_joint = all(
                    observations[k]
                    for k in (
                        "is_xing_corrected_day9",
                        "matches_ming_explicit_day",
                        "all_ten_board_fields_match",
                        "matches_shoushi22_under_same_raw_remainder_assumption",
                    )
                )
                for view in views:
                    view["all_original_observed_constraints_match"] = view[
                        "matches_quoted_original_integer"
                    ] and all(
                        observations[k]
                        for k in (
                            "is_original_literal_day8",
                            "matches_ming_explicit_day",
                            "all_ten_board_fields_match",
                            "all_typed_calendar_observations_match",
                        )
                    )
                    view["all_xing_observed_constraints_match"] = (
                        xing_joint and typed_calendar
                    )
                candidates.append(
                    {
                        "cohort_index": cohort_index,
                        "edition": cohort["edition"],
                        "year_shift": cohort["year_shift"],
                        "extra_preceding_lunation": cohort["extra_preceding_lunation"],
                        "initial_encoding": initial_encoding,
                        "lunar_day": day,
                        "normalized": normalized,
                        "counter_comparisons": views,
                        "board": board,
                        "observations": observations,
                        "one_based_in_cycle_remainder_under_old_assumption": residue,
                        "shoushi_remainder_semantics_adjudicated": False,
                        "source_corrected_absolute_accumulation_stated": False,
                        "matches_xing_corrected_absolute_accumulation": None,
                    }
                )

    given = []
    for encoding in encodings:
        normalized = decode_day_counter(
            source["given_original_accumulation"], encoding=encoding, epoch_ganzhi=epoch
        )
        given.append(
            {
                "encoding_hypothesis": encoding,
                "decoded": normalized,
                "matches_ming_explicit_day": normalized["day_ganzhi"]
                == source["given_ming_day_ganzhi"],
                "board": _board(normalized["one_based_day_number"], board_source),
            }
        )
    return {
        "freeze_sha256": FREEZE_SHA256,
        "prior_pinned_files": len(frozen["prior_sources"]),
        "external_phase_controls": external,
        "external_observation_count": len(external),
        "external_controls_are_taiyi_case_accuracy": False,
        "initial_counter_encoding_hypotheses": encodings,
        "all_eight_legacy_cohorts": old32["full_lunation_cohort_hypotheses"],
        "whole_calendar_encoding_series": calendar_series,
        "date_encoding_candidates": candidates,
        "given_source_integer_encoding_hypotheses": given,
        "original_observed_joint_matches": sum(
            v["all_original_observed_constraints_match"]
            for r in candidates
            for v in r["counter_comparisons"]
        ),
        "xing_observed_joint_matches": sum(
            v["all_xing_observed_constraints_match"]
            for r in candidates
            for v in r["counter_comparisons"]
        ),
        "source_epoch_identity_adjudicated": False,
        "source_counter_encoding_adjudicated": False,
        "fixed_day_correction_installed": False,
        "production_calendar_or_numeric_formula_changed": False,
        "new_independent_taiyi_cases": 0,
        "new_complete_dated_classical_cases_passed": 0,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_goal_complete": False,
        "scope": "Coupled representation diagnostics. Day9 matching a quoted old integer under one encoding is conditional; original day8, all ten board fields, Shoushi22, old calendar failures and unknown source epochs remain. No calendar or authorial meaning is chosen by fit.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = json.dumps(audit(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    else:
        print(raw)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
