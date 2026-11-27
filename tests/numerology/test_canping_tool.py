"""Canping arithmetic, source selection, rendering and service checks."""

from __future__ import annotations

from fatebridge.core.numerology.canping import (
    calculate,
    compute_number,
    lookup_record,
    nayin_element,
)
from fatebridge.services.divination import calculate_canping_analysis
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.utils.data import get_nayin

# horosa NAYIN_PAIRS (canpingLocal.js:18-29): (ganzhi_a, ganzhi_b, element).
_HOROSA_NAYIN_PAIRS = [
    ("甲子", "乙丑", "金"),
    ("丙寅", "丁卯", "火"),
    ("戊辰", "己巳", "木"),
    ("庚午", "辛未", "土"),
    ("壬申", "癸酉", "金"),
    ("甲戌", "乙亥", "火"),
    ("丙子", "丁丑", "水"),
    ("戊寅", "己卯", "土"),
    ("庚辰", "辛巳", "金"),
    ("壬午", "癸未", "木"),
    ("甲申", "乙酉", "水"),
    ("丙戌", "丁亥", "土"),
    ("戊子", "己丑", "火"),
    ("庚寅", "辛卯", "木"),
    ("壬辰", "癸巳", "水"),
    ("甲午", "乙未", "金"),
    ("丙申", "丁酉", "火"),
    ("戊戌", "己亥", "木"),
    ("庚子", "辛丑", "土"),
    ("壬寅", "癸卯", "金"),
    ("甲辰", "乙巳", "火"),
    ("丙午", "丁未", "水"),
    ("戊申", "己酉", "土"),
    ("庚戌", "辛亥", "金"),
    ("壬子", "癸丑", "木"),
    ("甲寅", "乙卯", "水"),
    ("丙辰", "丁巳", "土"),
    ("戊午", "己未", "火"),
    ("庚申", "辛酉", "木"),
    ("壬戌", "癸亥", "水"),
]


def test_canping_nayin_parity_with_fb_get_nayin() -> None:
    """FB get_nayin element must match horosa's NAYIN_ELEMENT for all 60 ganzhi."""
    for a, b, element in _HOROSA_NAYIN_PAIRS:
        for ganzhi in (a, b):
            assert nayin_element(ganzhi) == element
            assert get_nayin(ganzhi[0], ganzhi[1])[-1] == element


def test_canping_compute_number_documented_anchor() -> None:
    """本命 巳/午/火 → 2242/3242, the algorithm's own documented test case."""
    result = compute_number("巳", "午", "火")
    assert result["numShun"] == 2242
    assert result["numNi"] == 3242


def test_canping_fixed_pillars_keep_numbers_columns_and_readings() -> None:
    result = calculate(
        year_gz="庚午",
        month_branch="寅",
        day_branch="巳",
        hour_branch="午",
        gender="男",
        method="ming",
        qiyun_age=3,
        liunian_branch="戌",
        active_dayun_branch="申",
    )
    assert (result["element"], result["dayPalaceBranch"], result["mingGong"]) == (
        "土",
        "亥",
        "申",
    )
    # Earth adds 55 to 2000 and the two 子-origin counts, plus 100 per
    # directional count. The inclusive 亥-to-午 counts are 8 and 6.
    natal = result["benming"]
    assert (natal["numShun"], natal["numNi"]) == (2874, 2674)
    # Luck substitutes each successive branch for the hour. Volume 6's
    # same-branch example counts a full turn plus the starting position.
    expected_luck = [
        (3, 12, "申", 3076, 2476),
        (13, 22, "酉", 3177, 2377),
        (23, 32, "戌", 3278, 2278),
        (33, 42, "亥", 3379, 3379),
        (43, 52, "子", 2268, 3268),
        (53, 62, "丑", 2369, 3169),
        (63, 72, "寅", 2470, 3070),
        (73, 82, "卯", 2571, 2971),
        (83, 92, "辰", 2672, 2872),
    ]
    annual = result["liunian"]
    assert (annual["taisuiBranch"], annual["dayunBranch"]) == ("戌", "申")
    assert (annual["numShun"], annual["numNi"]) == (3175, 2375)

    assert natal["verses"]["textShun"] == ""
    assert (
        natal["verses"]["selectionShun"]["cell_status"] == "row_absent_in_local_corpus"
    )
    assert natal["verses"]["selectionNi"]["column"] == "upper_male"
    assert natal["verses"]["selectionNi"]["source_pdf_page"] == 103
    assert "witnesses" not in natal["verses"]["selectionNi"]
    luck = result["dayun"]
    # National Archives of Japan, 305-0271, volume 6. The Earth luck cells
    # are identified by their number and PDF page. Three forward rows are absent locally.
    earth_luck: dict[int, tuple[int | None, str]] = {
        3076: (None, ""),
        3177: (None, ""),
        3278: (None, ""),
        3268: (98, "笙歌頻聒聒，自可樂歡顏。"),
        3169: (99, "猛虎依平林，收威并失勢。"),
        3070: (100, "春天喜勝遊，冬日真可愛。"),
        2971: (101, "琴瑟不調和，其弦急可整。"),
        2872: (102, "黃鶯聲百囀，其可樂春遲。"),
        2268: (102, "荒田多野草，空自負耕犁。"),
        2369: (102, "葉落為辭樹，正不為幹枝。"),
        2470: (102, "柏樹長高崗，喬枝須出群。"),
        2571: (102, "良晝惟歸去，志存楊柳間。"),
        2672: (102, "二將競爭功，一得須一失。"),
        2476: (104, "酩酊見衝盃，性真正自在。"),
        2377: (104, "石上磨玉簪，不測中有折。"),
        2278: (104, "遊舟入水中，進退不由己。"),
        3379: (104, "塞翁須失馬，反禍又成福。"),
    }
    for step, expected in zip(luck, expected_luck, strict=True):
        assert (
            step["ageStart"],
            step["ageEnd"],
            step["branch"],
            step["numShun"],
            step["numNi"],
        ) == expected
        start, end, branch, forward, reverse = expected
        verses = step["verses"]
        for direction, number in (("Shun", forward), ("Ni", reverse)):
            page, text = earth_luck[number]
            selection = verses[f"selection{direction}"]
            assert selection["kind"] == "luck"
            assert selection.get("source_pdf_page") == page
            assert verses[f"text{direction}"] == text


def test_canping_service_full_shape() -> None:
    result = calculate_canping_analysis(
        date="1990-06-15",
        time="09:33:00",
        timezone="+08:00",
        gender="男",
        method="ming",
        longitude="121e28",  # Fictional test coordinate, now supplied explicitly.
    )
    assert result["analysis_type"] == "邵子参评数 / 金锁银匙"
    assert result["element"] in {"金", "木", "水", "火", "土"}
    assert (
        result["ming_gong"] is None
    )  # Named month-pillar schedule does not use a fabricated Minggong.
    assert result["canping_timing"]["profile_id"] == "bazi_appendix_v1"
    assert set(result["four_pillars"]) == {"year", "month", "day", "hour"}
    # Full 120 sexagenary-year labels, with actual date segments.
    assert len(result["liunian_series"]["rows"]) == 120
    assert result["liunian_series"]["year_boundary"] == "lichun"


def test_canping_gu_method_uses_day_branch() -> None:
    ming = calculate(
        year_gz="庚午",
        month_branch="寅",
        day_branch="巳",
        hour_branch="午",
        method="ming",
    )
    gu = calculate(
        year_gz="庚午",
        month_branch="寅",
        day_branch="巳",
        hour_branch="午",
        method="gu",
    )
    # 古法日宫支 = 八字日支; 明法用月支反向 (寅→亥), so the two diverge.
    assert gu["dayPalaceBranch"] == "巳"
    assert ming["dayPalaceBranch"] == "亥"


def test_canping_lookup_and_knowledge_read_omit_witnesses() -> None:
    record = lookup_record("水", 2231, "male")
    assert record["text"] == "月在清波底，維舟向柳邊。"
    assert "witnesses" not in record["selection"]
    knowledge = calculate_knowledge_read(domain="canping", key="水.2231.male")
    assert knowledge["key"] == "水.2231.male"
    assert "月在清波底" in knowledge["rendered_text"]
