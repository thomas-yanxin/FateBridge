"""Historical Japanese source facts, including year zero and Meiji truncation.

NAOJ's published month starts are the named reference under review. HuTime is
a separate publication/implementation control with a partly shared historical
corpus. Disagreements are retained, never averaged into one calendar.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any
from urllib.parse import parse_qs

FIRST = date(1, 1, 1)
LAST = date(1872, 12, 31)
END = LAST.toordinal() + 1
REFORM_MONTH = date(1872, 12, 30).toordinal()
HUTIME_PREFIX = "http://datetime.hutime.org/calendar/1001.1/month/"
NAOJ_ENDPOINT = "https://eco.mtk.nao.ac.jp/cgi-bin/koyomi/caldb.cgi"
DAY_CYCLE = tuple(
    "甲乙丙丁戊己庚辛壬癸"[n % 10] + "子丑寅卯辰巳午未申酉戌亥"[n % 12]
    for n in range(60)
)


def printed_day_ganzhi(value: str) -> str:
    """Read the literal source label; never repair an invalid stem/branch pair."""
    match = re.fullmatch(r"(\S{2}) \([^()]+\)", value)
    if not match or match[1] not in DAY_CYCLE:
        raise ValueError("NAOJ printed day ganzhi is not a valid sexagenary pair")
    return match[1]


def gregorian_ordinal(year: int, month: int, day: int) -> int:
    """Gregorian date index with astronomical year numbering, including zero."""
    if any(type(n) is not int for n in (year, month, day)) or not 1 <= month <= 12:
        raise ValueError("Invalid proleptic Gregorian fields")
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    lengths = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if not 1 <= day <= lengths[month - 1]:
        raise ValueError("Invalid proleptic Gregorian day")
    previous = year - 1
    return (
        365 * previous
        + previous // 4
        - previous // 100
        + previous // 400
        + sum(lengths[: month - 1])
        + day
    )


@dataclass(frozen=True)
class MonthStart:
    ordinal: int
    year: int
    month: int
    leap: bool
    # Calendar identity remains comparable with HuTime, which has no day label.
    day_ganzhi: str | None = field(default=None, compare=False)

    def fields(self, ordinal: int) -> list[int | bool]:
        return [self.year, self.month, ordinal - self.ordinal + 1, self.leap]


def parse_naoj(raw: bytes, query_year: int) -> list[MonthStart]:
    rows = list(csv.reader(io.StringIO(raw.decode("cp932"))))
    if not rows or rows[0] != [
        "西暦",
        "和暦",
        "神武紀元",
        "年の干支",
        "月の干支",
        "日の干支",
    ]:
        raise ValueError("NAOJ CSV header/encoding changed")
    result = []
    for row in rows[1:]:
        if len(row) != 6:
            raise ValueError("Unexpected NAOJ column count")
        civil = re.fullmatch(r"\s*(-?\d+)/(\d{2})/(\d{2})", row[0])
        lunar = re.search(r"(閏)?(\d{2})月(\d{2})日$", row[1])
        if not civil or not lunar or lunar[3] != "01":
            raise ValueError("NAOJ record is not a printed month start")
        ordinal = gregorian_ordinal(*map(int, civil.groups()))
        year = int(row[2]) - 660
        if year not in (query_year, query_year + 1) or not 1 <= int(lunar[2]) <= 12:
            raise ValueError("NAOJ lunar year/month contradicts the year query")
        result.append(
            MonthStart(
                ordinal, year, int(lunar[2]), bool(lunar[1]), printed_day_ganzhi(row[5])
            )
        )
    if not result or (result[0].year, result[0].month, result[0].leap) != (
        query_year,
        1,
        False,
    ):
        raise ValueError(
            "NAOJ 400-day query must begin at the requested lunar new year"
        )
    if any(a.ordinal >= b.ordinal for a, b in zip(result, result[1:])):
        raise ValueError("NAOJ month starts are not chronological")
    return result


def parse_hutime(row: Any, civil: date) -> tuple[MonthStart, int]:
    if not isinstance(row, dict) or set(row) != {
        "text",
        "jdBegin",
        "jdEnd",
        "uri",
        "isLeap",
    }:
        raise ValueError("HuTime month property set changed")
    match = re.fullmatch(r"(-?\d+)\|(閏)?([1-9]|1[0-2])", row["text"])
    if not match or row["isLeap"] != ("True" if match[2] else "False"):
        raise ValueError("HuTime printed lunar month and leap flag disagree")
    start, finish = row["jdBegin"], row["jdEnd"]
    if any(type(n) not in (int, float) or n % 1 != 0.5 for n in (start, finish)):
        raise ValueError("HuTime period must use half-integer date-period JD")
    ordinal = int(start - 1721424.5)
    length = int(finish - start)
    if not ordinal <= civil.toordinal() < ordinal + length:
        raise ValueError("HuTime month does not contain the input Gregorian date")
    if row["uri"] != HUTIME_PREFIX + f"{start:.1f}":
        raise ValueError("HuTime month URI contradicts its period")
    return MonthStart(ordinal, int(match[1]), int(match[3]), bool(match[2])), length


def _sequence_errors(months: list[MonthStart], final_end: int) -> list[dict[str, Any]]:
    errors = []
    for index, current in enumerate(months):
        following = months[index + 1] if index + 1 < len(months) else None
        length = (following.ordinal if following else final_end) - current.ordinal
        reform = current.ordinal == REFORM_MONTH and length == 2
        if length not in (29, 30) and not reform:
            errors.append(
                {
                    "kind": "unexpected_month_length",
                    "month": current.__dict__,
                    "length": length,
                }
            )
        if following:
            expected = (
                (current.year + 1, 1)
                if current.month == 12
                else (current.year, current.month + 1)
            )
            if (
                following.leap
                and (
                    current.leap
                    or (following.year, following.month)
                    != (current.year, current.month)
                )
            ) or (not following.leap and (following.year, following.month) != expected):
                errors.append(
                    {
                        "kind": "unexpected_year_month_sequence",
                        "previous": current.__dict__,
                        "next": following.__dict__,
                    }
                )
    return errors


def _day_cycle_errors(
    months: list[MonthStart], anchor: MonthStart
) -> list[dict[str, Any]]:
    """Check every captured month start against one source-bound civil-day anchor."""
    if anchor.day_ganzhi is None or anchor.day_ganzhi not in DAY_CYCLE:
        return [{"kind": "invalid_day_cycle_anchor"}]
    start = DAY_CYCLE.index(anchor.day_ganzhi)
    errors = []
    for month in months:
        expected = DAY_CYCLE[(start + month.ordinal - anchor.ordinal) % 60]
        if month.day_ganzhi != expected:
            errors.append(
                {
                    "kind": "day_cycle_discontinuity",
                    "ordinal": month.ordinal,
                    "printed": month.day_ganzhi,
                    "expected_from_anchor": expected,
                }
            )
    return errors


def normalize(
    files: dict[str, bytes], manifest: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    acquisition = json.loads(files["acquisition.json"])
    if acquisition["gregorian_domain_inclusive"] != [
        FIRST.isoformat(),
        LAST.isoformat(),
    ] or acquisition["naoj_lunar_year_queries_inclusive"] != [0, 1872]:
        raise ValueError("Historical source domain changed; review the complete scope")
    grid = [FIRST + timedelta(days=n) for n in range(0, (LAST - FIRST).days + 1, 28)]
    if grid[-1] != LAST:
        grid.append(LAST)
    expected_ids = {f"naoj-{year:04}" for year in range(1873)} | {
        f"hutime-{index:03}" for index in range((len(grid) + 99) // 100)
    }
    records = acquisition["requests"]
    if len(records) != len(expected_ids) or {r["id"] for r in records} != expected_ids:
        raise ValueError("Incomplete or duplicate historical acquisition requests")
    naoj: dict[int, MonthStart] = {}
    naoj_origins: dict[int, set[int]] = {}
    naoj_query_hashes = {}
    hutime: dict[int, tuple[MonthStart, int]] = {}
    naoj_errors: list[dict[str, Any]] = []
    hutime_errors: list[dict[str, Any]] = []
    nulls: list[str] = []
    queried = {}
    for record in records:
        request_raw = files[record["request_file"]]
        raw = files[record["response_file"]]
        for key, content in [
            ("request", request_raw),
            ("response", raw),
            ("metadata", files[record["metadata_file"]]),
        ]:
            if hashlib.sha256(content).hexdigest() != record[key + "_sha256"]:
                raise ValueError("Captured historical source fingerprint changed")
        request = parse_qs(request_raw.decode("ascii"), strict_parsing=True)
        if record["id"].startswith("naoj-"):
            year = int(record["id"].split("-")[1])
            expected = {
                "type": "2",
                "gengo": "a000",
                "year": str(year),
                "month": "1",
                "day": "1",
                "jg": "1",
                "div": "1",
                "divu": "3",
                "len": "400",
                "lenu": "3",
                "gen": "1",
                "csv": "CSV",
            }
            if (
                request != {k: [v] for k, v in expected.items()}
                or record["endpoint"] != NAOJ_ENDPOINT
            ):
                raise ValueError("NAOJ request calendar, unit or epoch policy changed")
            naoj_query_hashes[str(year)] = hashlib.sha256(raw).hexdigest()
            try:
                for month in parse_naoj(raw, year):
                    previous = naoj.setdefault(month.ordinal, month)
                    if previous != month or previous.day_ganzhi != month.day_ganzhi:
                        naoj_errors.append(
                            {
                                "kind": "overlap_label_conflict",
                                "ordinal": month.ordinal,
                                "previous": previous.__dict__,
                                "next": month.__dict__,
                            }
                        )
                    naoj_origins.setdefault(month.ordinal, set()).add(year)
            except ValueError as error:
                naoj_errors.append({"query_year": year, "error": str(error)})
        else:
            index = int(record["id"].split("-")[1])
            values = [d.isoformat() for d in grid[index * 100 : (index + 1) * 100]]
            expected = {
                "ical": "2.1",
                "itype": "date",
                "ival": "\r\n".join(values),
                "method": "conv",
                "ep": "b",
                "ocal": "1001.1",
                "otype": "month",
                "oprop": "text;jdBegin;jdEnd;uri;isLeap",
                "oform": "yW|MMM",
                "out": "json",
            }
            if (
                request != {k: [v] for k, v in expected.items()}
                or record["endpoint"] != "https://ap.hutime.org/cal/"
            ):
                raise ValueError(
                    "HuTime request changed: explicit Gregorian and calendar ID required"
                )
            rows = json.loads(raw)
            if not isinstance(rows, list) or len(rows) != len(values):
                raise ValueError("HuTime response count changed")
            queried[index] = values
            for value, row in zip(values, rows):
                if row is None:
                    nulls.append(value)
                    continue
                try:
                    month, length = parse_hutime(row, date.fromisoformat(value))
                    previous_period = hutime.setdefault(month.ordinal, (month, length))
                    if previous_period != (month, length):
                        hutime_errors.append(
                            {
                                "kind": "overlap_period_conflict",
                                "ordinal": month.ordinal,
                                "previous": [
                                    previous_period[0].__dict__,
                                    previous_period[1],
                                ],
                                "next": [month.__dict__, length],
                            }
                        )
                except ValueError as error:
                    hutime_errors.append({"date": value, "error": str(error)})
    if [value for index in sorted(queried) for value in queried[index]] != [
        d.isoformat() for d in grid
    ]:
        raise ValueError("Historical control grid is incomplete")
    all_naoj = sorted(naoj.values(), key=lambda month: month.ordinal)
    naoj_errors.extend(_sequence_errors(all_naoj, END))
    naoj_months = [
        month
        for index, month in enumerate(all_naoj)
        if month.ordinal < END
        and (all_naoj[index + 1].ordinal if index + 1 < len(all_naoj) else END) > 0
    ]
    if (
        not naoj_months
        or naoj_months[0].ordinal > 1
        or naoj_months[-1].ordinal != REFORM_MONTH
    ):
        naoj_errors.append({"kind": "incomplete_declared_domain"})
    for month in naoj_months:
        if month.year not in naoj_origins[month.ordinal]:
            naoj_errors.append(
                {"kind": "month_absent_from_own_year_query", "month": month.__dict__}
            )
    day_errors: list[dict[str, Any]] = (
        _day_cycle_errors(all_naoj, naoj_months[0])
        if naoj_months
        else [{"kind": "missing_day_cycle_anchor"}]
    )
    naoj_errors.extend(day_errors)
    anchor = naoj_months[0] if naoj_months else None
    day_anchor = (
        {
            "civil_ordinal": anchor.ordinal,
            "day_ganzhi": anchor.day_ganzhi,
            "source_lunar_year_query": anchor.year,
            "source_response_sha256": naoj_query_hashes[str(anchor.year)],
        }
        if anchor
        else None
    )
    hmonths = sorted(hutime.values(), key=lambda item: item[0].ordinal)
    for index, (month, length) in enumerate(hmonths):
        if length not in (29, 30) and not (
            month.ordinal == REFORM_MONTH and length == 2
        ):
            hutime_errors.append(
                {
                    "kind": "unexpected_month_length",
                    "month": month.__dict__,
                    "length": length,
                }
            )
        if (
            index + 1 < len(hmonths)
            and month.ordinal + length != hmonths[index + 1][0].ordinal
        ):
            hutime_errors.append(
                {
                    "kind": "noncontiguous_month_periods",
                    "month": month.__dict__,
                    "length": length,
                    "next_start": hmonths[index + 1][0].ordinal,
                }
            )
    differences: list[dict[str, Any]] = []
    missing_control: list[str] = []
    nstarts = [m.ordinal for m in naoj_months]
    hstarts = [m.ordinal for m, length in hmonths]
    current: dict[str, Any] | None = None
    matched = 0
    for ordinal in range(1, END):
        ni, hi = bisect_right(nstarts, ordinal) - 1, bisect_right(hstarts, ordinal) - 1
        nfields = naoj_months[ni].fields(ordinal) if ni >= 0 else None
        hfields = (
            hmonths[hi][0].fields(ordinal)
            if hi >= 0 and ordinal < hmonths[hi][0].ordinal + hmonths[hi][1]
            else None
        )
        if hfields is None:
            missing_control.append(date.fromordinal(ordinal).isoformat())
        mismatch = nfields != hfields
        month_identities = (
            (nfields[:2] + nfields[3:], hfields[:2] + hfields[3:])
            if nfields and hfields
            else None
        )
        # Preserve day-offset disagreements too; ranges are grouped only when
        # the pair of month identities and the day offset stay constant.
        signature = (
            (repr(month_identities), nfields[2] - hfields[2])
            if nfields and hfields
            else None
        )
        if mismatch:
            if current is None or current["signature"] != signature:
                current = {
                    "start": date.fromordinal(ordinal).isoformat(),
                    "end_inclusive": date.fromordinal(ordinal).isoformat(),
                    "days": 1,
                    "naoj_first_fields": nfields,
                    "hutime_first_fields": hfields,
                    "signature": signature,
                }
                differences.append(current)
            else:
                current["end_inclusive"] = date.fromordinal(ordinal).isoformat()
                current["days"] += 1
        else:
            matched += 1
            current = None
    for row in differences:
        row.pop("signature")
    compiled = []
    for index, month in enumerate(naoj_months):
        finish = naoj_months[index + 1].ordinal if index + 1 < len(naoj_months) else END
        compiled.append(
            [month.ordinal, month.year, month.month, month.leap, finish - month.ordinal]
        )
    eligible = not naoj_errors
    report = {
        "format": "sukuyo_historical_source_admission_v2",
        "gregorian_domain_inclusive": [FIRST.isoformat(), LAST.isoformat()],
        "provider_earliest_lunar_year_advertised": -659,
        "complete_provider_advertised_historical_range": False,
        "public_datetime_year_zero_and_bce_inputs_supported": False,
        "naoj_year_queries": 1873,
        "naoj_reference_months": len(naoj_months),
        "naoj_structural_errors": naoj_errors,
        "naoj_unique_captured_month_start_day_labels_checked": len(all_naoj),
        "naoj_month_start_day_cycle_errors": day_errors,
        "day_cycle_anchor": day_anchor,
        "naoj_reference_import_eligible": eligible,
        "hutime_query_dates": len(grid),
        "hutime_unique_months": len(hmonths),
        "hutime_structural_errors": hutime_errors,
        "hutime_null_query_dates": nulls,
        "control_missing_dates": missing_control,
        "cross_source_matched_dates": matched,
        "cross_source_disagreement_dates": sum(row["days"] for row in differences),
        "cross_source_disagreement_intervals": differences,
        "meiji_final_month_days": 2,
        "all_historical_calendars_accepted": False,
        "historical_local_time_reconstructed": False,
        "independent_original_manuscript_collation": False,
        "scope": "Named NAOJ frozen-reference structural admission only. HuTime disagreement is retained as a separate control, not corrected by majority. The publications share historical source literature; agreement is not independent historical truth or time-standard acceptance.",
    }
    data = {
        "id": "naoj_japanese_historical_month_starts_20261022_v2",
        "supported_range_inclusive": [FIRST.isoformat(), LAST.isoformat()],
        "reference_day_count": END - 1,
        "source_url": NAOJ_ENDPOINT,
        "source_archive_sha256": manifest["archive_sha256"],
        "source_query_response_sha256": naoj_query_hashes,
        "day_cycle_anchor": day_anchor,
        "source_provenance": [
            {
                "lunar_year_end": 453,
                "origin": "naoj_reconstructed_gihou_mean_new_moons_not_contemporary_observation",
            },
            {
                "lunar_year_begin": 454,
                "origin": "naoj_calculated_and_historically_corrected_japanese_calendar_reference",
            },
        ],
        "complete_provider_advertised_historical_range": False,
        "public_datetime_year_zero_and_bce_inputs_supported": False,
        "cross_source_disagreement_intervals": differences,
        "cross_source_disagreement_dates": report["cross_source_disagreement_dates"],
        "hutime_control_structural_findings": {
            "errors": hutime_errors,
            "nulls": nulls,
            "missing_date_count": len(missing_control),
        },
        "historical_calendar_acceptance": False,
        "independent_whole_range_verification": False,
        "historical_local_time_reconstruction": False,
        "months": compiled,
        "scope": "NAOJ frozen month-start reference, proleptic Gregorian dates and astronomical lunar-year numbering. Year zero and the two-day reform month are retained. Fixed UTC+09 is a declared reference policy, not historical local time or ancient daybreak. Early chronology is a reconstruction, and cross-publication disagreements remain unresolved.",
    }
    return data, report
