"""NLC3150's literal210 local limit ranges, separate from rate reconstruction.

Year markers are inherited in printed reading order. Missing markers never
trigger an inferred new year. Gaps and overlaps do not select a fallback cell.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_ruler_calendar import NominalSourceDate

DATA = (
    Path(__file__).resolve().parents[1]
    / "data/guolao/ruler-printed-table-nlc3150-v1.json"
)
PROFILE = "nlc3150_literal210_v1"
SCHEMA = "nlc3150_literal210_limit_intervals_v1"
REFERENCE_SHA256 = "df08d12477901314c9a86724d968fc412d629a63c951a93ba1a03a2a925a3845"
GROUPS = ("fude", "qianyi", "jie", "nupu", "xiangmao", "guanlu", "xiongdi")
PALACES = (
    ("福德", "妻妾"),
    ("迁移",),
    ("疾厄",),
    ("奴仆", "男女", "田宅"),
    ("相貌",),
    ("官禄",),
    ("兄弟", "财帛"),
)
YEAR_POLICY = "inherit_last_explicit_year_marker_in_printed_right_to_left_order_without_automatic_year_rollover"
_DIGITS = "一二三四五六七八九"
_LABEL = re.compile(
    r"(?:(?P<year>[一二三四五六七八九十]+)年)?(?P<month>正|[一二三四五六七八九十]+)月(?P<day>初?[一二三四五六七八九十]+)"
)


def _number(text: str) -> int:
    """Only the normalized literal numerals used on this specific sheet."""
    for n in range(1, 31):
        tens, ones = divmod(n, 10)
        printed = (
            _DIGITS[n - 1]
            if n < 10
            else ("" if tens == 1 else _DIGITS[tens - 1])
            + "十"
            + (_DIGITS[ones - 1] if ones else "")
        )
        if text == printed:
            return n
    raise ValueError("原表数字未释或不是已声明的规范汉字，不按邻格填数")


def _date(text: str, context_year: int | None) -> tuple[NominalSourceDate, int | None]:
    match = _LABEL.fullmatch(text)
    if match is None:
        raise ValueError("原表日期格式未释，不猜缺月、缺日或整年")
    explicit = _number(match["year"]) if match["year"] else None
    year = explicit if explicit is not None else context_year
    if year is None:
        raise ValueError("必须先见明确序年，不能默取一年")
    month = 1 if match["month"] == "正" else _number(match["month"])
    day_text = match["day"]
    day = _number(day_text.removeprefix("初"))
    if day_text.startswith("初") and day > 10:
        raise ValueError("初字仅按本表初一至初十规范释读")
    return NominalSourceDate(year, month, day), explicit


@dataclass(frozen=True)
class LiteralLimitCell:
    group: str
    column: int
    literal_text: str
    start: NominalSourceDate
    last: NominalSourceDate
    start_year_marker: int | None
    last_year_marker: int | None

    @property
    def end_exclusive_days(self) -> F:
        return self.last.elapsed_days + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "column": self.column,
            "source_page": 36,
            "leaf": "right" if self.column <= 14 else "left",
            "read_view": self.group
            + ("-cols01-14.png" if self.column <= 14 else "-cols15-30.png"),
            "normalized_literal_text": self.literal_text,
            "explicit_start_year_marker": self.start_year_marker,
            "explicit_last_day_year_marker": self.last_year_marker,
            "start_nominal_source_date": self.start.as_dict(),
            "last_included_nominal_day": self.last.as_dict(),
            "start_nominal_days_exact": str(self.start.elapsed_days),
            "end_exclusive_nominal_days_exact": str(self.end_exclusive_days),
            "span_nominal_days_exact": str(
                self.end_exclusive_days - self.start.elapsed_days
            ),
            "last_day_includes_all_fractional_instants": True,
            "reading_corrected_by_rate_formula": False,
        }


class PrintedLimitTable:
    """Literal lookup preserving all matching cells and unassigned gaps."""

    def __init__(self, source: dict[str, Any], fingerprint: str):
        if (
            source["schema"] != SCHEMA
            or source["profile_id"] != PROFILE
            or source["year_context_policy"] != YEAR_POLICY
            or [r["group"] for r in source["rows"]] != list(GROUPS)
            or [tuple(r["palaces"]) for r in source["rows"]] != list(PALACES)
            or any(len(r["cells"]) != 30 for r in source["rows"])
            or source["source_intervals_corrected_by_formula"] is not False
            or source["used_in_native_birth_chart"] is not False
        ):
            raise ValueError("原表须完整保持七行各30格及明确的年份承接政策")
        self.source = source
        self.fingerprint = fingerprint
        self.rows: dict[str, tuple[LiteralLimitCell, ...]] = {}
        for row in source["rows"]:
            context = None
            cells = []
            for i, text in enumerate(row["cells"], 1):
                pieces = text.split("|")
                if len(pieces) != 2:
                    raise ValueError("每格须独立录读起日和末日")
                start, start_marker = _date(pieces[0], context)
                context = start.year
                last, last_marker = _date(pieces[1], context)
                context = last.year
                if last.elapsed_days < start.elapsed_days:
                    raise ValueError(
                        "原格起末日倒置；不能以自动进年修复，须另列未释来源"
                    )
                cells.append(
                    LiteralLimitCell(
                        row["group"], i, text, start, last, start_marker, last_marker
                    )
                )
            self.rows[row["group"]] = tuple(cells)

    def _group(self, group: str) -> tuple[LiteralLimitCell, ...]:
        if not isinstance(group, str) or group not in GROUPS:
            raise ValueError("须明确选择具名的七行之一，不跨行或按别名猜组")
        return self.rows[group]

    def _provenance(self, group: str) -> dict[str, Any]:
        row = self.source["rows"][GROUPS.index(group)]
        return {
            "profile_id": PROFILE,
            "data_sha256": self.fingerprint,
            "source_id": self.source["source"]["id"],
            "printed_heading": row["printed_heading"],
            "normalized_palaces": list(row["palaces"]),
            "year_context_policy": YEAR_POLICY,
            "date_basis": self.source["source_date_convention"],
            "first_reading_only_not_independent_second_collation": True,
            "calendar_date": None,
            "birth_age": None,
            "life_degree": None,
            "used_in_native_birth_chart": False,
            "real_world_efficacy_established": False,
        }

    def cell(self, group: str, column: int) -> dict[str, Any]:
        row = self._group(group)
        if type(column) is not int or not 1 <= column <= 30:
            raise ValueError("原表列号须为1至30的明确整数")
        return dict(self._provenance(group), cell=row[column - 1].as_dict())

    def lookup(self, group: str, date: NominalSourceDate) -> dict[str, Any]:
        row = self._group(group)
        if not isinstance(date, NominalSourceDate):
            raise TypeError("须明确使用本限名义日期，不接收公历、年龄或字符串")
        t = date.elapsed_days
        end = max(c.end_exclusive_days for c in row)
        if t < min(c.start.elapsed_days for c in row) or t > end:
            raise ValueError("日期超出本地原刊限表；不能将公历年份代入名义序年")
        matches = [
            c.as_dict() for c in row if c.start.elapsed_days <= t < c.end_exclusive_days
        ]
        status = (
            "at_printed_limit_end"
            if t == end
            else (
                "unique_literal_cell"
                if len(matches) == 1
                else (
                    "unassigned_printed_gap"
                    if not matches
                    else "ambiguous_printed_overlap"
                )
            )
        )
        return dict(
            self._provenance(group),
            nominal_source_date=date.as_dict(),
            status=status,
            matching_cells=matches,
            formula_fallback_used=False,
            selected_cell=matches[0]["column"] if len(matches) == 1 else None,
        )

    def audit(self) -> dict[str, Any]:
        rows = []
        for group in GROUPS:
            cells = self.rows[group]
            gaps: list[dict[str, Any]] = []
            overlaps: list[dict[str, Any]] = []
            for a, b in zip(cells, cells[1:]):
                difference = b.start.elapsed_days - a.end_exclusive_days
                if difference:
                    (gaps if difference > 0 else overlaps).append(
                        {
                            "after_column": a.column,
                            "before_column": b.column,
                            "signed_gap_nominal_days_exact": str(difference),
                            "left_end_exclusive_nominal_days_exact": str(
                                a.end_exclusive_days
                            ),
                            "right_start_nominal_days_exact": str(b.start.elapsed_days),
                            "automatically_repaired": False,
                        }
                    )
            rows.append(
                dict(
                    self._provenance(group),
                    group=group,
                    cells=[c.as_dict() for c in cells],
                    gaps=gaps,
                    overlaps=overlaps,
                )
            )
        return {
            "profile_id": PROFILE,
            "source": self.source["source"],
            "data_sha256": self.fingerprint,
            "complete_literal_first_reading_slots": 210,
            "independent_second_collation_completed": False,
            "source_intervals_corrected_by_formula": False,
            "full_birth_limit_schedule_accepted": False,
            "real_world_efficacy_established": False,
            "rows": rows,
        }


def load_printed_limit_table(profile: str) -> PrintedLimitTable:
    if profile != PROFILE:
        raise ValueError("须明确选择nlc3150_literal210_v1，不默取底本")
    blob = DATA.read_bytes()
    fingerprint = hashlib.sha256(blob).hexdigest()
    if fingerprint != REFERENCE_SHA256:
        raise ValueError("完整原格资料哈希变化，须保留旧版重新核验")
    source = json.loads(blob)
    old = DATA.with_name("ruler-calendar-nlc3150-v1.json")
    if hashlib.sha256(old.read_bytes()).hexdigest() != source["old_rate_data_sha256"]:
        raise ValueError("此前条文资料发生漂移，不能混用公式版本")
    return PrintedLimitTable(source, fingerprint)
