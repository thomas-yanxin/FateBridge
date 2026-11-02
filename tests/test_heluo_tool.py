"""Historical port regression tests for heluo (河洛理数).

Two parity goldens, both produced by horosa's own `heluoLocal.js` / `runHeluo`:

- ``heluo_judge_snapshot.txt`` — fixed pillars 甲子/丁卯/庚申/庚辰 (阳男·辰时) +
  an explicit 清明 化工, so it pins the 节气-*independent* algorithm
  (起命/元堂/爻辞/大限) **and** the 命运篇 judge logic, with no ephemeris in play.
- ``heluo_e2e_snapshot.txt`` — horosa's full `runHeluo` for 2000-05-15 09:33 (a
  节气-safe date). It is retained as migration evidence, with explicit changes
  for corrected Najia matching and overconfident labels. Independent scanned
  fixtures, rather than historical port parity, establish the rule checks.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fatebridge.core.heluo import (
    build_snapshot_text,
    calculate,
    da_yun,
    judge,
    solar_term_huagong,
)
from fatebridge.services.divination import calculate_heluo_analysis
from tests.heluo_guan_shi_revision_reference import (
    SNAPSHOT_SOURCE,
    rebind_r84_snapshot_source_lines,
)

_FIX = Path(__file__).resolve().parent / "fixtures"

_CASE1 = {"year": "甲子", "month": "丁卯", "day": "庚申", "hour": "庚辰"}
READING_DELIVERY = json.loads(
    (
        _FIX / "heluo_reading_delivery_v1/historical-snapshot-migration-final.json"
    ).read_bytes()
)


def _r90_reading_notes(text: str) -> str:
    """Advance only the exact historical Guan1 paragraph, preserving its body."""
    heading = READING_DELIVERY["specific_heading"]
    if heading not in text:
        return text
    assert text.count(heading) == 1
    prefix, tail = text.split(heading, 1)
    block, separator, suffix = tail.partition("\n\n[")
    assert heading + block == READING_DELIVERY["before_block"]
    return prefix + READING_DELIVERY["after_block"] + separator + suffix


def _classical_corrections(historical: str) -> str:
    # Keep the upstream fixture intact. Both historical examples falsely match
    # a lower-trigram assignment when that trigram is actually outside. The
    # independent scanned lists and counterexamples live in test_heluo_najia_depth.
    text = historical.replace("　葉\n", "　基础命中有（综合葉否未定）\n").replace(
        "二数：", "二数（仅对25/30比较，非四时旺衰定论）："
    )
    text = text.replace("(过)", "(有余)")
    for mapped in ("震", "坤"):
        text = text.replace(
            f"得势有　得时无　得体 {mapped}(有)",
            f"年命纳甲无（按实际六爻含乾坤借用）　月表匹配无　日干映射 {mapped}(有)（得时、得体综合未定）",
        )
    text = text.replace("　顺气\n", "　用爻与所用阴阳令同类（非综合顺逆时）\n")
    # Preserve the legacy opposite-polarity fact, without presenting it as the
    # source's asymmetric yin-Yuantang/yang-response support clause.
    text = text.replace(
        "　有应　", "　先天元堂与应爻阴阳相异（非十体有援总判）　"
    ).replace("　无应　", "　先天元堂与应爻阴阳相同（非十体有援总判）　")
    # The original Dangwei note concerns birth-month polarity. The inherited
    # boolean only compares line-index parity; preserve its fact under that
    # explicit label while the source month definition remains unresolved.
    text = text.replace("元堂：不当位", "元堂：位序阴阳未匹配").replace(
        "（非综合顺逆时）", "（非原典当位或综合顺逆时）"
    )
    text = text.replace("\n天元气 ", "\n先后天合并：天元气 ").replace(
        "\n化工 ", "\n合并化工 "
    )
    # These two historical cases use uncollated commentaries; source labels now
    # precede their text. The original historical text fixtures stay intact.
    text = text.replace(
        "\n摘要：",
        "\n校勘：摘要注文及诗歌尚未逐字核对，诗歌来源待核；条件分支未自动选取。\n注文：",
    ).replace("\n诗歌：", "\n诗歌（继承文本，来源待核）：")
    return _r90_reading_notes(rebind_r84_snapshot_source_lines(text))


def test_heluo_documented_anchors():
    """heluoLocal.js:3-4 算例：甲子…→天風姤/上九；丁巳…→水風井。"""
    c1 = calculate(
        four_pillars=_CASE1, gender="男", hour_zhi="辰", birth_year=1924, month_zhi="卯"
    )
    assert c1["xian"]["name"] == "天風姤"
    assert c1["xian"]["yuan"] == 6  # 上九

    c2 = calculate(
        four_pillars={"year": "丁巳", "month": "丙午", "day": "壬寅", "hour": "辛丑"},
        gender="男",
        hour_zhi="丑",
        birth_year=1917,
        month_zhi="午",
    )
    assert c2["xian"]["name"] == "水風井"


def test_heluo_judge_historical_snapshot_with_explicit_label_corrections():
    """Preserve the historical result except independently documented corrections."""
    chart = calculate(
        four_pillars=_CASE1, gender="男", hour_zhi="辰", birth_year=1924, month_zhi="卯"
    )
    hg = solar_term_huagong("清明", False)
    jg = judge(chart, _CASE1, "卯", hg)
    dy = da_yun(chart["xian"], chart["hou"], 1924)
    expected = (
        (_FIX / "heluo_judge_snapshot.txt").read_text(encoding="utf-8").rstrip("\n")
    )
    assert jg["deSheng"] is False
    actual = build_snapshot_text(chart, jg, dy)
    # Round 31 added this exact, separately tested evidence block before the
    # seasonal block. Preserve the historical fixture and verify the addition.
    source_block = (
        "\n\n[年命纳甲与来源]\n"
        "先天·天風姤：出生年甲子未命中本阶段六爻正纳／借用。\n"
        "后天·風澤中孚：出生年甲子未命中本阶段六爻正纳／借用。"
    )
    assert actual.split("\n\n[二数与时令·原典条件]")[0] == (
        _classical_corrections(expected) + source_block
    )
    assert "缺出生瞬间，未评估时令条件" in actual


def test_heluo_end_to_end_historical_snapshot_with_explicit_label_corrections():
    """Keep unrelated historical output stable while exposing corrected facts."""
    result = calculate_heluo_analysis(
        date="2000-05-15", time="09:33:00", zone="+08:00", gender="男", lon="121e28"
    )
    expected = (
        (_FIX / "heluo_e2e_snapshot.txt").read_text(encoding="utf-8").rstrip("\n")
    )
    assert (
        hashlib.sha256((_FIX / "heluo_e2e_snapshot.txt").read_bytes()).hexdigest()
        == SNAPSHOT_SOURCE["historical_fixture_sha256"]
    )
    assert result["judge"]["deSheng"] is False
    source_block = (
        "\n\n[年命纳甲与来源]\n"
        "先天·雷風恆：出生年庚辰未命中本阶段六爻正纳／借用。\n"
        "后天·風地觀：出生年庚辰未命中本阶段六爻正纳／借用。"
    )
    assert result["snapshot_text"].split("\n\n[二数与时令·原典条件]")[0] == (
        _classical_corrections(expected) + source_block
    )
    assert result["judge"]["seasonal_numbers"]["seasonal_status"] == "evaluated"


def test_heluo_service_shape():
    result = calculate_heluo_analysis(
        date="2000-05-15", time="09:33:00", zone="+08:00", gender="男", lon="121e28"
    )
    assert result["analysis_type"] == "河洛理数"
    assert result["chart"]["xian"]["name"] and result["chart"]["hou"]["name"]
    assert len(result["dayun"]["all"]) == 12  # 先天 6 段 + 后天 6 段
    assert result["solar_term"]["term"] == "立夏"
    assert result["snapshot_text"].startswith("[起命]")
    assert set(result["four_pillars"]) == {"year", "month", "day", "hour"}


def test_heluo_zhizun_bian_er_bu_yi():
    """三至尊卦(坎為水/水雷屯/水山蹇) 九五阴令/上六阳令『变而不易』特例覆盖。"""
    from fatebridge.core.heluo import transform_houtian

    lines = [0, 1, 0, 0, 1, 0]  # 坎為水
    # 上六(yuan=6) + 阳令 → 变而不易：只翻爻、不互换上下卦、元堂位不动。
    hou = transform_houtian("坎為水", lines, 6, True)
    assert hou["yuan"] == 6
    assert hou["lines"] == [0, 1, 0, 0, 1, 1]
