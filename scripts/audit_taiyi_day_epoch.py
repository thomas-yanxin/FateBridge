"""Printed Liang504 calendar versus Jinjing day accumulation, keeping failures."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fatebridge.core.almanac import get_day_ganzhi
from fatebridge.core.metaphysics.taiyi_day import key_day_numeric_board
from fatebridge.core.metaphysics.taiyi_historical import julian_to_proleptic_gregorian
from fatebridge.core.metaphysics.taiyi_year import cyclic_core
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.validation.taiyi_epoch import (
    accumulation_hypothesis,
    sexagenary_hypothesis,
)

if TYPE_CHECKING or __package__:
    from scripts.taiyi_origin_sources import day_token_evidence
else:
    from taiyi_origin_sources import day_token_evidence

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v28"
FREEZE_SHA256 = "b269106b408d86efe8567d896a5860740f420d40ca5dcb1ab90c854905f67fce"
ERRATA_SHA256 = "fbe4c00d13edf3f7e22d990e830a74ebd5ec9b7348a2c47a1f32ae58e74e685f"
ADDITIONAL_SHA256 = "7c3e60b3d84bf1d58ad1d9cf4f42af3674d4be4dfcffa4593bd156751e8b2929"
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
# Deductive controls from the two explicit Key clauses, not historical examples.
KEY_JISHEN = {False: "寅丑子亥戌酉申未午巳辰卯", True: "申未午巳辰卯寅丑子亥戌酉"}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Source must be an object: {path.name}")
    return value


def verify_sources(corpus: Path = CORPUS) -> dict[str, Any]:
    for name, digest in [
        ("freeze.json", FREEZE_SHA256),
        ("derived-label-errata.json", ERRATA_SHA256),
        ("additional-source-freeze.json", ADDITIONAL_SHA256),
    ]:
        if hashlib.sha256((corpus / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"V28 original source/errata freeze changed: {name}")
    freeze = _json(corpus / "freeze.json")
    for name, digest in freeze["files"].items():
        if hashlib.sha256((corpus / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"V28 frozen source changed: {name}")
    for name, digest in freeze["prior_sources"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"V28 prior source changed: {name}")
    additional = _json(corpus / "additional-source-freeze.json")
    for name, digest in additional["files"].items():
        if hashlib.sha256((corpus / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"V28 additional source changed: {name}")
    return freeze


def julian_jdn(label: str) -> int:
    """Independent Julian integer arithmetic; no production calendar call."""
    y, m, d = map(int, label.split("-"))
    a = (14 - m) // 12
    y += 4800 - a
    m += 12 * a - 3
    return d + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083


def gregorian_from_jdn(jdn: int) -> date:
    return date.fromordinal(jdn - 1721425)


def calendar_cohort(data: dict[str, Any]) -> dict[str, Any]:
    months = data["months"]
    if len(months) != 13 or [r["month"] for r in months] != [*range(1, 13), 1]:
        raise ValueError("V28 requires the complete12 months and next-year sentinel")
    mismatch = []
    records = []
    for row, following in zip(months, months[1:]):
        start = julian_jdn(row["julian_month_start"])
        length = julian_jdn(following["julian_month_start"]) - start
        if length != row["printed_month_length"] or length not in (29, 30):
            raise ValueError("V28 printed month length disagrees with month-first rows")
        for day in range(1, length + 1):
            western = gregorian_from_jdn(start + day - 1)
            idx = (row["printed_cycle_base"] + day - 1) % 60
            expected = STEMS[idx % 10] + BRANCHES[idx % 12]
            weekday = (row["printed_week_base"] + day) % 7
            actual = get_day_ganzhi(western.year, western.month, western.day)
            if actual != expected or western.isoweekday() % 7 != weekday:
                mismatch.append(
                    {
                        "date": western.isoformat(),
                        "expected": expected,
                        "actual": actual,
                        "printed_weekday": weekday,
                    }
                )
            records.append(
                {
                    "month": row["month"],
                    "day": day,
                    "gregorian": western.isoformat(),
                    "day_ganzhi": expected,
                    "weekday_sunday_zero": weekday,
                }
            )
    return {
        "month_first_anchors": 13,
        "complete_months": 12,
        "days": len(records),
        "mismatches": mismatch,
        "records": records,
        "scope": "Printed Liang504 reconstruction and day-label checks; not Wang calendar identity or a public lunar provider.",
    }


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    freeze = verify_sources(corpus)
    date_tokens = day_token_evidence()
    data = _json(corpus / "liang-504-months.json")
    readings = _json(corpus / "readings.json")
    location_errata = _json(corpus / "summary-location-errata.json")
    if (
        location_errata["path"] != "key.summary_page"
        or location_errata["original"] != readings["key"]["summary_page"]
        or location_errata["corrected"] != 43
    ):
        raise ValueError("V28 summary location correction lost its original")
    original_case = readings["independent_calendar_case"]
    case = copy.deepcopy(original_case)
    errata = _json(corpus / "derived-label-errata.json")
    # Preserve the wrong initial derived label3 and its pre-comparison correction.
    for change in errata["changes"]:
        if change["path"] != "independent_calendar_case.weekday_sunday_zero":
            raise ValueError("V28 unregistered derived-label correction")
        if case["weekday_sunday_zero"] != change["original"]:
            raise ValueError("V28 correction lost original derived label")
        case["weekday_sunday_zero"] = change["corrected"]
    cohort = calendar_cohort(data)
    selected = next(r for r in cohort["records"] if r["month"] == 6 and r["day"] == 8)
    western = date.fromisoformat(selected["gregorian"])
    julian = case["julian_date"]
    selected_checks = {
        "declared_gregorian": selected["gregorian"] == case["proleptic_gregorian_date"],
        "declared_ganzhi": selected["day_ganzhi"] == case["day_ganzhi"],
        "corrected_weekday": selected["weekday_sunday_zero"]
        == case["weekday_sunday_zero"],
        "integer_julian_conversion": gregorian_from_jdn(julian_jdn(julian)) == western,
        "production_julian_conversion": julian_to_proleptic_gregorian(
            *map(int, julian.split("-"))
        )
        == western,
    }
    source = readings["jinjing"]["day_case"]
    accumulation = source["original_day_accumulation"]
    core = cyclic_core(accumulation)
    supplied = {
        "original_accumulation": accumulation,
        "division360": list(divmod(accumulation, 360)),
        "division60_of_remainder": list(divmod(accumulation % 360, 60)),
        "taiyi_number": core["taiyi_number"],
        "wenchang_palace": core["wenchang_palace"],
        "scope": "Supplied original accumulation; date-to-accumulation bridge not tested by this replay.",
    }
    hypotheses: list[dict[str, Any]] = []
    anchor = readings["jinjing"]["original_year_anchor"]
    for year_shift in (0, -1):
        annual = anchor["accumulation"] + 504 - anchor["ce_year"] + year_shift
        for month_offset in (7, 8):
            row = accumulation_hypothesis(
                year_accumulation=annual,
                chapter_years=657,
                chapter_months=8126,
                month_numerator=1447,
                day_denominator=49,
                month_offset=month_offset,
                day_offset=7,
            )
            candidate = int(row["candidate_accumulation"])
            row.update(
                year_offset_hypothesis=year_shift,
                minus_original_accumulation=candidate - accumulation,
            )
            hypotheses.append(
                {
                    **row,
                    "sexagenary_conventions": [
                        {
                            "jiazi_origin": origin,
                            "ganzhi": sexagenary_hypothesis(
                                candidate, jiazi_origin=origin
                            ),
                            "matches_printed_Liang_day": sexagenary_hypothesis(
                                candidate, jiazi_origin=origin
                            )
                            == selected["day_ganzhi"],
                        }
                        for origin in (0, 1)
                    ],
                }
            )
    jishen_controls = []
    for yin, sequence in KEY_JISHEN.items():
        for i, expected in enumerate(sequence):
            board = key_day_numeric_board(i + 1, BRANCHES[i], yin)
            jishen_controls.append(
                {
                    "yin": yin,
                    "day_branch": BRANCHES[i],
                    "expected": expected,
                    "actual": board["core_board"]["jishen"],
                    "matches": board["core_board"]["jishen"] == expected,
                }
            )
    public = calculate_taiyi_analysis(
        analysis_year=western.year,
        analysis_month=western.month,
        analysis_day=western.day,
        analysis_hour=12,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
        calculation_mode="day",
    )
    if "taiyi" not in public:
        raise ValueError(f"V28 public current-profile replay failed: {public}")
    board = public["taiyi"]
    return {
        "freeze_sha256": FREEZE_SHA256,
        "errata_sha256": ERRATA_SHA256,
        "additional_source_freeze_sha256": ADDITIONAL_SHA256,
        "key_summary_location_correction": location_errata,
        "frozen_files": freeze["files"],
        "calendar_cohort": cohort,
        "initial_derived_weekday": original_case["weekday_sunday_zero"],
        "corrected_derived_weekday": case["weekday_sunday_zero"],
        "source_glyphs_changed_by_correction": False,
        "selected_calendar_case": selected,
        "selected_calendar_checks": selected_checks,
        "given_accumulation_replay": supplied,
        "original_accumulation_day_labels": [
            {
                "jiazi_origin": origin,
                "ganzhi": sexagenary_hypothesis(accumulation, jiazi_origin=origin),
                "matches_printed_Liang_day": sexagenary_hypothesis(
                    accumulation, jiazi_origin=origin
                )
                == selected["day_ganzhi"],
                "matches_ncl_ming_explicit_day": sexagenary_hypothesis(
                    accumulation, jiazi_origin=origin
                )
                == date_tokens["by_edition"]["ncl_ming"]["explicit_day_ganzhi"],
            }
            for origin in (0, 1)
        ],
        "jinjing_date_token_evidence": date_tokens,
        "all_four_V27_hypotheses": hypotheses,
        "hypotheses_matching_original_accumulation": sum(
            r["minus_original_accumulation"] == 0 for r in hypotheses
        ),
        "hypothesis_convention_pairs_matching_Liang_day": sum(
            c["matches_printed_Liang_day"]
            for r in hypotheses
            for c in r["sexagenary_conventions"]
        ),
        "source_calendar_identity": "not_adjudicated_Wang_same_epoch_Sifen_vs_printed_Liang_calendar",
        "counter_representation_scope": {
            "legacy_raw_difference_is_adjudicated_calendar_error": False,
            "source_integer_encoding_and_epoch_adjudicated": False,
            "meaning": "Old raw differences retain their supplied offsets. Completed days and a day number must be normalized together with the day label before identifying a calendar error.",
            "guide": "https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-day-count-encodings.md",
        },
        "key_jishen_deductive_controls": jishen_controls,
        "key_jishen_historical_yin_examples": 0,
        "public_current_day_profile": {
            "calendar_rules": board["calendar_rules"],
            "core_board": board["core_board"],
            "counter_comparison_to_Jinjing_applicable": False,
            "scope": "Representative12:00 fixed+08 input for engineering; Key modern adapter, not a recovered Jinjing source time or Sifen accumulation.",
        },
        "production_calendar_installed_or_changed": False,
        "new_complete_dated_classical_cases_passed": 0,
        "whole_calendar_acceptance_passed": False,
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
    raise SystemExit(1)


if __name__ == "__main__":
    main()
