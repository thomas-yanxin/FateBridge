"""Separately identified Shoushi width witnesses, without repairing their sums.

The page prints no circle total. A comparison against a named Yuan Shi circle
does not establish the Lu Wei epoch or decide which source glyph to emend.
Half/tai arithmetic requires a declared quarter-mark policy.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.guolao_classical import MANSIONS
from fatebridge.core.guolao_coordinates import NLC166_MANSIONS
from fatebridge.core.guolao_passages import POLICIES, load_registry

DATA = Path(__file__).resolve().parents[1] / "data/guolao/luwei-shoushi-widths-v1.json"
SOURCES = {
    "tohoku": DATA,
    "nijl": DATA.with_name("nijl-shoushi-widths-v1.json"),
    "nlc3149": DATA.with_name("nlc3149-shoushi-widths-v1.json"),
}
QUARTER_POLICIES = ("uninterpreted_marks", "quarter_marks")
QUARTERS = {"少": Fraction(1, 4), "半": Fraction(1, 2), "太": Fraction(3, 4)}


def _integer(value: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("源字组件须为明确整数，不接收浮点、布尔或隐式古度")
    if not 0 <= value <= maximum:
        raise ValueError("源字组件超出本表范围，不能取模或进位修正")


def _policy(policy: str) -> None:
    if policy not in QUARTER_POLICIES:
        raise ValueError("须明确保留半太未释，或声明按四分制读少半太")


@dataclass(frozen=True)
class WidthReading:
    mansion: str
    normalized_text: str
    whole_degree: int | None
    minute: int | None
    quarter_mark: str | None

    def __post_init__(self) -> None:
        if self.mansion not in MANSIONS:
            raise ValueError("须保留28宿的明确宿名")
        if not isinstance(self.normalized_text, str) or not self.normalized_text:
            raise ValueError("须保留格内原字的规范转写")
        if self.whole_degree is not None:
            _integer(self.whole_degree, 40)
        if self.minute is not None:
            _integer(self.minute, 99)
        if self.quarter_mark is not None:
            if self.quarter_mark not in QUARTERS or self.whole_degree is None:
                raise ValueError("本行只记录明确的整度附少半太")
            if self.minute is not None:
                raise ValueError("本行不得混造分数与整度附半太")
        elif self.whole_degree is None and self.minute is None:
            raise ValueError("不得把空格变成零宿宽")

    def resolve(self, *, quarter_policy: str) -> dict[str, Any]:
        _policy(quarter_policy)
        unresolved = (
            self.quarter_mark is not None and quarter_policy == "uninterpreted_marks"
        )
        width = None
        if not unresolved:
            width = (
                Fraction(self.whole_degree or 0)
                + Fraction(self.minute or 0, 100)
                + QUARTERS.get(self.quarter_mark or "", Fraction(0))
            )
        return {
            "mansion": self.mansion,
            "normalized_text": self.normalized_text,
            "whole_degree": self.whole_degree,
            "minute": self.minute,
            "quarter_mark": self.quarter_mark,
            "whole_degree_unit_printed": self.whole_degree is not None,
            "minute_unit_printed": self.minute is not None,
            "quarter_policy": quarter_policy,
            "quarter_mark_interpreted": self.quarter_mark is not None
            and not unresolved,
            "literal_width_du_exact": str(width) if width is not None else None,
            "status": (
                "quarter_mark_uninterpreted"
                if unresolved
                else (
                    "declared_quarter_arithmetic"
                    if self.quarter_mark is not None
                    else "printed_unit_arithmetic"
                )
            ),
            "accepted_modern_width": False,
        }


@dataclass(frozen=True)
class WidthWitness:
    witness_id: str
    locator: str
    credit: str
    primary_kind: str
    primary_sha256: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(v, str) or not v.strip()
            for v in (self.witness_id, self.locator, self.credit)
        ):
            raise ValueError("须保留具名底本、定位与来源署名")
        if self.primary_kind not in ("jpeg", "pdf"):
            raise ValueError("须区分原始JPEG与跨页PDF，不能混称图片")
        if (
            not isinstance(self.primary_sha256, str)
            or len(self.primary_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.primary_sha256)
        ):
            raise ValueError("原始资料须有明确SHA-256指纹")


@dataclass(frozen=True)
class WidthRow:
    source_id: str
    source_url: str
    image_sha256: str | None
    data_sha256: str
    readings: tuple[WidthReading, ...]
    witness: WidthWitness

    def __post_init__(self) -> None:
        if not isinstance(self.witness, WidthWitness):
            raise TypeError("宿宽行须绑定冻结的具名底本")
        expected_image = (
            self.witness.primary_sha256 if self.witness.primary_kind == "jpeg" else None
        )
        if self.image_sha256 != expected_image:
            raise ValueError("图片指纹须对应原JPEG；原PDF指纹不能冒充图片指纹")
        object.__setattr__(self, "readings", tuple(self.readings))
        if any(not isinstance(r, WidthReading) for r in self.readings):
            raise TypeError("各格须为冻结的具名宿宽释读")
        if tuple(r.mansion for r in self.readings) != tuple(MANSIONS):
            raise ValueError("本行须按角至轸顺序恰有28格，不重排、补齐或混历")

    def audit(self, *, quarter_policy: str) -> dict[str, Any]:
        _policy(quarter_policy)
        entries = [r.resolve(quarter_policy=quarter_policy) for r in self.readings]
        values = [
            (
                Fraction(e["literal_width_du_exact"])
                if e["literal_width_du_exact"] is not None
                else None
            )
            for e in entries
        ]
        total = (
            sum((v for v in values if v is not None), Fraction(0))
            if None not in values
            else None
        )
        cumulative: Fraction | None = Fraction(0)
        reference_cumulative = Fraction(0)
        for entry, value, reference in zip(entries, values, NLC166_MANSIONS.widths_du):
            entry["comparison"] = {
                "reference_source_id": NLC166_MANSIONS.source_id,
                "reference_width_du_exact": str(reference),
                "literal_difference_du_exact": (
                    str(value - reference) if value is not None else None
                ),
                "cumulative_difference_before_this_mansion_du_exact": (
                    str(cumulative - reference_cumulative)
                    if cumulative is not None
                    else None
                ),
                "cumulative_origin": "both_literal_lists_start_at_角_zero_for_arithmetic_only",
                "reference_used_to_emend_source": False,
                "difference_interpreted_as_modern_error": False,
            }
            cumulative = (
                cumulative + value
                if cumulative is not None and value is not None
                else None
            )
            reference_cumulative += reference
        return {
            "source": {
                "source_id": self.source_id,
                "source_url": self.source_url,
                "image_sha256": self.image_sha256,
                "data_sha256": self.data_sha256,
                "locator": self.witness.locator,
                "witness_id": self.witness.witness_id,
                "credit": self.witness.credit,
                "primary_artifact": {
                    "kind": self.witness.primary_kind,
                    "sha256": self.witness.primary_sha256,
                },
                "calendar": "shoushi",
                "circle_total_printed_on_this_page": None,
            },
            "quarter_policy": quarter_policy,
            "entries": entries,
            "resolved_widths": sum(v is not None for v in values),
            "sum_of_resolved_widths_du_exact": str(
                sum((v for v in values if v is not None), Fraction(0))
            ),
            "all28_width_sum_du_exact": str(total) if total is not None else None,
            "named_reference_circle_du_exact": str(NLC166_MANSIONS.circle_du),
            "sum_minus_named_reference_circle_du_exact": (
                str(total - NLC166_MANSIONS.circle_du) if total is not None else None
            ),
            "matches_named_reference_circle": (
                total == NLC166_MANSIONS.circle_du if total is not None else None
            ),
            "source_circle_accepted": False,
            "normalized_to_reference_circle": False,
            "source_widths_emended": False,
            "complete_luwei_coordinate_profile_built": False,
            "modern_epoch_calibrated": False,
            "life_degree_accepted": False,
        }

    def audit_passages(
        self, *, quarter_policy: str, whole_degree_policy: str
    ) -> dict[str, Any]:
        if whole_degree_policy not in POLICIES:
            raise ValueError("过宫对照须另行声明整度承接政策")
        result = self.audit(quarter_policy=quarter_policy)
        widths = {r["mansion"]: r for r in result["entries"]}
        passages = load_registry()
        same_witness = self.witness.witness_id == "tohoku_ma591"
        entries = []
        for branch in "丑子亥戌酉申未午巳辰卯寅":
            entry = passages.entry(
                "shoushi", branch, whole_degree_policy=whole_degree_policy
            )
            width = widths[entry["mansion_from_column_heading"]]
            offset_text = entry["literal_unit_sum_du_exact"]
            width_text = width["literal_width_du_exact"]
            within = (
                0 <= Fraction(offset_text) < Fraction(width_text)
                if offset_text is not None and width_text is not None
                else None
            )
            entries.append(
                {
                    "passage": entry,
                    "width": width,
                    "printed_unit_sum_within_source_mansion": within,
                    "check_scope": (
                        "local_literal_offset_bounds_only_not_coordinate_acceptance"
                        if same_witness
                        else "cross_witness_literal_bounds_only_not_source_consistency"
                    ),
                }
            )
        result["passages"] = {
            "whole_degree_policy": whole_degree_policy,
            "same_witness": same_witness,
            "comparison_scope": (
                "same_witness_literal_bounds"
                if same_witness
                else "cross_witness_literal_bounds"
            ),
            "source": {
                "source_id": passages.source_id,
                "source_url": passages.source_url,
                "source_image_sha256": passages.source_image_sha256,
                "data_sha256": passages.data_sha256,
            },
            "entries": entries,
            "bounds_passed_is_not_full_profile_acceptance": True,
        }
        return result


def load_row(source: str = "tohoku") -> WidthRow:
    if source not in SOURCES:
        raise ValueError("须明确选择已登记的宿宽底本，不按周天吻合度自动择本")
    blob = SOURCES[source].read_bytes()
    data = json.loads(blob)
    if data["calendar"] != "shoushi" or data["printed_calendar_label"] != "授時":
        raise ValueError("本资料须为授时源行，不接受混历")
    return WidthRow(
        source_id=data["source_id"],
        source_url=data["source_url"],
        image_sha256=data["image_sha256"],
        data_sha256=hashlib.sha256(blob).hexdigest(),
        readings=tuple(WidthReading(**row) for row in data["readings"]),
        witness=(
            WidthWitness(
                witness_id="tohoku_ma591",
                locator="陆位辑校本第26幅，黄道宿度表授时行",
                credit=data["credit"],
                primary_kind="jpeg",
                primary_sha256=data["image_sha256"],
            )
            if source == "tohoku"
            else WidthWitness(**data["witness"])
        ),
    )
