"""Lu Wei image27's four calendars: printed components and explicit policies.

An unprinted whole degree is never zero. A caller can explicitly inherit the
column heading as an interpretation. Ambiguous glyphs and a bare 抄 block a
numeric sum; no Yuan Shi value fills them. Printed-unit arithmetic is distinct
from accepted coordinates, mansion widths, modern dates and life degrees.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, MANSIONS
from fatebridge.core.guolao_coordinates import PROFILES

DATA = Path(__file__).resolve().parents[1] / "data/guolao/luwei-passages-v1.json"
NIJL_DATA = DATA.with_name("nijl-shoushi-passages-v1.json")
CALENDARS = ("tongtian", "kaixi", "huitian", "shoushi")
CALENDAR_LABELS = dict(zip(CALENDARS, ("統天", "開禧", "會天", "授時")))
POLICIES = ("explicit_only", "inherit_column_heading")


def _integer(value: int, maximum: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label}须为明确整数，不接收浮点、布尔或隐式现代度数")
    if not 0 <= value <= maximum:
        raise ValueError(f"{label}越过此源表范围，不能进位或取模来修正")


@dataclass(frozen=True)
class FractionalTerm:
    value: int | None
    status: str
    text: str | None

    def __post_init__(self) -> None:
        if self.status == "literal":
            if self.value is None or not isinstance(self.text, str) or not self.text:
                raise ValueError("明确分抄须同时保留整数释读及原字记录")
            _integer(self.value, 99, "分抄数")
        elif self.status in {"not_printed", "unresolved"}:
            if self.value is not None:
                raise ValueError("未印单位或未释数字不能暗补成零或其他数")
            if self.status == "not_printed" and self.text is not None:
                raise ValueError("未印单位不能附造原字")
        else:
            raise ValueError("分抄须明确标为已读、单位未印或数字未释")

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "status": self.status, "text": self.text}


@dataclass(frozen=True)
class PassageCell:
    calendar: str
    printed_calendar_label: str
    branch: str
    mansion: str
    heading_degree: int
    printed_degree: int | None
    minute: FractionalTerm
    second: FractionalTerm
    normalized_cell_text: str
    second_unit: str = "抄"

    def __post_init__(self) -> None:
        if (
            self.calendar not in CALENDARS
            or self.branch not in BRANCHES
            or len(self.branch) != 1
        ):
            raise ValueError("须为本图四历之一及单个明确辰支")
        if self.mansion not in MANSIONS:
            raise ValueError("须保留列头明确宿名")
        if self.printed_calendar_label != CALENDAR_LABELS[self.calendar]:
            raise ValueError("历名标注与所选源行不符，不能换名混历")
        if self.second_unit not in {"抄", "秒"}:
            raise ValueError("须保留本格明确的小单位，不能跨影像换字")
        _integer(self.heading_degree, 40, "列头整度")
        if self.printed_degree is not None:
            _integer(self.printed_degree, 40, "格内重印整度")
        if not isinstance(self.minute, FractionalTerm) or not isinstance(
            self.second, FractionalTerm
        ):
            raise TypeError("分抄须用具名源字组件")

    def resolve(self, *, whole_degree_policy: str) -> dict[str, Any]:
        if whole_degree_policy not in POLICIES:
            raise ValueError("须明确选择只用格内整度或承接列头，不能猜整度")
        inherited = (
            self.printed_degree is None
            and whole_degree_policy == "inherit_column_heading"
        )
        degree = (
            self.printed_degree
            if self.printed_degree is not None
            else self.heading_degree if inherited else None
        )
        unresolved = [
            unit
            for unit, term in [("分", self.minute), (self.second_unit, self.second)]
            if term.status == "unresolved"
        ]
        missing_terms = [
            unit
            for unit, term in [("分", self.minute), (self.second_unit, self.second)]
            if term.status == "not_printed"
        ]
        value = None
        if degree is not None and not unresolved:
            value = (
                Fraction(degree)
                + Fraction(self.minute.value or 0, 100)
                + Fraction(self.second.value or 0, 10000)
            )
        old_example = self.calendar == "shoushi" and (
            (self.branch, self.mansion, degree) in {("卯", "氐", 2), ("申", "毕", 7)}
        )
        return {
            "calendar": self.calendar,
            "printed_calendar_label": self.printed_calendar_label,
            "branch": self.branch,
            "mansion_from_column_heading": self.mansion,
            "heading_degree": self.heading_degree,
            "printed_degree": self.printed_degree,
            "minute": self.minute.as_dict(),
            "second": self.second.as_dict(),
            "normalized_cell_text": self.normalized_cell_text,
            "whole_degree_policy": whole_degree_policy,
            "whole_degree_used": degree,
            "whole_degree_from_heading_interpretation": inherited,
            "unresolved_fractional_units": unresolved,
            "unprinted_fractional_units_contributing_no_literal_term": missing_terms,
            "arithmetic_policy": "literal_printed_units_sum_not_an_emendation_or_coordinate_acceptance",
            "literal_unit_sum_du_exact": str(value) if value is not None else None,
            "status": (
                "source_text_partial"
                if value is None
                else (
                    "column_heading_interpretation"
                    if inherited
                    else "printed_unit_arithmetic"
                )
            ),
            "same_integral_degree_as_later_rejected_old_ruler_example": old_example,
            "later_note_applied_to_change_value": False,
            "coordinate_unit": "historical_du_not_modern_degrees",
            "continuous_coordinate_accepted": False,
            "modern_longitude": None,
            "life_degree": None,
        }


@dataclass(frozen=True)
class PassageRegistry:
    source_id: str
    source_url: str
    source_image_sha256: str
    credit: str
    locator: str
    data_sha256: str
    later_note_image_sha256: str
    cells: tuple[PassageCell, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "cells", tuple(self.cells))
        if any(not isinstance(cell, PassageCell) for cell in self.cells):
            raise TypeError("各格须为已冻结的具名源字组件")
        expected = {(calendar, branch) for calendar in CALENDARS for branch in BRANCHES}
        actual = {(cell.calendar, cell.branch) for cell in self.cells}
        if len(self.cells) != 48 or actual != expected:
            raise ValueError("本图须逐一具备四历十二宫48格，不能重排补齐或混历")

    def entry(
        self, calendar: str, branch: str, *, whole_degree_policy: str
    ) -> dict[str, Any]:
        matches = [
            cell
            for cell in self.cells
            if cell.calendar == calendar and cell.branch == branch
        ]
        if len(matches) != 1:
            raise ValueError("须明确给本图历名和辰支；不能以年份或其他版本代替")
        result = matches[0].resolve(whole_degree_policy=whole_degree_policy)
        result.update(
            {
                "source_id": self.source_id,
                "source_url": self.source_url,
                "source_image_sha256": self.source_image_sha256,
                "credit": self.credit,
                "locator": self.locator,
                "data_sha256": self.data_sha256,
                "later_note_reference": {
                    "locator": "館藏卷1–2第86幅命度圖上方校注",
                    "source_image_sha256": self.later_note_image_sha256,
                    "rejected_old_examples": ["氐二過卯", "畢七過申"],
                    "comparison_scope": "same_integral_degree_only_not_a_source_emendation",
                },
                "modern_epoch_calibrated": False,
                "luwei_table_emended": False,
                "used_in_native_birth_chart": False,
            }
        )
        return result

    def audit(self, *, whole_degree_policy: str) -> dict[str, Any]:
        entries = [
            self.entry(c.calendar, c.branch, whole_degree_policy=whole_degree_policy)
            for c in self.cells
        ]
        return {
            "source_id": self.source_id,
            "source_image_sha256": self.source_image_sha256,
            "data_sha256": self.data_sha256,
            "credit": self.credit,
            "whole_degree_policy": whole_degree_policy,
            "cells": len(entries),
            "printed_whole_degree_cells": sum(
                c.printed_degree is not None for c in self.cells
            ),
            "whole_degree_not_repeated_cells": sum(
                c.printed_degree is None for c in self.cells
            ),
            "resolved_literal_sum_cells": sum(
                e["literal_unit_sum_du_exact"] is not None for e in entries
            ),
            "entries": entries,
            "full_luwei_coordinate_profile_built": False,
            "modern_epoch_calibrated": False,
            "life_degree_accepted": False,
            "real_world_efficacy_tested": False,
        }

    def compare_yuanshi(
        self, calendar: str, branch: str, *, whole_degree_policy: str
    ) -> dict[str, Any]:
        source = self.entry(calendar, branch, whole_degree_policy=whole_degree_policy)
        value = source["literal_unit_sum_du_exact"]
        comparisons = []
        for name, profile in PROFILES.items():
            reference = next(e for e in profile.entrances if e.branch == branch)
            comparisons.append(
                {
                    "reference_profile": name,
                    "reference_profile_id": profile.profile_id,
                    "mansion": reference.mansion,
                    "degree_du_exact": str(reference.degree_du),
                    "literal_numeric_difference_du_exact": (
                        str(Fraction(value) - reference.degree_du)
                        if value is not None
                        and source["mansion_from_column_heading"] == reference.mansion
                        else None
                    ),
                    "difference_interpreted_as_coordinate_error": False,
                    "reference_used_to_fill_source": False,
                }
            )
        return {"source": source, "comparisons": comparisons}


def load_registry() -> PassageRegistry:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    headings = {h["branch"]: h for h in data["headers"]}
    if len(data["headers"]) != 12 or set(headings) != set(BRANCHES):
        raise ValueError("列头须具备十二个不同辰支")
    cells = tuple(
        PassageCell(
            calendar=row["key"],
            printed_calendar_label=row["printed_label"],
            branch=c["branch"],
            mansion=headings[c["branch"]]["mansion"],
            heading_degree=headings[c["branch"]]["degree"],
            printed_degree=c["printed_degree"],
            minute=FractionalTerm(**c["minute"]),
            second=FractionalTerm(**c["second"]),
            normalized_cell_text=c["normalized_cell_text"],
        )
        for row in data["calendars"]
        for c in row["cells"]
    )
    return PassageRegistry(
        **{
            key: data[key]
            for key in [
                "source_id",
                "source_url",
                "source_image_sha256",
                "credit",
                "locator",
            ]
        },
        data_sha256=hashlib.sha256(raw).hexdigest(),
        later_note_image_sha256=data["later_correction_note"]["source_image_sha256"],
        cells=cells,
    )


def compare_nijl_shoushi(*, whole_degree_policy: str) -> dict[str, Any]:
    """Compare two named digital witnesses; never use one to fill the other.

    The newly inspected NIJL row is not a replacement for the four-calendar
    registry. Its 秒 uses the explicitly declared centesimal arithmetic only.
    Its relationship to the earlier digital witness is not adjudicated.
    """
    if whole_degree_policy not in POLICIES:
        raise ValueError("两份见证须使用同一个明确整度政策作比较")
    blob = NIJL_DATA.read_bytes()
    data = json.loads(blob)
    headings = {h["branch"]: h for h in data["headers"]}
    if len(data["headers"]) != 12 or set(headings) != set(BRANCHES):
        raise ValueError("新见证的列头须自行具备十二个不同辰支")
    if data["calendar"] != "shoushi" or data["printed_calendar_label"] != "授時":
        raise ValueError("新见证只核本行授时，不能换名扩成其他三历")
    branches = [cell["branch"] for cell in data["cells"]]
    if len(branches) != 12 or set(branches) != set(BRANCHES):
        raise ValueError("新见证须逐一保存授时十二格，不补齐或删除难格")
    original = load_registry()
    entries = []
    for cell in data["cells"]:
        heading = headings[cell["branch"]]
        observed = PassageCell(
            calendar=data["calendar"],
            printed_calendar_label=data["printed_calendar_label"],
            branch=cell["branch"],
            mansion=heading["mansion"],
            heading_degree=heading["degree"],
            printed_degree=cell["printed_degree"],
            minute=FractionalTerm(**cell["minute"]),
            second=FractionalTerm(**cell["second"]),
            normalized_cell_text=cell["normalized_cell_text"],
            second_unit=cell["second_unit"],
        ).resolve(whole_degree_policy=whole_degree_policy)
        earlier = original.entry(
            "shoushi", cell["branch"], whole_degree_policy=whole_degree_policy
        )
        left, right = (
            observed["literal_unit_sum_du_exact"],
            earlier["literal_unit_sum_du_exact"],
        )
        entries.append(
            {
                "nijl": observed,
                "nijl_printed_small_unit": cell["second_unit"],
                "earlier_witness": earlier,
                "literal_difference_du_exact": (
                    str(Fraction(left) - Fraction(right))
                    if left is not None
                    and right is not None
                    and observed["mansion_from_column_heading"]
                    == earlier["mansion_from_column_heading"]
                    else None
                ),
                "witness_used_to_fill_or_emend_other": False,
                "difference_interpreted_as_modern_coordinate_error": False,
            }
        )
    return {
        "witness": {
            key: data[key]
            for key in [
                "source_id",
                "source_url",
                "manifest_url",
                "image_url",
                "image_sha256",
                "credit",
                "locator",
                "witness_relation",
                "distinct_holding_records_established",
                "small_unit_arithmetic_policy",
            ]
        },
        "data_sha256": hashlib.sha256(blob).hexdigest(),
        "whole_degree_policy": whole_degree_policy,
        "entries": entries,
        "old_ruler_example_comparison_reference": {
            "witness_source_id": original.source_id,
            "image_sha256": original.later_note_image_sha256,
            "scope": "external_earlier_witness_note_not_a_note_collated_in_NIJL",
        },
        "second_independent_collator": False,
        "independent_edition_established": False,
        "universal_page_offset_applied": False,
        "earlier_source_rewritten": False,
        "complete_luwei_coordinate_profile_built": False,
        "life_degree_accepted": False,
        "modern_epoch_calibrated": False,
    }
