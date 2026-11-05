"""Keep source-year and serial-lunation hypotheses distinct from Jie month counts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_year import yearly_core
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.validation.taiyi_epoch import sexagenary_hypothesis
from scripts.taiyi.audit_taiyi_day_epoch import calendar_cohort

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v32"
FREEZE_SHA256 = "903bc7911f1d3c763f3b4d61f3518e542e954ffae53e97a098a25dad528f345d"


def _json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"V32 source object required: {path.name}")
    return data


def verify_sources(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    if (
        hashlib.sha256((corpus / "freeze.json").read_bytes()).hexdigest()
        != FREEZE_SHA256
    ):
        raise ValueError("V32 pinned source freeze changed")
    frozen = _json(corpus / "freeze.json")
    for base, key in ((corpus, "files"), (root, "prior_sources")):
        for name, digest in frozen[key].items():
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"V32 frozen source changed: {name}")
    return frozen


def serial_lunations(
    profile: dict[str, Any], annual: int, *, months: int = 16
) -> list[dict[str, int]]:
    """Literal initial conversion and next-month step, retaining every fraction.

    No leap-month assignment, epoch correction or civil-date conversion is made.
    Inconsistent constants remain inconsistent instead of borrowing another text.
    """
    constants = profile["initial_profile_from_v26"]
    numbers = [*constants.values(), annual, months, profile["step_integer"]]
    if any(type(v) is not int or v < 1 for v in numbers):
        raise ValueError("V32 positive integral source constants required")
    denominator = constants["day_denominator"]
    remainder = profile["step_remainder"]
    if type(remainder) is not int or not 0 <= remainder < denominator:
        raise ValueError("V32 step remainder must be within source denominator")
    initial_months = annual * constants["chapter_months"] // constants["chapter_years"]
    initial_day_units = initial_months * constants["month_numerator"]
    step_units = profile["step_integer"] * denominator + remainder
    result = []
    for offset in range(months):
        day, fraction = divmod(initial_day_units + offset * step_units, denominator)
        direct = (initial_months + offset) * constants["month_numerator"] // denominator
        following = (initial_day_units + (offset + 1) * step_units) // denominator
        result.append(
            {
                "offset": offset,
                "initial_mean_lunations": initial_months,
                "mean_lunations": initial_months + offset,
                "day_accumulation": day,
                "small_remainder": fraction,
                "day_denominator": denominator,
                "next_month_days": following - day,
                "direct_multiply_day_accumulation": direct,
                "direct_minus_serial": direct - day,
            }
        )
    return result


def audit(corpus: Path = CORPUS, *, root: Path = ROOT) -> dict[str, Any]:
    frozen = verify_sources(corpus, root=root)
    reading = _json(corpus / "readings.json")
    wujing = reading["wujing"]
    constants = wujing["day_constants"]
    profiles = reading["jinjing_serial_month_rules"]
    source_annual = wujing["annual_case"]
    annual = yearly_core(source_annual["ce_year"])
    residue = (annual["accumulation"] - 1) % 360
    annual_actual = {
        "annual_accumulation": annual["accumulation"],
        "yuan_index": residue // 72 + 1,
        "ju": residue % 72 + 1,
    }
    annual_checks = [
        {
            "field": key,
            "source": source_annual[key],
            "actual": value,
            "matches": source_annual[key] == value,
        }
        for key, value in annual_actual.items()
    ]
    monthly = []
    source_month = wujing["month_case"]
    for hypothesis in reading["predeclared_diagnostics"]["wujing_month_readings"]:
        for profile in ("jinjing_month_jie_360_v1", "key_month_tianzheng_jie_v1"):
            result = calculate_taiyi_analysis(
                analysis_year=hypothesis["cycle_year"],
                analysis_month=12,
                analysis_day=15,
                analysis_hour=12,
                analysis_timezone="+08:00",
                use_true_solar_time=False,
                calculation_mode="month",
                month_profile=profile,
            )
            if "taiyi" not in result:
                raise ValueError(
                    f"V32 engineering representative clock failed: {result}"
                )
            board = result["taiyi"]
            cycle = (board["core_board"]["accumulation"] - 1) % 360
            actual = {
                "ji_index": cycle // 60 + 1,
                "yuan_index": cycle // 72 + 1,
                "ju": cycle % 72 + 1,
            }
            observations = [
                {
                    "field": key,
                    "source": source_month[key],
                    "actual": value,
                    "matches": source_month[key] == value,
                }
                for key, value in actual.items()
            ]
            monthly.append(
                {
                    "year_reading": hypothesis,
                    "profile": profile,
                    "representative_civil_clock": board["calendar_rules"][
                        "civil_datetime"
                    ],
                    "counter": board["core_board"]["accumulation"],
                    "cycle360": cycle + 1,
                    "observations": observations,
                    "all_listed_fields_match": all(o["matches"] for o in observations),
                    "actual_year_and_unit_receipt": board["calendar_rules"][
                        "month_origin"
                    ],
                    "scope": "Representative Dec15 noon+08 clock, not a recovered historical day, time, place or source month boundary. Rival readings and both profiles stay; agreement cannot select an epoch.",
                }
            )
    prior = root / "tests/fixtures/taiyi_jinjing_v28"
    cohort = calendar_cohort(_json(prior / "liang-504-months.json"))
    if cohort["mismatches"]:
        raise ValueError("V32 prior printed-calendar reconstruction drifted")
    printed = _json(prior / "liang-504-months.json")["months"]
    reference_firsts = [r for r in cohort["records"] if r["day"] == 1]
    reference_firsts.append(
        {
            "day_ganzhi": sexagenary_hypothesis(
                printed[-1]["printed_cycle_base"] + 1, jiazi_origin=1
            )
        }
    )
    anchor = _json(prior / "readings.json")["jinjing"]["original_year_anchor"]
    series_comparisons = []
    for edition, profile in profiles.items():
        for year_shift in (0, -1):
            year_counter = anchor["accumulation"] + 504 - anchor["ce_year"] + year_shift
            series = serial_lunations(profile, year_counter)
            for extra in (0, 1):
                records = []
                for index, row in enumerate(printed):
                    candidate = series[index + 2 + extra]
                    expected_day = reference_firsts[index]["day_ganzhi"]
                    records.append(
                        {
                            "lunar_year": row["lunar_year"],
                            "month": row["month"],
                            "source_julian_month_start": row["julian_month_start"],
                            "printed_first_ganzhi": expected_day,
                            "printed_month_length": row["printed_month_length"],
                            "candidate": candidate,
                            "month_length_matches": (
                                None
                                if index == 12
                                else candidate["next_month_days"]
                                == row["printed_month_length"]
                            ),
                            "day_labels": [
                                {
                                    "jiazi_origin": origin,
                                    "ganzhi": sexagenary_hypothesis(
                                        candidate["day_accumulation"],
                                        jiazi_origin=origin,
                                    ),
                                    "matches": sexagenary_hypothesis(
                                        candidate["day_accumulation"],
                                        jiazi_origin=origin,
                                    )
                                    == expected_day,
                                }
                                for origin in (0, 1)
                            ],
                        }
                    )
                june8 = records[5]["candidate"]["day_accumulation"] + 7
                series_comparisons.append(
                    {
                        "edition": edition,
                        "year_shift": year_shift,
                        "extra_preceding_lunation": extra,
                        "year_accumulation": year_counter,
                        "required_month_first_anchors": 13,
                        "required_month_lengths": 12,
                        "records": records,
                        "matching_month_lengths": sum(
                            row["month_length_matches"] is True for row in records
                        ),
                        "matching_first_labels_by_origin": {
                            str(origin): sum(
                                row["day_labels"][origin]["matches"] for row in records
                            )
                            for origin in (0, 1)
                        },
                        "june8_candidate_accumulation": june8,
                        "june8_matches_original_accumulation": june8 == 707501061,
                        "all_listed_calendar_constraints_match": (
                            june8 == 707501061
                            and all(
                                r["month_length_matches"] is not False for r in records
                            )
                            and any(
                                all(r["day_labels"][origin]["matches"] for r in records)
                                for origin in (0, 1)
                            )
                        ),
                        "scope": "Literal serial mean-new-moon diagnostic only; fixed extra lunation is a hypothesis, not recovered intercalation. No civil date calculated from this absolute accumulation.",
                    }
                )
    return {
        "freeze_sha256": FREEZE_SHA256,
        "frozen_files": frozen["files"],
        "online_transcription_variant": {
            "initial_online": wujing["initial_online_transcription_chapter_years"],
            "native": wujing["native_chapter_years"],
            "old_file_overwritten": False,
        },
        "wujing_constants_against_two_jinjing_editions": [
            {
                "edition": edition,
                "observations": [
                    {
                        "field": key,
                        "wujing_source": value,
                        "jinjing_source": profile["initial_profile_from_v26"][key],
                        "matches": value == profile["initial_profile_from_v26"][key],
                    }
                    for key, value in constants.items()
                ],
            }
            for edition, profile in profiles.items()
        ],
        "given_annual_anchor_checks": annual_checks,
        "month_case_rival_readings": monthly,
        "fuying_month_formula": reading["fuying"],
        "full_lunation_cohort_hypotheses": series_comparisons,
        "prior_calendar_days_rechecked": cohort["days"],
        "year_label_reading_selected_by_match": False,
        "mean_lunation_counter_is_public_jie_counter": False,
        "production_numeric_formula_changed": False,
        "new_complete_dated_classical_cases_passed": 0,
        "whole_calendar_acceptance_passed": False,
        "whole_classic_acceptance_passed": False,
        "whole_goal_complete": False,
    }
