"""Read explicit day tokens and exact newmoon/solstice phase hypotheses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fatebridge.validation.taiyi_epoch import (
    mean_origin_hypothesis,
    sexagenary_hypothesis,
)
from scripts.taiyi.taiyi_origin_sources import (
    CORPUS,
    FREEZE_SHA256,
    ROOT,
    read_origin_sources,
)


def audit(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    reading = read_origin_sources(corpus, root=root)
    from scripts.taiyi.audit_taiyi_day_epoch import audit as day_epoch_audit
    from scripts.taiyi.audit_taiyi_lunation_chain import audit as lunation_audit

    v28 = day_epoch_audit()
    v32 = lunation_audit(root=root)
    given = reading["given_accumulation"]
    ming_day = reading["day_tokens"]["ncl_ming"]["explicit_day_ganzhi"]
    old_calendar = v28["calendar_cohort"]
    selected = [
        row
        for row in old_calendar["records"]
        if row["month"] == 6 and row["day"] in (8, 9)
    ]
    axes = reading["predeclared_axes"]
    origin = reading["mean_origin"]
    old_reading = json.loads(
        (root / "tests/fixtures/taiyi_jinjing_v28/readings.json").read_text(
            encoding="utf-8"
        )
    )["jinjing"]
    anchor = old_reading["original_year_anchor"]
    annual_counter = (
        anchor["accumulation"] + old_reading["day_case"]["year"] - anchor["ce_year"]
    )
    fields = (
        "chapter_years",
        "chapter_months",
        "month_numerator",
        "day_denominator",
        "qi_denominator",
        "annual_residue_numerator",
    )
    phase_rows = [
        mean_origin_hypothesis(
            year_accumulation=annual_counter,
            month_year_shift=shift,
            solstice_year_shift=axes["solstice_year_shift"],
            whole_cycle_days_per_year=axes["whole_cycle_days_per_year"],
            **{key: origin[key] for key in fields},
        )
        for shift in axes["month_year_shifts"]
    ]
    cohorts = []
    for old_row in v32["full_lunation_cohort_hypotheses"]:
        candidate = old_row["june8_candidate_accumulation"]
        cohorts.append(
            {
                **old_row,
                "new_explicit_ming_day_constraint": [
                    {
                        "jiazi_origin": origin_id,
                        "candidate_day_ganzhi": sexagenary_hypothesis(
                            candidate, jiazi_origin=origin_id
                        ),
                        "matches_ming_explicit_day": sexagenary_hypothesis(
                            candidate, jiazi_origin=origin_id
                        )
                        == ming_day,
                    }
                    for origin_id in axes["jiazi_origins"]
                ],
            }
        )
    if len(cohorts) != 8 or len(old_calendar["records"]) != 355:
        raise ValueError("V33 must retain all8 cohorts and355 old calendar rows")
    return {
        "freeze_sha256": FREEZE_SHA256,
        "date_tokens_by_edition": reading["day_tokens"],
        "old_overbroad_statement_correction": reading["old_overbroad_statement"],
        "given_source_accumulation": given,
        "given_source_day_labels": [
            {
                "jiazi_origin": origin_id,
                "day_ganzhi": sexagenary_hypothesis(given, jiazi_origin=origin_id),
                "matches_ming_explicit_day": sexagenary_hypothesis(
                    given, jiazi_origin=origin_id
                )
                == ming_day,
                "matches_explicit_siku_day": None,
            }
            for origin_id in axes["jiazi_origins"]
        ],
        "printed_calendar_selected_days_from_frozen_v28_report": selected,
        "old_calendar_rows_retained": len(old_calendar["records"]),
        "old_calendar_report_is_new_independent_observation": False,
        "phase_hypotheses": phase_rows,
        "siku_phase": {
            "status": "unresolved",
            "annual_residue_numerator": origin["siku_solstice_numerator"],
            "scope": origin["siku_status"],
        },
        "all_eight_retained_serial_cohorts": cohorts,
        "scope": "New edition-specific day constraint on the same old Liang example. Fractional solstice/newmoon containment is conditional on an unadjudicated absolute lift; modulo60 alone cannot select a year. No production provider or source year reading installed.",
        "independent_new_ancient_cases": 0,
        "new_complete_dated_classical_cases_passed": 0,
        "old_source_expectations_or_reports_overwritten": False,
        "production_calendar_installed_or_changed": False,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_goal_complete": False,
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
