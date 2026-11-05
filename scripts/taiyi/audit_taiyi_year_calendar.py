"""Independent printed-calendar cohort audit; whole ancient calendar stays open."""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_historical import julian_to_proleptic_gregorian
from fatebridge.core.metaphysics.taiyi_year_calendar import (
    HISTORICAL_YEAR_PROFILE,
    historical_year_context,
)
from fatebridge.services.metaphysics import calculate_taiyi_analysis

CORPUS = Path(__file__).resolve().parents[2] / "tests/fixtures/taiyi_jinjing_v12"
STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def julian_jdn(text: str) -> int:
    """Independent integer Julian arithmetic, not the production Swiss adapter."""
    y, m, d = map(int, text.split("-"))
    a = (14 - m) // 12
    y += 4800 - a
    m += 12 * a - 3
    return d + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083


def public_case(year=385, month=7, day=1):
    return calculate_taiyi_analysis(
        analysis_year=year,
        analysis_month=month,
        analysis_day=day,
        analysis_hour=12,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
        year_profile=HISTORICAL_YEAR_PROFILE,
    )


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    corpus = corpus.resolve()
    manifest = json.loads((corpus / "manifest.json").read_text())
    for row in (
        manifest["source_files"]
        + manifest["prior_source_references"]
        + [manifest["source_reference"]]
    ):
        if (
            hashlib.sha256((corpus / row["file"]).read_bytes()).hexdigest()
            != row["sha256"]
        ):
            raise ValueError("历史年历来源指纹不符：" + row["file"])
    data = json.loads((corpus / "month-starts.json").read_text())
    rows = data["months"]
    required = {(y, m, False) for y in range(381, 386) for m in range(1, 13)} | {
        (382, 9, True),
        (385, 5, True),
        (386, 1, False),
    }
    fields = {
        "year",
        "month",
        "is_leap_month",
        "julian_start",
        "printed_week_counter",
        "printed_cycle_counter",
        "pdf_page",
        "printed_page",
        "regnal_year",
    }
    if (
        len(rows) != 63
        or any(not fields <= r.keys() for r in rows)
        or {(r["year"], r["month"], r["is_leap_month"]) for r in rows} != required
    ):
        raise ValueError("须保留完整五年62个月及次年终界，共63月首与原印字段")
    dates = []
    observations = []
    daily = 0
    daily_diffs = []
    for row in rows:
        jdn = julian_jdn(row["julian_start"])
        expected = date.fromordinal(jdn - 1721425)
        y, m, d = map(int, row["julian_start"].split("-"))
        actual = julian_to_proleptic_gregorian(y, m, d)
        ok = (
            actual == expected
            and jdn % 7 == row["printed_week_counter"]
            and (jdn + 49) % 60 == row["printed_cycle_counter"]
        )
        observations.append(
            {
                "year": row["year"],
                "month": row["month"],
                "is_leap_month": row["is_leap_month"],
                "source_julian": row["julian_start"],
                "expected_gregorian": expected.isoformat(),
                "computed_gregorian": actual.isoformat(),
                "printed_week_counter": row["printed_week_counter"],
                "printed_cycle_counter": row["printed_cycle_counter"],
                "matches": ok,
            }
        )
        dates.append(expected)
    for i, row in enumerate(rows[:-1]):
        length = (dates[i + 1] - dates[i]).days
        if length not in [29, 30]:
            raise ValueError("原表相邻月首不能构成完整大小月")
        for n in range(length):
            d = dates[i] + timedelta(days=n)
            actual = historical_year_context(d)
            jdn = d.toordinal() + 1721425
            idx = (jdn + 49) % 60
            expected = {
                "year": row["year"],
                "month": row["month"],
                "is_leap_month": row["is_leap_month"],
                "day": n + 1,
                "day_ganzhi": STEMS[idx % 10] + BRANCHES[idx % 12],
                "weekday_sunday_zero": (jdn + 1) % 7,
            }
            daily += 1
            if any(actual[k] != v for k, v in expected.items()):
                daily_diffs.append(
                    {"date": d.isoformat(), "expected": expected, "actual": actual}
                )
    # Original V11 cohort and explicit source correction remain immutable.
    previous = corpus.parent / "taiyi_jinjing_v11"
    case = json.loads((previous / "principal-enclosure.json").read_text())
    correction = json.loads((previous / "transcription-correction.json").read_text())
    truth = {**case["expected"], "wenchang_palace": correction["corrected_value"]}
    result = public_case()
    if "taiyi" not in result:
        raise ValueError(result.get("error"))
    b = result["taiyi"]
    values = {
        **b["core_board"],
        "taiyi_palace": b["taiyi_palace"],
        "wenchang_palace": b["wenchang_palace"],
    }
    replay = [
        {"field": k, "source_value": v, "actual": values[k], "matches": values[k] == v}
        for k, v in truth.items()
    ]
    # The V11 source example states the Taiyi-plus-general reading. New
    # same-side pairs can enclose co-located actors too; absence from that
    # selected source clause is not a denial of those distinct readings.
    paths = b["enclosure_assessment"]["principal_enclosure"]["pattern_paths"]
    enclosures = [b["patterns"][int(p.rsplit(".", 1)[1])] for p in paths]
    additional_pairs = b["enclosure_assessment"]["two_general_enclosure"]["patterns"]
    return {
        "completion_claim": False,
        "source_title": data["source"],
        "required_month_start_anchors": 63,
        "matching_month_start_anchors": sum(r["matches"] for r in observations),
        "month_start_observations": observations,
        "complete_month_intervals": 62,
        "daily_reconstruction_checks": daily,
        "daily_disagreements": daily_diffs,
        "leap_months": [[382, 9], [385, 5]],
        "cohort_calendar_reconstruction_passed": all(r["matches"] for r in observations)
        and not daily_diffs,
        "actual_public_annual_replay": {
            "source_historical_label": case["historical_label"],
            "representative_civil_input": "0385-07-01T12:00:00+08:00",
            "original_day_and_location": "not_stated_not_invented",
            "year_profile": HISTORICAL_YEAR_PROFILE,
            "historical_calendar": b["calendar_rules"]["historical_calendar"],
            "numeric_observations": replay,
            "matching_numeric_observations": sum(r["matches"] for r in replay),
            "enclosure_subjects": [p["subject"] for p in enclosures],
            "enclosure_profile": "jinjing_vol3_principal_enclosure_v1",
            "additional_pair_enclosures": additional_pairs,
            "additional_pairs_included_in_original_source_denominator": False,
            "enclosure_targets_match": [p["subject"] for p in enclosures]
            == [p["subject"] for p in case["enclosures"]],
            "source_ju_matches": b["core_board"]["kook_number"] == case["ju"],
            "scope": "年度原例未载具体月日；所选日期只检验实际历史年适配，不宣称恢复原例时刻。",
        },
        "full_ancient_calendar_reconstructed": False,
        "classic_year_boundary_adjudicated": False,
        "parallel_dynasty_calendars_reconstructed": False,
        "whole_goal_complete": False,
        "count_policy": "63月首与1831日是所选完整历表区段的日期重建检查，不是1831条独立古例。V11同一古例11数值与2主体不作新案例累加；旧差异不删。",
    }
