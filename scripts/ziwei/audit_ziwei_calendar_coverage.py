"""Compare civil date labels with consecutive printed calendar tables."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Protocol, TypedDict

from fatebridge.core.almanac import (
    LUNAR_SUPPORTED_SOLAR_END,
    LUNAR_SUPPORTED_SOLAR_START,
    _lunar_date_from_solar,
)
from scripts.ziwei.audit_ziwei_calendar_sources import frozen_calendar_rows
from scripts.ziwei.ziwei_conditional_inputs import FIXTURES


class HkoCalendarRow(TypedDict):
    solar: date
    year: int
    month: int | None
    day: int
    is_leap: bool | None


class HkoRowsReader(Protocol):
    def __call__(self, text: str, year: int) -> list[HkoCalendarRow]: ...


MONTHS = {
    name: i
    for i, name in enumerate(
        (
            "正月",
            "二月",
            "三月",
            "四月",
            "五月",
            "六月",
            "七月",
            "八月",
            "九月",
            "十月",
            "十一月",
            "十二月",
        ),
        1,
    )
}
DAYS = {
    name: i
    for i, name in enumerate(
        (
            "初一",
            "初二",
            "初三",
            "初四",
            "初五",
            "初六",
            "初七",
            "初八",
            "初九",
            "初十",
            "十一",
            "十二",
            "十三",
            "十四",
            "十五",
            "十六",
            "十七",
            "十八",
            "十九",
            "二十",
            "廿一",
            "廿二",
            "廿三",
            "廿四",
            "廿五",
            "廿六",
            "廿七",
            "廿八",
            "廿九",
            "三十",
        ),
        1,
    )
}
HKO_ROW = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\S+)")


def hko_rows(
    text: str,
    year: int,
    initial_month: int | None = None,
    initial_leap: bool | None = None,
) -> list[HkoCalendarRow]:
    """Read HKO cells independently; retain missing prefix month information.

    Annual text tables omit the month name on Jan 1 when it is not 初一.
    Never infer that missing month/leap status using the engine under test.
    Every day cell is checked; the full-date denominator is separate.
    """
    result: list[HkoCalendarRow] = []
    month, leap = initial_month, initial_leap
    lunar_year = year - 1
    for line in text.splitlines():
        match = HKO_ROW.match(line)
        if not match:
            continue
        else:
            pass
        y, m, d = (int(x) for x in match.groups()[:3])
        solar = date(y, m, d)
        token = match.group(4)
        month_token = token.removeprefix("閏").removeprefix("闰")
        if month_token in MONTHS:
            month = MONTHS[month_token]
            leap = token.startswith(("閏", "闰"))
            day = 1
            if month == 1 and not leap:
                lunar_year = year
            else:
                pass
        else:
            day = DAYS[token]  # unknown spellings are errors, not skipped rows
        result.append(
            dict(solar=solar, year=lunar_year, month=month, day=day, is_leap=leap)
        )
    expected_count = (date(year + 1, 1, 1) - date(year, 1, 1)).days
    expected_dates = [
        date(year, 1, 1) + timedelta(days=i) for i in range(expected_count)
    ]
    if [r["solar"] for r in result] != expected_dates:
        raise ValueError(f"HKO {year} table has missing, duplicate or unordered rows")
    else:
        pass
    return result


def audit_calendar(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest = json.loads(
        (fixtures / "calendar_manifest.json").read_text(encoding="utf-8")
    )
    mismatches: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    if [s["year"] for s in manifest["sources"]] != list(range(1901, 2101)):
        raise ValueError(
            "The complete fixed HKO 1901-2100 source cohort must be retained"
        )
    else:
        pass
    supported_start, supported_end = (
        LUNAR_SUPPORTED_SOLAR_START,
        LUNAR_SUPPORTED_SOLAR_END,
    )
    _, printed_1900 = frozen_calendar_rows(fixtures)
    last = printed_1900[-1]
    last_year, last_month, last_leap = 1900, last["month"], last["is_leap_month"]
    recovered_prefix_cells = 0
    for source in manifest["sources"]:
        data = (fixtures / source["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError(f"Source checksum mismatch: {source['path']}")
        else:
            pass
        adjacent = last_year is not None and source["year"] == last_year + 1
        if source["year"] == 1901:
            recovered_prefix_cells = sum(
                r["month"] is None
                for r in hko_rows(data.decode("utf-8-sig"), source["year"])
            )
        else:
            pass
        rows = hko_rows(
            data.decode("utf-8-sig"),
            source["year"],
            last_month if adjacent else None,
            last_leap if adjacent else None,
        )
        if source["year"] == 1901 and (
            rows[0]["solar"] != date.fromisoformat(last["solar"]) + timedelta(days=1)
            or (rows[0]["year"], rows[0]["month"], rows[0]["day"], rows[0]["is_leap"])
            != (last["year"], last["month"], last["day"] + 1, last["is_leap_month"])
        ):
            mismatches.append(dict(case="tam_1900_hko_1901_printed_date_seam"))
        else:
            pass
        last_year, last_month, last_leap = (
            source["year"],
            rows[-1]["month"],
            rows[-1]["is_leap"],
        )
        # The reference cohort is fixed. A smaller advertised runtime range is
        # a failure, never permission to drop difficult printed dates.
        supported_rows = rows
        for row in supported_rows:
            if not supported_start <= row["solar"] <= supported_end:
                mismatches.append(
                    dict(
                        case="runtime_support_reduced_fixed_reference_cohort",
                        solar=row["solar"].isoformat(),
                    )
                )
            else:
                pass
            got = _lunar_date_from_solar(row["solar"])
            expected = {"year": row["year"], "day": row["day"]}
            if row["month"] is not None:
                expected.update(month=row["month"], isLeapMonth=row["is_leap"])
            else:
                pass
            actual = {k: getattr(got, k) for k in expected}
            if expected != actual:
                mismatches.append(
                    dict(
                        solar=row["solar"].isoformat(), expected=expected, actual=actual
                    )
                )
            else:
                pass
        coverage.append(
            {
                "year": source["year"],
                "source_rows": len(rows),
                "day_and_year_cells": len(supported_rows),
                "full_date_cells": sum(r["month"] is not None for r in supported_rows),
                "prefix_month_not_published": sum(
                    r["month"] is None for r in supported_rows
                ),
                "outside_engine_support": sum(
                    not supported_start <= r["solar"] <= supported_end for r in rows
                ),
            }
        )
    return {
        "status": "pass_in_frozen_corpus" if not mismatches else "failed",
        "coverage": coverage,
        "day_and_year_cells": sum(r["day_and_year_cells"] for r in coverage),
        "full_date_cells": sum(r["full_date_cells"] for r in coverage),
        "outside_engine_support": sum(r["outside_engine_support"] for r in coverage),
        "frozen_manifest_declared_engine_range": {
            "start": manifest["engine_supported_solar_start"],
            "end": manifest["engine_supported_solar_end"],
        },
        "actual_engine_supported_range": {
            "start": supported_start.isoformat(),
            "end": supported_end.isoformat(),
        },
        "source_prefix_cells_recovered_from_preceding_tam_table": recovered_prefix_cells,
        "recovered_month_labels_are_explicitly_printed_in_each_hko_cell": False,
        "preceding_printed_anchor": last,
        "mismatches": mismatches,
        "limits": [
            "HKO begins in 1901; 1900 has a separately checked complete TAM printed-date witness, plus a NASA lunar-day-only comparison. None certifies all timezones or apparent-solar clock policies",
            "The 1901 January prefix inherits month/leap from the immediately preceding printed TAM 1900 table; recovered labels are not newly explicit HKO month cells",
            "HKO warns that some distant future new moons near midnight may shift civil dates",
        ],
    }
