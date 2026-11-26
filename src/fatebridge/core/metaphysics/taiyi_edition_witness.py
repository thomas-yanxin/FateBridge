"""Compare selected Taiyi fields with named print-edition readings."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypedDict

FIELDS = (
    "taiyi_number",
    "wenchang_palace",
    "shiji",
    "jishen",
    "main_count",
    "guest_count",
)


@dataclass(frozen=True, slots=True)
class EditionRow:
    ju: int
    values: tuple[int | str, ...]
    literals: tuple[str, ...]
    image_numbers: tuple[int, ...]
    location: str
    fields: tuple[str, ...] = FIELDS
    yin: bool = True
    book_number: int = 19


# Read from the provider's original JPEGs, including the split 大/武 in row 37.
# These three rows do not establish the genealogy or correctness of either book.
ROWS: tuple[EditionRow, ...] = (
    EditionRow(
        37,
        (4, "寅", "坤", "申", 1, 25),
        ("四宮", "呂申", "大武", "申", "一", "二十五"),
        (17, 18),
        "冊19圖17左頁下第三十七局；始擊將大／武跨圖18右頁首行，客算二十五。",
    ),
    EditionRow(
        43,
        (2, "午", "巳", "寅", 2, 1),
        ("二宮", "大威", "大神", "寅", "二", "一"),
        (20,),
        "冊19圖20右頁第四十三局；始擊將大／神跨列，客算一。",
    ),
    EditionRow(
        44,
        (2, "未", "坤", "丑", 39, 38),
        ("二宮", "天道", "大武", "丑", "三十九", "三十八"),
        (20,),
        "冊19圖20左頁第四十四局；始擊將大武，客算三十八。",
    ),
)

# Targeted follow-up of all 11 original count conflicts, not a new blind cohort.
# Rows 43/44 above already cover the other two. Unread fields stay absent.
ROWS += (
    EditionRow(
        39,
        (35,),
        ("三十五",),
        (45,),
        "冊18圖45第39局main_count: 三十五。",
        ("main_count",),
        False,
        18,
    ),
    EditionRow(
        50,
        (16,),
        ("十六",),
        (50,),
        "冊18圖50第50局main_count: 十六。",
        ("main_count",),
        False,
        18,
    ),
    EditionRow(
        11,
        (26,),
        ("二十六",),
        (7,),
        "冊19圖7第11局guest_count: 二十六。",
        ("guest_count",),
        True,
        19,
    ),
    EditionRow(
        15,
        (25,),
        ("二十五",),
        (8,),
        "冊19圖8第15局guest_count: 二十五。",
        ("guest_count",),
        True,
        19,
    ),
    EditionRow(
        25,
        (31,),
        ("三十一",),
        (12,),
        "冊19圖12第25局main_count: 三十一。",
        ("main_count",),
        True,
        19,
    ),
    EditionRow(
        26,
        (30,),
        ("三十",),
        (13,),
        "冊19圖13第26局main_count: 三十。",
        ("main_count",),
        True,
        19,
    ),
    EditionRow(
        27,
        (29,),
        ("二十九",),
        (13,),
        "冊19圖13第27局main_count: 二十九。",
        ("main_count",),
        True,
        19,
    ),
    EditionRow(
        46,
        (1,),
        ("一",),
        (21,),
        "冊19圖21第46局guest_count: 一。",
        ("guest_count",),
        True,
        19,
    ),
    EditionRow(
        70,
        (32,),
        ("三十二",),
        (31,),
        "冊19圖31第70局main_count: 三十二。",
        ("main_count",),
        True,
        19,
    ),
)


class EditionImage(TypedDict):
    book_number: int
    image_number: int


class EditionObservation(TypedDict):
    field: str
    actual_value: int | str
    selected_source_value: int | str
    selected_source_literal: str
    edition_value: int | str
    edition_literal: str
    matches_current: bool
    matches_selected_source: bool


class EditionComparison(TypedDict):
    source_id: str
    source_title: str
    classical_author: str
    provider: str
    catalog_identity: str
    edition: str
    bibliographic_note: str
    location: str
    review_status: str
    count_conflict_status: str
    scope: str
    images: list[EditionImage]
    observations: list[EditionObservation]
    unread_fields: list[str]
    ju: int
    required_observations: int
    matching_current_observations: int
    matching_selected_source_observations: int
    yin_dun: bool
    textual_lineage_independence_established: bool
    whole_work_acceptance_passed: bool


def edition_comparisons(
    yin: bool,
    ju: int,
    actual_values: Mapping[str, int | str],
    selected_values: Mapping[str, int | str],
    selected_literals: Mapping[str, str],
) -> list[EditionComparison]:
    """Compare collated fields only; never fill unread fields from the engine."""
    row = next((r for r in ROWS if r.yin == yin and r.ju == ju), None)
    if row is None:
        return []
    observations: list[EditionObservation] = [
        {
            "field": field,
            "actual_value": actual_values[field],
            "selected_source_value": selected_values[field],
            "selected_source_literal": selected_literals[field],
            "edition_value": value,
            "edition_literal": literal,
            "matches_current": actual_values[field] == value,
            "matches_selected_source": selected_values[field] == value,
        }
        for field, value, literal in zip(row.fields, row.values, row.literals)
    ]
    return [
        {
            "source_id": (
                "wujing_yonezawa_wanli27_yin_v1"
                if yin
                else "wujing_yonezawa_wanli27_yang_counts_v1"
            ),
            "source_title": "武經總要後集卷之二十" if yin else "武經總要後集卷之十九",
            "classical_author": "宋 曾公亮、丁度等奉敕撰（馆方目录）",
            "provider": "市立米沢図書館",
            "catalog_identity": "米沢善本40 / AA040001 / 20冊",
            "edition": "万暦27年（1599）跋重刻本",
            "bibliographic_note": "馆方目录记载：据南宋绍定4年本的正统4年本重刻。此处不据目录推断两书文本谱系独立。",
            "images": [
                {
                    "book_number": row.book_number,
                    "image_number": number,
                }
                for number in row.image_numbers
            ],
            "location": row.location,
            "yin_dun": yin,
            "ju": ju,
            "observations": observations,
            "required_observations": len(row.fields),
            "matching_current_observations": sum(
                actual_values[field] == value
                for field, value in zip(row.fields, row.values)
            ),
            "matching_selected_source_observations": sum(
                selected_values[field] == value
                for field, value in zip(row.fields, row.values)
            ),
            "review_status": "ai_facsimile_reading_pending_expert_collation",
            "textual_lineage_independence_established": False,
            "whole_work_acceptance_passed": False,
            "unread_fields": [field for field in FIELDS if field not in row.fields],
            "count_conflict_status": "printed_edition_variant_observed_pending_expert_collation",
            "scope": "仅所列字段的具名版本书影对照；原11个两算冲突全部定向复核，非盲测新队列。AI校读，待专家复核。原《金镜》分歧保留，文本谱系独立性未证；不填未读字段、不替换默认通则，不证明全144局、全书、古历或预测。",
        }
    ]
