"""Collate Xing Yunlu's Liang504 critique without selecting a new day epoch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.metaphysics.taiyi_year import (
    count_to_taiyi,
    cyclic_core,
    general_for_count,
    structural_patterns,
)
from fatebridge.validation.taiyi_epoch import (
    accumulation_hypothesis,
    sexagenary_hypothesis,
)

if TYPE_CHECKING or __package__:
    from scripts.audit_taiyi_day_epoch import calendar_cohort
    from scripts.taiyi_origin_sources import day_token_evidence
else:
    from audit_taiyi_day_epoch import calendar_cohort
    from taiyi_origin_sources import day_token_evidence

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v31"
FREEZE_SHA256 = "38686e4ecd951821d9a978eb96a58a8149b88b037c515dba9ea101527dbd7185"
BOARD_FIELDS = (
    "taiyi_number",
    "wenchang_palace",
    "main_count",
    "main_general",
    "main_vice_general",
    "shiji",
    "guest_count",
    "guest_general",
    "guest_vice_general",
    "jishen",
)


def _json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"V31 object required: {path.name}")
    return data


def verify_sources(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    if (
        hashlib.sha256((corpus / "freeze.json").read_bytes()).hexdigest()
        != FREEZE_SHA256
    ):
        raise ValueError("V31 pinned source freeze changed")
    freeze = _json(corpus / "freeze.json")
    for base, key in ((corpus, "files"), (root, "prior_sources")):
        for name, digest in freeze[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"V31 frozen source changed: {name}")
    return freeze


def compare_board(accumulation: int, expected: dict[str, Any]) -> dict[str, Any]:
    """Retain every printed field, including upstream positions when counts match."""
    if set(expected) != set(BOARD_FIELDS):
        raise ValueError("V31 requires all ten source fields")
    core = cyclic_core(accumulation)
    observations = [
        {
            "field": field,
            "source": expected[field],
            "actual": core[field],
            "matches": expected[field] == core[field],
        }
        for field in BOARD_FIELDS
    ]
    return {
        "accumulation": accumulation,
        "kook_number": core["kook_number"],
        "required_fields": len(BOARD_FIELDS),
        "matching_fields": sum(row["matches"] for row in observations),
        "observations": observations,
        "full_board_matches": all(row["matches"] for row in observations),
        "scope": "Given accumulation through current Jinjing cyclic rule; no date-to-accumulation validation.",
    }


def source_position_counts(expected: dict[str, Any]) -> dict[str, Any]:
    """Use the source's positions; never replace its count or printed generals."""
    traces = {}
    observations = []
    for marker, prefix in (("wenchang_palace", "main"), ("shiji", "guest")):
        trace = count_to_taiyi(expected[marker], expected["taiyi_number"])
        count = trace["count"]
        general = general_for_count(count)
        traces[prefix] = trace
        for suffix, actual in (
            ("count", count),
            ("general", general),
            ("vice_general", general * 3 % 10),
        ):
            field = f"{prefix}_{suffix}"
            observations.append(
                {
                    "field": field,
                    "source": expected[field],
                    "from_source_position": actual,
                    "matches": expected[field] == actual,
                }
            )
    return {
        "required_fields": 6,
        "matching_fields": sum(row["matches"] for row in observations),
        "observations": observations,
        "count_traces": traces,
        "scope": "Post-freeze diagnostic under current vol2 counting rule; not six independent source cases or a correction of Xing's text.",
    }


def audit(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    freeze = verify_sources(corpus, root=root)
    reading = _json(corpus / "readings.json")
    source = reading["case"]
    expected = reading["board"]
    prior = root / "tests/fixtures/taiyi_jinjing_v28"
    cohort = calendar_cohort(_json(prior / "liang-504-months.json"))
    selected = [
        r for r in cohort["records"] if r["month"] == 6 and r["day"] in (1, 8, 9)
    ]
    date_checks = [
        {
            **row,
            "xing_day_label": source[
                "month_first_ganzhi" if row["day"] == 1 else "corrected_day_ganzhi"
            ],
            "matches_xing_day_label": row["day_ganzhi"]
            == source[
                "month_first_ganzhi" if row["day"] == 1 else "corrected_day_ganzhi"
            ],
        }
        for row in selected
    ]
    original = source["original_accumulation"]
    # Keep the quotient fixed only for this named hypothesis. Xing prints no
    # full replacement absolute accumulation; his22 cannot certify original+1.
    plus1 = original + source["shoushi_in_cycle"] - source["original_in_cycle"]
    candidates = [
        {"id": "literal", "accumulation": original, "source_absolute": True},
        {
            "id": "plus1_same_quotient_hypothesis",
            "accumulation": plus1,
            "source_absolute": False,
        },
    ]
    anchor = _json(prior / "readings.json")["jinjing"]["original_year_anchor"]
    formula_hypotheses = []
    for year_shift in (0, -1):
        annual = anchor["accumulation"] + 504 - anchor["ce_year"] + year_shift
        for month_offset in (7, 8):
            hypothesis = accumulation_hypothesis(
                year_accumulation=annual,
                chapter_years=657,
                chapter_months=8126,
                month_numerator=1447,
                day_denominator=49,
                month_offset=month_offset,
                day_offset=7,
            )
            formula_hypotheses.append({**hypothesis, "year_shift": year_shift})
            candidates.append(
                {
                    "id": f"V27_year{year_shift}_month{month_offset}",
                    "accumulation": int(hypothesis["candidate_accumulation"]),
                    "source_absolute": False,
                }
            )
    comparisons = []
    for candidate in candidates:
        amount = candidate["accumulation"]
        comparisons.append(
            {
                **candidate,
                "division360": list(divmod(amount, 360)),
                "division60_of_remainder": list(divmod(amount % 360, 60)),
                "board": compare_board(amount, expected),
                "day_numbering_hypotheses": [
                    {
                        "jiazi_origin": origin,
                        "ganzhi": label,
                        "matches_printed_day8": label == selected[1]["day_ganzhi"],
                        "matches_printed_day9": label == selected[2]["day_ganzhi"],
                    }
                    for origin in (0, 1)
                    for label in [sexagenary_hypothesis(amount, jiazi_origin=origin)]
                ],
            }
        )
    residues = [
        {
            "source": field,
            "value": source[field],
            "jiazi_origin": origin,
            "hypothetical_ganzhi": sexagenary_hypothesis(
                source[field], jiazi_origin=origin
            ),
            "scope": "Assumes identical Jiazi epoch and counter meaning; not an adjudication of 算外 or Xing's calendar.",
        }
        for field in ("original_in_cycle", "shoushi_in_cycle")
        for origin in (0, 1)
    ]
    patterns = structural_patterns(cyclic_core(original))
    return {
        "freeze_sha256": FREEZE_SHA256,
        "frozen_files": freeze["files"],
        "primary_editions": 2,
        "independent_new_ancient_cases": 0,
        "calendar_cohort": cohort,
        "xing_date_claims_against_printed_calendar": date_checks,
        "jinjing_date_token_evidence": day_token_evidence(),
        "original_jinjing_day8_overwritten": False,
        "source_full_corrected_accumulation_stated": False,
        "all_four_retained_formula_hypotheses": formula_hypotheses,
        "all_six_candidate_comparisons": comparisons,
        "in_cycle_numbering_hypotheses": residues,
        "source_position_recalculation": source_position_counts(expected),
        "post_freeze_spatial_diagnostic": {
            "source_words": reading["transcription"]["eye_relationship"],
            "actual_wenchang_pressure": [
                r for r in patterns if r["name"] == "迫" and r["subject"] == "文昌"
            ],
            "all_actual_patterns": patterns,
            "scope": "Reported geometry only. Not scored into the ten board fields; no evaluation of source event claims or real-world efficacy.",
        },
        "source_attribution_difference": reading["attribution_difference"],
        "source_calendar_identity": "not_adjudicated_Wang_Sifen_vs_Xing_Shoushi_vs_printed_Liang",
        "counter_representation_scope": {
            "legacy_raw_difference_is_adjudicated_calendar_error": False,
            "source_integer_encoding_and_epoch_adjudicated": False,
            "meaning": "Original day8, corrected day9, quoted old accumulation and Shoushi in-cycle22 remain different claims; a coupled encoding match cannot replace their joint validation.",
            "guide": "docs/taiyi-day-count-encodings.md",
        },
        "production_calendar_installed_or_changed": False,
        "new_complete_dated_classical_cases_passed": 0,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_goal_complete": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    raw = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw)
    else:
        print(raw)
    # Partial agreement cannot turn the unresolved classical audit green.
    raise SystemExit(1)


if __name__ == "__main__":
    main()
