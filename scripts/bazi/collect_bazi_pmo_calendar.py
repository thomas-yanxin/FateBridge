"""Extract every PMO printed date without importing a calendar calculator.

Run with the separately locked PyMuPDF collector environment. The literal
cells, positions, extraction failures and source consistency flags are kept;
none is replaced using FateBridge, lunardate, HKO or an astronomical model.
"""

from __future__ import annotations

import argparse
import calendar
import gzip
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

import fitz

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
CYCLE = [STEMS[i % 10] + BRANCHES[i % 12] for i in range(60)]
WEEKDAYS = "一二三四五六日"
MONTH = re.compile(r"(?:(闰?)(正|冬|腊|十二|十一|十|九|八|七|六|五|四|三|二|一)月)?")
CELL = re.compile(
    MONTH.pattern
    + r"(初[一二三四五六七八九十]|十[一二三四五六七八九]|二十|廿[一二三四五六七八九]|三十)"
    + rf"([{STEMS}][{BRANCHES}])"
)


def normalized(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).replace("閏", "闰")


def chinese_number(text: str) -> int:
    if text in {"正", "冬", "腊"}:
        return {"正": 1, "冬": 11, "腊": 12}[text]
    numbers = {c: i for i, c in enumerate("零一二三四五六七八九")}
    if text.startswith("初"):
        return 10 if text == "初十" else numbers[text[1:]]
    if text == "三十":
        return 30
    if text == "二十":
        return 20
    if text.startswith("廿"):
        return 20 + numbers[text[1:]]
    if text.startswith("十"):
        return 10 + (numbers[text[1:]] if text[1:] else 0)
    return numbers[text]


def lines(page):
    result = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"])
            if normalized(text):
                result.append({"text": text, "bbox": list(line["bbox"])})
    return result


def page_cells(page, number: int):
    items = lines(page)
    heading = normalized(items[0]["text"])
    year_match = re.search(r"公元(\d{4})年", heading)
    if year_match is None:
        raise ValueError("Missing printed Gregorian year")
    year = int(year_match[1])
    headers = [
        item
        for item in items
        if item["bbox"][1] < 65 and re.fullmatch(r"\d{1,2}月", normalized(item["text"]))
    ]
    headers.sort(key=lambda x: x["bbox"][0])
    expected_year, quarter = 1900 + (number - 3) // 3, (number - 3) % 3
    if year != expected_year or [
        int(normalized(h["text"])[:-1]) for h in headers
    ] != list(range(quarter * 4 + 1, quarter * 4 + 5)):
        raise ValueError(
            "Published year/month headers do not match the complete page sequence"
        )
    date_rows = {
        int(item["text"]): (item["bbox"][1] + item["bbox"][3]) / 2
        for item in items
        if item["bbox"][0] < 42
        and 80 < item["bbox"][1] < 490
        and item["text"].isdigit()
    }
    if set(date_rows) != set(range(1, 32)):
        raise ValueError("Printed Gregorian day column is incomplete")
    body_top = min(
        item["bbox"][1]
        for item in items
        if item["bbox"][0] < 42 and item["text"] == "1" and item["bbox"][1] > 80
    )
    body_bottom = max(date_rows.values()) + 6
    weekdays = sorted(
        [
            item
            for item in items
            if normalized(item["text"]) == "星期" and item["bbox"][1] < 80
        ],
        key=lambda x: x["bbox"][0],
    )
    if len(weekdays) != 4:
        raise ValueError("Weekday headings incomplete")
    centers = [(h["bbox"][0] + h["bbox"][2]) / 2 for h in headers]
    width = centers[1] - centers[0]
    boundaries = (
        [centers[0] - width / 2]
        + [(a + b) / 2 for a, b in zip(centers, centers[1:])]
        + [centers[-1] + width / 2]
    )
    rows = []
    errors = []
    for column, header in enumerate(headers):
        month = int(normalized(header["text"])[:-1])
        weekday_x = (weekdays[column]["bbox"][0] + weekdays[column]["bbox"][2]) / 2
        by_day = defaultdict(lambda: {"lunar": [], "weekday": []})
        for item in items:
            x0, y0, x1, y1 = item["bbox"]
            x, y = (x0 + x1) / 2, (y0 + y1) / 2
            if not (
                boundaries[column] < x < boundaries[column + 1]
                and body_top <= y0
                and y < body_bottom
            ):
                continue
            day = min(date_rows, key=lambda k: abs(date_rows[k] - y))
            if abs(date_rows[day] - y) > 4:
                errors.append(
                    {
                        "source_pdf_page": number,
                        "year": year,
                        "month": month,
                        "unassigned_item": item,
                    }
                )
                continue
            kind = "weekday" if abs(x - weekday_x) < 10 else "lunar"
            by_day[day][kind].append(item)
        count = calendar.monthrange(year, month)[1]
        for day in range(1, 32):
            items_for_day = by_day.get(day, {"lunar": [], "weekday": []})
            literal = "".join(
                normalized(x["text"])
                for x in sorted(
                    items_for_day["lunar"], key=lambda x: (x["bbox"][0], x["bbox"][1])
                )
            )
            weekday = "".join(normalized(x["text"]) for x in items_for_day["weekday"])
            if day > count:
                if literal or weekday:
                    errors.append(
                        {
                            "source_pdf_page": number,
                            "year": year,
                            "month": month,
                            "day": day,
                            "error": "Printed data outside Gregorian month",
                            "literal": literal,
                            "weekday": weekday,
                        }
                    )
                continue
            matched = CELL.fullmatch(literal)
            row = {
                "solar": date(year, month, day).isoformat(),
                "source_pdf_page": number,
                "literal": literal,
                "weekday_literal": weekday,
                "source_tokens": items_for_day,
            }
            if matched is None or weekday not in WEEKDAYS or len(weekday) != 1:
                errors.append({**row, "error": "Unrecognized literal cell or weekday"})
            else:
                leap, lunar_month, lunar_day, ganzhi = matched.groups()
                row.update(
                    lunar_month_marker=(
                        chinese_number(lunar_month) if lunar_month else None
                    ),
                    leap_marker=bool(leap) if lunar_month else None,
                    lunar_day=chinese_number(lunar_day),
                    day_ganzhi=ganzhi,
                )
            rows.append(row)
    return rows, errors


def collect(source: Path):
    document = fitz.open(source)
    if len(document) != 380:
        raise ValueError("Unexpected full source length")
    rows, errors = [], []
    for number in range(3, 381):
        try:
            collected, problems = page_cells(document[number - 1], number)
            rows.extend(collected)
            errors.extend(problems)
        except Exception as error:
            errors.append(
                {
                    "source_pdf_page": number,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
    rows.sort(key=lambda r: r["solar"])
    flags = []
    lunar_year, lunar_month, leap = 1899, None, None
    previous = None
    for row in rows:
        if "lunar_day" not in row:
            previous = None
            continue
        solar = date.fromisoformat(row["solar"])
        marker = row["lunar_month_marker"]
        if marker is not None:
            if marker == 1 and row["leap_marker"] is False and row["lunar_day"] == 1:
                lunar_year = solar.year
            lunar_month, leap = marker, row["leap_marker"]
        if lunar_month is None or leap is None:
            errors.append(
                {
                    "solar": row["solar"],
                    "error": "Lunar month/leap not established by printed marker",
                }
            )
            previous = None
            continue
        row.update(
            year=lunar_year, month=lunar_month, day=row["lunar_day"], is_leap_month=leap
        )
        if row["weekday_literal"] != WEEKDAYS[solar.weekday()]:
            flags.append(
                {
                    "solar": row["solar"],
                    "kind": "printed_weekday_vs_gregorian_arithmetic",
                    "literal": row["weekday_literal"],
                    "gregorian_weekday": WEEKDAYS[solar.weekday()],
                }
            )
        if row["day_ganzhi"] not in CYCLE:
            flags.append(
                {
                    "solar": row["solar"],
                    "kind": "invalid_printed_sexagenary_pair",
                    "literal": row["day_ganzhi"],
                }
            )
        if previous is not None:
            if solar != date.fromisoformat(previous["solar"]) + timedelta(days=1):
                flags.append({"solar": row["solar"], "kind": "source_date_gap"})
            if (
                previous["day_ganzhi"] in CYCLE
                and row["day_ganzhi"]
                != CYCLE[(CYCLE.index(previous["day_ganzhi"]) + 1) % 60]
            ):
                flags.append(
                    {
                        "solar": row["solar"],
                        "kind": "printed_ganzhi_cycle_discontinuity",
                        "previous": previous["day_ganzhi"],
                        "literal": row["day_ganzhi"],
                    }
                )
            same_month = all(
                row[k] == previous[k] for k in ("year", "month", "is_leap_month")
            )
            if (
                same_month
                and row["day"] != previous["day"] + 1
                or not same_month
                and (row["day"] != 1 or previous["day"] not in (29, 30))
            ):
                flags.append(
                    {
                        "solar": row["solar"],
                        "kind": "printed_lunar_day_discontinuity",
                        "previous": {
                            k: previous[k]
                            for k in ("year", "month", "day", "is_leap_month")
                        },
                        "current": {
                            k: row[k] for k in ("year", "month", "day", "is_leap_month")
                        },
                    }
                )
        previous = row
    return {
        "source_pdf_sha256": sha256(source.read_bytes()).hexdigest(),
        "collector_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "pymupdf_version": fitz.VersionBind,
        "source_pages": 380,
        "date_pages": 378,
        "rows": rows,
        "collection_errors": errors,
        "source_consistency_flags": flags,
        "expected_source_dates": 46021,
        "candidate_calculators_imported": False,
        "initial_lunar_year_basis": "Printed PMO1900 January heading 己亥年 and first cell 十二月初一; Gregorian1899 is the preceding year, corroborated by the already retained PMO/TAM prefix; no candidate conversion supplied it.",
        "new_independent_observation_count": 0,
        "whole_goal_complete": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Keep every earlier extraction result")
    result = collect(args.source)
    data = (
        json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()
    args.output.write_bytes(gzip.compress(data, mtime=0))
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        sha256(args.output.read_bytes()).hexdigest() + "\n"
    )
    print(
        json.dumps(
            {
                "source_rows": len(result["rows"]),
                "collection_errors": len(result["collection_errors"]),
                "source_consistency_flags": len(result["source_consistency_flags"]),
                "candidate_comparisons": 0,
            }
        )
    )
    return int(
        bool(result["collection_errors"])
        or len(result["rows"]) != result["expected_source_dates"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
