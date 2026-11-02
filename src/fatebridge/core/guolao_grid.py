"""Literal lookup in Lu Wei image78's 橫看 grid, not an accepted life degree.

Regular integers are semantic readings of printed numerals, not celestial
angles. 初 is a separate marker and is never converted to zero. Named attached
readings preserve visible glyphs and a blank, without accepted coordinate
semantics. The lower palace-limit rows remain untranscribed; they have not
been established as celestial fractional tails. Mansion names stay local.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import BRANCHES, MANSIONS

DATA = Path(__file__).resolve().parents[1] / "data/guolao/life-grid-v1.json"
MARKER_DATA = DATA.with_name("life-grid-markers-v1.json")
_DIGITS = "一二三四五六七八九"


def _integer_text(value: int) -> str:
    if value < 10:
        return _DIGITS[value - 1]
    tens, ones = divmod(value, 10)
    return (
        ("" if tens == 1 else _DIGITS[tens - 1])
        + "十"
        + (_DIGITS[ones - 1] if ones else "")
    )


@dataclass(frozen=True)
class MarkerReading:
    palace: str
    column: int
    mansion: str
    kind: str
    text: str | None
    integer_value: int | None

    def __post_init__(self) -> None:
        if self.palace not in BRANCHES or len(self.palace) != 1:
            raise ValueError("附字须有单个明确宫支")
        if isinstance(self.column, bool) or not isinstance(self.column, int):
            raise TypeError("附字位置须为明确整数列号")
        if not 1 <= self.column <= 30 or self.mansion not in MANSIONS:
            raise ValueError("附字须对应本图1至30列的具名宿标")
        if self.kind == "integer":
            if isinstance(self.integer_value, bool) or not isinstance(
                self.integer_value, int
            ):
                raise TypeError("整数释读须明确给出整数，不能借浮点或默认零补字")
            if not 1 <= self.integer_value <= 30 or self.text != _integer_text(
                self.integer_value
            ):
                raise ValueError("规范汉字与数值释读不符；不能借相邻格改字")
        elif self.kind == "initial":
            if self.text != "初" or self.integer_value is not None:
                raise ValueError("初字须保留为初，不赋数值零")
        elif self.kind == "not_visible":
            if self.text is not None or self.integer_value is not None:
                raise ValueError("未见附字不等于零、初或推定整数")
        else:
            raise ValueError("须明确选择整数、初字或本图未见附字")

    def as_dict(self) -> dict[str, Any]:
        return {
            "palace": self.palace,
            "column": self.column,
            "mansion": self.mansion,
            "kind": self.kind,
            "text": self.text,
            "integer_value": self.integer_value,
            "coordinate_semantics_accepted": False,
            "value_inferred_from_neighbours": False,
        }


@dataclass(frozen=True)
class GridCell:
    mansion_marker: str | None
    numeral_value: int | None
    initial_marker: bool

    def __post_init__(self) -> None:
        if not isinstance(self.initial_marker, bool):
            raise TypeError("初标须明确为布尔值，不以数值冒充")
        if self.mansion_marker is not None and self.mansion_marker not in MANSIONS:
            raise ValueError("宿名标须为具名28宿之一，不要求所有标名都有外圈")
        if self.numeral_value is not None:
            if isinstance(self.numeral_value, bool) or not isinstance(
                self.numeral_value, int
            ):
                raise TypeError("普通格数字只接收明确整数释读")
            if not 1 <= self.numeral_value <= 30:
                raise ValueError("本图普通格数字释读范围为1至30，不接收浮点古度")
        if (
            int(self.mansion_marker is not None)
            + int(self.numeral_value is not None)
            + int(self.initial_marker)
            != 1
        ):
            raise ValueError("每格须且仅须一种已释类别；不猜宿标附字或缺失格")


@dataclass(frozen=True)
class LifeDegreeGrid:
    source_id: str
    source_url: str
    image_url: str
    source_image_sha256: str
    data_sha256: str
    credit: str
    locator: str
    rows: tuple[tuple[GridCell, ...], ...]
    marker_readings: tuple[MarkerReading, ...] = ()
    marker_profile_id: str | None = None
    marker_data_sha256: str | None = None

    def __post_init__(self) -> None:
        rows = tuple(tuple(row) for row in self.rows)
        if len(rows) != 12 or any(len(row) != 30 for row in rows):
            raise ValueError("本图须有明确的12行30列；不按相邻格生成缺格")
        if any(not isinstance(cell, GridCell) for row in rows for cell in row):
            raise TypeError("每格须为明确释读的GridCell")
        object.__setattr__(self, "rows", rows)
        readings = tuple(self.marker_readings)
        if any(not isinstance(r, MarkerReading) for r in readings):
            raise TypeError("附字须为明确的MarkerReading")
        if (readings and not (self.marker_profile_id and self.marker_data_sha256)) or (
            not readings
            and (
                self.marker_profile_id is not None
                or self.marker_data_sha256 is not None
            )
        ):
            raise ValueError(
                "具名附字资料及其指纹须与完整读法一起提供，不能空表冒充同版本"
            )
        if readings:
            expected = {
                (p, c, cell.mansion_marker)
                for p, row in zip(BRANCHES, rows)
                for c, cell in enumerate(row, 1)
                if cell.mansion_marker is not None
            }
            actual = {(r.palace, r.column, r.mansion) for r in readings}
            if len(actual) != len(readings) or actual != expected:
                raise ValueError(
                    "附字须逐一对应本图全部宿名标，不重排、补位或跨版本拼接"
                )
        object.__setattr__(self, "marker_readings", readings)

    def _marker(self, palace: str, column: int) -> MarkerReading | None:
        return next(
            (
                r
                for r in self.marker_readings
                if r.palace == palace and r.column == column
            ),
            None,
        )

    def cell(self, palace: str, column: int) -> dict[str, Any]:
        if palace not in BRANCHES or len(palace) != 1:
            raise ValueError("须明确给出单个宫支，不从现代经度推定")
        if isinstance(column, bool) or not isinstance(column, int):
            raise TypeError("原图列号须为1至30的整数，不接收现代角度或小数")
        if not 1 <= column <= 30:
            raise ValueError("本图列号须为1至30，不取模、不自动换叶或挪一列")
        cell = self.rows[BRANCHES.index(palace)][column - 1]
        reading = self._marker(palace, column)
        return {
            "palace": palace,
            "column": column,
            "leaf": "right" if column <= 14 else "left",
            "mansion_marker": cell.mansion_marker,
            "numeral_value": cell.numeral_value,
            "initial_marker": cell.initial_marker,
            "marker_reading": reading.as_dict() if reading else None,
            "reading_kind": (
                "mansion_marker_visible_reading_not_continuous_coordinate"
                if reading
                else (
                    "mansion_marker_attached_numeral_not_transcribed"
                    if cell.mansion_marker is not None
                    else (
                        "printed_initial_marker_not_numeric_zero"
                        if cell.initial_marker
                        else "regular_numeral_reading_not_continuous_coordinate"
                    )
                )
            ),
            "inherited_mansion": None,
            "continuous_historical_degree": None,
            "modern_longitude": None,
        }

    def compare(
        self, *, source_palace: str, target_palace: str, column: int
    ) -> dict[str, Any]:
        """Compare the declared same column; neither infer nor shift it."""
        source = self.cell(source_palace, column)
        target = self.cell(target_palace, column)
        return {
            "source_id": self.source_id,
            "source_url": self.source_url,
            "image_url": self.image_url,
            "source_image_sha256": self.source_image_sha256,
            "data_sha256": self.data_sha256,
            "marker_profile_id": self.marker_profile_id,
            "marker_data_sha256": self.marker_data_sha256,
            "credit": self.credit,
            "locator": self.locator,
            "source_cell": source,
            "target_cell": target,
            "column_shift_applied": 0,
            "cell_mansion_context_inferred": False,
            "life_degree": None,
            "status": "literal_grid_comparison_not_accepted_life_degree",
            "life_degree_accepted": False,
            "modern_epoch_calibrated": False,
            "used_in_native_birth_chart": False,
        }

    def compare_marker(
        self,
        *,
        source_palace: str,
        target_palace: str,
        mansion: str,
        attached_text: str | None,
    ) -> dict[str, Any]:
        """Find one literal marker, with its attached text explicitly declared.

        None matches only a reading explicitly marked not-visible. It never
        denotes an omitted argument, a zero or an inferred missing numeral.
        """
        if attached_text is not None and not isinstance(attached_text, str):
            raise TypeError("须给原图规范汉字附字，或明确None表示所见空白")
        candidates = [
            r
            for r in self.marker_readings
            if r.palace == source_palace and r.mansion == mansion
        ]
        if len(candidates) != 1:
            raise ValueError("指定宫支/宿标在已录附字中不唯一或不存在，不从普通格猜宿")
        reading = candidates[0]
        if reading.text != attached_text:
            raise ValueError("附字与本图释读不符，不按邻格、全宿度或目标算例改数")
        result = self.compare(
            source_palace=source_palace,
            target_palace=target_palace,
            column=reading.column,
        )
        result["column_selection"] = "exact_named_marker_and_attached_text"
        result["matched_marker"] = reading.as_dict()
        return result

    def audit(self) -> dict[str, Any]:
        cells = [cell for row in self.rows for cell in row]
        restarts = []
        marker_restarts = []
        for palace, row in zip(BRANCHES, self.rows):
            for index, (left, right) in enumerate(zip(row, row[1:]), 1):
                reading = self._marker(palace, index)
                if (
                    reading is not None
                    and reading.integer_value is not None
                    and right.numeral_value is not None
                    and right.numeral_value != reading.integer_value - 1
                ):
                    marker_restarts.append(
                        {
                            "palace": palace,
                            "from_column": index,
                            "to_column": index + 1,
                            "mansion_marker": reading.mansion,
                            "visible_attached_text": reading.text,
                            "from_literal_integer": reading.integer_value,
                            "to_regular_numeral": right.numeral_value,
                            "meaning_adjudicated": False,
                            "label_or_column_corrected": False,
                        }
                    )
                if left.numeral_value is None or right.numeral_value is None:
                    continue
                if right.numeral_value != left.numeral_value - 1:
                    restarts.append(
                        {
                            "palace": palace,
                            "from_column": index,
                            "to_column": index + 1,
                            "from_numeral": left.numeral_value,
                            "to_numeral": right.numeral_value,
                            "new_mansion_inferred": None,
                            "label_or_column_corrected": False,
                        }
                    )
        return {
            "source_id": self.source_id,
            "source_url": self.source_url,
            "image_url": self.image_url,
            "source_image_sha256": self.source_image_sha256,
            "data_sha256": self.data_sha256,
            "marker_profile_id": self.marker_profile_id,
            "marker_data_sha256": self.marker_data_sha256,
            "credit": self.credit,
            "locator": self.locator,
            "palace_order": BRANCHES,
            "rows": 12,
            "columns": 30,
            "positioned_cells": len(cells),
            "regular_numeral_cells": sum(c.numeral_value is not None for c in cells),
            "initial_marker_cells": sum(c.initial_marker for c in cells),
            "mansion_marker_cells": sum(c.mansion_marker is not None for c in cells),
            "unmarked_numeric_restarts": restarts,
            "marker_to_regular_numeric_discontinuities": marker_restarts,
            "marker_readings_recorded": len(self.marker_readings),
            "marker_reading_counts": {
                kind: sum(r.kind == kind for r in self.marker_readings)
                for kind in ["integer", "initial", "not_visible"]
            },
            "all_marker_readings_recorded": bool(self.marker_readings),
            "marker_attached_numerals_collated": bool(self.marker_readings),
            "marker_collation_scope": "visible_text_and_explicit_not_visible_observation_not_complete_numeric_values",
            "marker_numeric_values_complete": bool(self.marker_readings)
            and all(r.kind == "integer" for r in self.marker_readings),
            "marker_coordinate_semantics_accepted": False,
            "fractional_tail_cells_collated": False,
            "fractional_tail_label_is_established_interpretation": False,
            "lower_section_role": "separate_palace_limit_rows_numeric_semantics_unadjudicated",
            "lower_section_numeric_cells_collated": False,
            "full_360_cell_numerical_mapping_accepted": False,
            "modern_epoch_calibrated": False,
            "life_degree_accepted": False,
            "used_in_native_birth_chart": False,
            "real_world_efficacy_tested": False,
        }


def load_grid() -> LifeDegreeGrid:
    raw = DATA.read_bytes()
    data = json.loads(raw)
    marker_raw = MARKER_DATA.read_bytes()
    markers = json.loads(marker_raw)
    if (
        markers["matrix_source_id"] != data["source_id"]
        or markers["matrix_data_sha256"] != hashlib.sha256(raw).hexdigest()
        or markers["source_image_sha256"] != data["source_image_sha256"]
    ):
        raise ValueError("附字文件与具名矩阵/原图指纹不一致，拒绝跨版本合表")
    if "".join(row["palace"] for row in data["rows"]) != BRANCHES:
        raise ValueError("源图行支顺序须明确，不自动排序或补行")
    rows = tuple(
        tuple(GridCell(**cell) for cell in row["cells"]) for row in data["rows"]
    )
    return LifeDegreeGrid(
        **{
            key: data[key]
            for key in [
                "source_id",
                "source_url",
                "image_url",
                "source_image_sha256",
                "credit",
                "locator",
            ]
        },
        data_sha256=hashlib.sha256(raw).hexdigest(),
        rows=rows,
        marker_readings=tuple(MarkerReading(**r) for r in markers["readings"]),
        marker_profile_id=markers["profile_id"],
        marker_data_sha256=hashlib.sha256(marker_raw).hexdigest(),
    )
