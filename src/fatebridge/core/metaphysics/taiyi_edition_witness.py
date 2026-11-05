"""Bounded, named-edition evidence; never a replacement calculation table."""

from collections.abc import Mapping
from typing import NamedTuple

FIELDS = (
    "taiyi_number",
    "wenchang_palace",
    "shiji",
    "jishen",
    "main_count",
    "guest_count",
)


class EditionRow(NamedTuple):
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

IMAGE_SHA256 = {
    31: "607fd0d481f334108858b1b7261c1b68cc47012111ebaef2e3bf69b426535cff",
    21: "2ed9dcaeeec3545c7d4ac9cb7f87d7b52d950de19d345aebc3302cb46c2d90eb",
    13: "e8954151e2f0fbd6352d4012cd877e29dfbba3ffe9e46a89da27ac7b369496de",
    12: "3875052e23e1b30398ce99f5cc4385cfa3c1432fabb2ad9dcc286c74b262d768",
    8: "1ea2a88e5fde5a4309662143c46e743b12efcfbc76434b36c6485dbea8aa3d06",
    7: "88f05501e1346b32e1ed631bf8bba1f065e43a4e7eb061d39605e3ae9216098a",
    17: "dec593b89d9db04cfacfd1cb608bbbc10e0ec0b7a30aeb57c54c6494cc95bff9",
    18: "aec00d7e293da4d005735733d581f069051f25de347e24ef258820251fba582a",
    20: "036bfda5d9c30f5d87e0adba2134da19561070ff7499e9d28ce2ba0fa9468c62",
}


YANG_IMAGE_SHA256 = {
    28: "2b976b625aa303a1825ae2f93cf915823ae78c1529d84534dd88f97d30ecf0de",
    45: "32779ea6d1492da00984f2f372e00d7b07192f8c37f90a4c52c5a1ebc9c36454",
    50: "cc11d5080f4720417984c3698d1feb935f7e246c782f861a362bf1e977aae483",
}


def edition_comparisons(
    yin: bool,
    ju: int,
    actual_values: Mapping[str, int | str],
    selected_values: Mapping[str, int | str],
    selected_literals: Mapping[str, str],
) -> list[dict[str, object]]:
    """Compare collated fields only; never fill unread fields from the engine."""
    row = next((r for r in ROWS if r.yin == yin and r.ju == ju), None)
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
            "catalog_url": "https://www.library.yonezawa.yamagata.jp/dg/AA040.html",
            "catalog_sha256": "bb7471ba20ee2c74437aa2199984b61543358fcbf30f394f6c1f3bc93c9d29b3",
            "edition": "万暦27年（1599）跋重刻本",
            "bibliographic_note": "馆方目录记载：据南宋绍定4年本的正统4年本重刻。此处不据目录推断两书文本谱系独立。",
            "chapter_image_url": (
                "https://www.library.yonezawa.yamagata.jp/dg/data/AA040/019/AA040019_002.jpg"
                if yin
                else "https://www.library.yonezawa.yamagata.jp/dg/data/AA040/018/AA040018_028.jpg"
            ),
            "chapter_image_sha256": (
                "cbed0e7776aa63ba6ca2e808edeb6db77fd9464947d6733e9479929d794751fb"
                if yin
                else YANG_IMAGE_SHA256[28]
            ),
            "images": [
                {
                    "book_number": row.book_number,
                    "image_number": number,
                    "url": f"https://www.library.yonezawa.yamagata.jp/dg/data/AA040/{row.book_number:03d}/AA040{row.book_number:03d}_{number:03d}.jpg",
                    "sha256": (
                        IMAGE_SHA256[number] if yin else YANG_IMAGE_SHA256[number]
                    ),
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
