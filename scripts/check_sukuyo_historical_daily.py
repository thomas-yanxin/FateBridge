"""Compare direct daily controls to the named historical source and variants."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]
if not __package__:
    sys.path.insert(0, str(ROOT))

from fatebridge.validation.sukuyo_historical_sources import printed_day_ganzhi
from scripts.build_sukuyo_historical_calendar import read_fixture


def verify_daily_controls() -> dict:
    from fatebridge.core.sukuyo import calendar_mansion
    from fatebridge.core.sukuyo_historical_calendar import date_reference

    files, manifest = read_fixture(
        ROOT / "tests/data/sukuyo_historical_daily_controls_v1"
    )
    naoj_count = 0
    hutime_count = 0
    legal_controls = []
    naoj_errors: list[dict[str, Any]] = []
    day_ganzhi_errors: list[dict[str, Any]] = []
    control_errors: list[dict[str, Any]] = []
    naoj_dates, control_dates = set(), set()
    for record in manifest["records"]:
        request = parse_qs(
            files[record["request"]].decode("ascii"), strict_parsing=True
        )
        raw = files[record["response"]]
        if record["provider"] == "NAOJ":
            first = date.fromisoformat(record["first_civil_date"])
            expected_request = {
                "type": "0",
                "gengo": "a000",
                "year": str(first.year),
                "month": str(first.month),
                "day": str(first.day),
                "jg": "1",
                "div": "1",
                "divu": "3",
                "len": str(record["days"]),
                "lenu": "3",
                "gen": "1",
                "csv": "CSV",
            }
            if request != {k: [v] for k, v in expected_request.items()}:
                raise ValueError("NAOJ direct-day control request changed")
            rows = list(csv.reader(io.StringIO(raw.decode("cp932"))))
            if len(rows) != record["days"] + 1 or rows[0] != [
                "西暦",
                "和暦",
                "神武紀元",
                "年の干支",
                "月の干支",
                "日の干支",
            ]:
                raise ValueError("NAOJ direct-day control count/encoding changed")
            for offset, row in enumerate(rows[1:]):
                civil = date(*map(int, row[0].strip().split("/")))
                if civil != first + timedelta(days=offset):
                    raise ValueError("NAOJ direct-day grid changed")
                if civil in naoj_dates:
                    raise ValueError("Duplicate NAOJ direct-day control")
                naoj_dates.add(civil)
                printed = re.search(r"(閏)?(\d{2})月(\d{2})日$", row[1])
                if not printed:
                    raise ValueError("NAOJ direct printed date changed")
                expected = [
                    int(row[2]) - 660,
                    int(printed[2]),
                    int(printed[3]),
                    bool(printed[1]),
                ]
                if civil == date(1873, 1, 1):
                    if expected != [1873, 1, 1, False]:
                        raise ValueError("Meiji Gregorian reform control changed")
                    try:
                        calendar_mansion(
                            civil.isoformat(),
                            zone="+09:00",
                            calendar_basis="japanese_naoj_historical_utc09",
                        )
                    except ValueError:
                        legal_controls.append(
                            {
                                "date": civil.isoformat(),
                                "printed_legal_calendar_fields": expected,
                                "admitted_as_old_lunisolar_date": False,
                            }
                        )
                    else:
                        naoj_errors.append(
                            {
                                "date": civil.isoformat(),
                                "error": "Gregorian reform date entered the old-lunisolar host",
                            }
                        )
                    continue
                actual = calendar_mansion(
                    civil.isoformat(),
                    zone="+09:00",
                    calendar_basis="japanese_naoj_historical_utc09",
                )
                printed_ganzhi = printed_day_ganzhi(row[5])
                actual_ganzhi = actual["calendar_reference"]["day_ganzhi_reference"][
                    "name"
                ]
                if actual_ganzhi != printed_ganzhi:
                    day_ganzhi_errors.append(
                        {
                            "date": civil.isoformat(),
                            "printed": printed_ganzhi,
                            "actual": actual_ganzhi,
                        }
                    )
                if [
                    actual[key]
                    for key in [
                        "lunar_year",
                        "lunar_month",
                        "lunar_day",
                        "is_leap_month",
                    ]
                ] != expected:
                    naoj_errors.append(
                        {"date": civil.isoformat(), "expected": expected}
                    )
                naoj_count += 1
        else:
            fixed = {
                "ical": "2.1",
                "itype": "date",
                "method": "conv",
                "ep": "b",
                "ocal": "1001.1",
                "otype": "date",
                "oprop": "text;jdBegin;jdEnd;uri;isLeap;ofMonth.isLeap;ofMonth.uri",
                "oform": "yW|MMM|d",
                "out": "json",
            }
            if set(request) != {*fixed, "ival"} or any(
                request[key] != [value] for key, value in fixed.items()
            ):
                raise ValueError("HuTime direct-day control request changed")
            values = request["ival"][0].splitlines()
            rows = json.loads(raw)
            if len(rows) != len(values) or len(values) != record["days"]:
                raise ValueError("HuTime direct-day count changed")
            for value, row in zip(values, rows):
                if value in control_dates:
                    raise ValueError("Duplicate HuTime direct-day control")
                control_dates.add(value)
                printed = re.fullmatch(
                    r"(-?\d+)\|(閏)?([1-9]|1[0-2])\|([1-9]|[12][0-9]|30)", row["text"]
                )
                if not printed:
                    raise ValueError("HuTime direct-day printed fields changed")
                expected = [
                    int(printed[1]),
                    int(printed[3]),
                    int(printed[4]),
                    bool(printed[2]),
                ]
                jd = date.fromisoformat(value).toordinal() + 1721424.5
                prefix = "http://datetime.hutime.org/calendar/1001.1/"
                if (
                    row["jdBegin"] != jd
                    or row["jdEnd"] != jd + 1
                    or row["isLeap"] != "False"
                    or row["ofMonth.isLeap"] != ("True" if expected[3] else "False")
                    or row["uri"] != prefix + f"date/{jd:.1f}"
                    or row["ofMonth.uri"]
                    != prefix + f"month/{jd - int(expected[2]) + 1:.1f}"
                ):
                    raise ValueError(
                        "HuTime direct-day identity, period or month flag changed"
                    )
                comparison = date_reference(date.fromisoformat(value))[
                    "cross_source_comparison"
                ]
                if (
                    comparison is None
                    or comparison["control_fields"] != expected
                    or comparison["reference_fields"] == expected
                    or comparison["control_applied_to_primary"]
                ):
                    control_errors.append(
                        {"date": value, "expected_control_fields": expected}
                    )
                hutime_count += 1
    if naoj_count != 225 or hutime_count != 210 or len(legal_controls) != 1:
        raise ValueError("Direct-day control scope changed")
    from fatebridge.core.sukuyo_historical_calendar import SOURCE
    from fatebridge.core.sukuyo_sources import load_source

    expected_disagreement_dates = {
        (date.fromisoformat(row["start"]) + timedelta(days=offset)).isoformat()
        for row in load_source(SOURCE).data["cross_source_disagreement_intervals"]
        for offset in range(row["days"])
    }
    if control_dates != expected_disagreement_dates:
        raise ValueError("Direct-day controls do not cover every retained discrepancy")
    return {
        "format": "sukuyo_historical_direct_daily_check_v2",
        "source_archive_sha256": manifest["archive_sha256"],
        "naoj_inside_host_range_daily_dates": naoj_count,
        "naoj_calculation_to_daily_source_mismatches": naoj_errors,
        "naoj_daily_printed_ganzhi_checked": naoj_count,
        "naoj_daily_printed_ganzhi_mismatches": day_ganzhi_errors,
        "hutime_direct_disagreement_dates": hutime_count,
        "hutime_daily_to_retained_variant_mismatches": control_errors,
        "separate_post_reform_legal_calendar_controls": legal_controls,
        "independent_whole_range_daily_verification": False,
        "all_cross_source_disagreements_resolved": False,
        "scope": "Direct daily endpoints confirm the retained 210 disagreements and selected boundaries. They do not turn the complete month-derived reference into independently observed historical truth.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_daily_controls()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return (
        1
        if result["naoj_calculation_to_daily_source_mismatches"]
        or result["naoj_daily_printed_ganzhi_mismatches"]
        or result["hutime_daily_to_retained_variant_mismatches"]
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
