"""Bounded, named-edition evidence; never a replacement calculation table."""

from collections.abc import Mapping
from typing import NamedTuple


class EditionRow(NamedTuple):
    ju: int
    values: tuple[int | str, ...]
    literals: tuple[str, ...]
    image_numbers: tuple[int, ...]
    location: str


# Read from the provider's original JPEGs, including the split 大/武 in row 37.
# These three rows do not establish the genealogy or correctness of either book.
ROWS = (
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
IMAGE_SHA256 = {
    17: "dec593b89d9db04cfacfd1cb608bbbc10e0ec0b7a30aeb57c54c6494cc95bff9",
    18: "aec00d7e293da4d005735733d581f069051f25de347e24ef258820251fba582a",
    20: "036bfda5d9c30f5d87e0adba2134da19561070ff7499e9d28ce2ba0fa9468c62",
}
FIELDS = (
    "taiyi_number",
    "wenchang_palace",
    "shiji",
    "jishen",
    "main_count",
    "guest_count",
)


def edition_comparisons(
    yin: bool,
    ju: int,
    actual_values: Mapping[str, int | str],
    selected_values: Mapping[str, int | str],
    selected_literals: Mapping[str, str],
) -> list[dict[str, object]]:
    """Compare only the three collated yin rows, retaining the selected source."""
    row = next((r for r in ROWS if yin and r.ju == ju), None)
    if row is None:
        return []
    observations = [
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
        for field, value, literal in zip(FIELDS, row.values, row.literals)
    ]
    return [
        {
            "source_id": "wujing_yonezawa_wanli27_yin_v1",
            "source_title": "武經總要後集卷之二十",
            "classical_author": "宋 曾公亮、丁度等奉敕撰（馆方目录）",
            "provider": "市立米沢図書館",
            "catalog_identity": "米沢善本40 / AA040001 / 20冊",
            "catalog_url": "https://www.library.yonezawa.yamagata.jp/dg/AA040.html",
            "catalog_sha256": "bb7471ba20ee2c74437aa2199984b61543358fcbf30f394f6c1f3bc93c9d29b3",
            "edition": "万暦27年（1599）跋重刻本",
            "bibliographic_note": "馆方目录记载：据南宋绍定4年本的正统4年本重刻。此处不据目录推断两书文本谱系独立。",
            "chapter_image_url": "https://www.library.yonezawa.yamagata.jp/dg/data/AA040/019/AA040019_002.jpg",
            "chapter_image_sha256": "cbed0e7776aa63ba6ca2e808edeb6db77fd9464947d6733e9479929d794751fb",
            "images": [
                {
                    "book_number": 19,
                    "image_number": number,
                    "url": f"https://www.library.yonezawa.yamagata.jp/dg/data/AA040/019/AA040019_{number:03d}.jpg",
                    "sha256": IMAGE_SHA256[number],
                }
                for number in row.image_numbers
            ],
            "location": row.location,
            "yin_dun": True,
            "ju": ju,
            "observations": observations,
            "required_observations": 6,
            "matching_current_observations": sum(
                actual_values[field] == value
                for field, value in zip(FIELDS, row.values)
            ),
            "matching_selected_source_observations": sum(
                selected_values[field] == value
                for field, value in zip(FIELDS, row.values)
            ),
            "review_status": "ai_facsimile_reading_pending_expert_collation",
            "textual_lineage_independence_established": False,
            "whole_work_acceptance_passed": False,
            "scope": "仅阴37/43/44各四位置与两算的具名版本书影对照；AI校读，待专家复核。原《金镜》分歧保留，文本谱系独立性未证；不替换默认通则，不证明全144局、全书、古历或预测。",
        }
    ]
