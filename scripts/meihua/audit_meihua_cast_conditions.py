"""Replay selected HKO lunar labels and separate civil and Zi-start clocks."""

import json
from datetime import date, timedelta

from pydantic import JsonValue

from fatebridge.services.divination import calculate_meihua_analysis

HKO_URLS = [
    "https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T1993c.txt",
    "https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T2001c.txt",
]
HKO_LABELS = [
    ("1993-02-03", "酉", 1, 12, False),
    ("1993-02-04", "酉", 1, 13, False),
    ("2001-01-23", "辰", 12, 29, False),
    ("2001-01-24", "巳", 1, 1, False),
    ("2001-02-03", "巳", 1, 11, False),
    ("2001-02-04", "巳", 1, 12, False),
    ("2001-05-22", "巳", 4, 30, False),
    ("2001-05-23", "巳", 4, 1, True),
    ("2001-06-20", "巳", 4, 29, True),
    ("2001-06-21", "巳", 5, 1, False),
]


def audit_cast_clocks() -> dict[str, JsonValue]:
    """Compare published daily labels; ordinal arithmetic shares the epoch only."""
    reports = []
    for label, year_branch, lunar_month, lunar_day, leap in HKO_LABELS:
        civil = date.fromisoformat(label)
        for hour, minute in [(0, 0), (22, 59), (23, 0), (23, 59)]:
            output = calculate_meihua_analysis(
                analysis_year=civil.year,
                analysis_month=civil.month,
                analysis_day=civil.day,
                analysis_hour=hour,
                analysis_minute=minute,
                analysis_timezone="+08:00",
            )
            cast = output["meihua"]
            seed = cast["seed"]
            calendar = cast["calendar_policy"]
            expected_hour = "亥" if hour == 22 else "子"
            expected = (year_branch, lunar_month, lunar_day, expected_hour, leap)
            actual = (
                seed["year_branch"],
                seed["lunar_month"],
                seed["lunar_day"],
                seed["hour_branch"],
                calendar["is_leap_month"],
            )
            clock = output["interpretation"]["day_qi"]
            calendars = [row["calendar"] for row in clock["calendar_candidates"]]
            expected_dates = [civil]
            if hour == 23:
                expected_dates.append(civil + timedelta(days=1))
            else:
                pass
            expected_days = []
            for candidate_date in expected_dates:
                day_index = (candidate_date - date(2000, 1, 7)).days % 60
                expected_days.append(
                    (
                        candidate_date.isoformat(),
                        "甲乙丙丁戊己庚辛壬癸"[day_index % 10]
                        + "子丑寅卯辰巳午未申酉戌亥"[day_index % 12],
                    )
                )
            actual_days = [
                (candidate["date"], candidate["ganzhi"]) for candidate in calendars
            ]
            reports.append(
                {
                    "civil_datetime": f"{label}T{hour:02}:{minute:02}:00+08:00",
                    "published_lunar_label_matches": actual == expected,
                    "ordinal_day_candidates_match": actual_days == expected_days,
                    "selected_midnight": clock["selected_candidate_id"]
                    == "local_midnight",
                    "named_boundaries_match": [
                        candidate["day_boundary"] for candidate in calendars
                    ]
                    == (
                        ["local_midnight", "zi_start"]
                        if hour == 23
                        else ["local_midnight"]
                    ),
                }
            )
    replay = calculate_meihua_analysis(
        analysis_year=1993,
        analysis_month=2,
        analysis_day=3,
        analysis_hour=12,
        analysis_timezone="+08:00",
    )
    lunar_vector = replay["meihua"]["seed"]
    solar_term_vector = {
        "year": replay["four_pillars"]["year"],
        "month_branch": replay["meihua"]["seasonal_strength"]["month_branch"],
    }
    vectors_match = lunar_vector == {
        "year_branch": "酉",
        "lunar_month": 1,
        "lunar_day": 12,
        "hour_branch": "午",
        "upper_number": 7,
        "lower_number": 6,
        "moving_line": 6,
    } and solar_term_vector == {
        "year": {"stem": "壬", "branch": "申"},
        "month_branch": "丑",
    }
    return {
        "audit_id": "meihua_cast_clocks_hko_selected_v1",
        "sources": HKO_URLS,
        "reference_scope": "New selected probes, frozen before the change; no lunar algorithm tuned. HKO labels are publisher cross-checks, not an independent astronomical model or a holdout from the earlier full calendar survey. Ordinal day arithmetic shares the documented 2000-01-07 epoch with production.",
        "case_count": len(reports),
        "checks_passed": vectors_match
        and all(
            all(value for name, value in report.items() if name != "civil_datetime")
            for report in reports
        ),
        "cases": reports,
        "synthetic_1993_vectors_match": vectors_match,
        "synthetic_1993_lunar_vector": lunar_vector,
        "synthetic_1993_solar_term_vector": solar_term_vector,
    }


if __name__ == "__main__":
    report = audit_cast_clocks()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["checks_passed"] else 1)
