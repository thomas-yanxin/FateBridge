"""Source conditions and current program observations remain separate."""

from pathlib import Path

import pytest

from fatebridge.core.bazi.bazi_evidence import (
    build_natal_evidence,
    build_topic_evidence,
)
from fatebridge.services.knowledge import calculate_knowledge_read

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {
    "education": [
        "印星主学历",
        "官印相生",
        "食伤主才华",
        "文昌贵人",
        "财破印",
        "伤官见官",
    ],
    "children": ["子女星", "子女宫", "时柱十神看子女", "生育时机"],
    "relatives": ["六亲取象", "六亲宫位", "比劫论手足"],
    "shensha": ["文昌"],
}
PARTIAL = {
    "education/文昌贵人",
    "shensha/文昌",
    "children/子女星",
    "relatives/六亲取象",
}
CASES = [(c, k) for c, keys in TARGETS.items() for k in keys]


@pytest.mark.parametrize("category,key", CASES)
def test_each_public_entry_attributes_only_its_declared_statements(
    category, key
) -> None:
    result = calculate_knowledge_read(domain="bazi", category=category, key=key)
    entry = result["provenance"]["entry_curation"]
    assert (
        entry["validation_status"]
        == "topic_source_semantics_not_global_force_or_real_prediction"
    )
    assert entry["source_attribution_status"] == (
        "partial_still_pending"
        if f"{category}/{key}" in PARTIAL
        else "selected_source_conditions_collated"
    )
    indices = sum(
        [
            entry[k]
            for k in (
                "source_tip_indices",
                "implementation_tip_indices",
                "editorial_tip_indices",
                "source_pending_tip_indices",
            )
        ],
        [],
    )
    assert sorted(indices) == list(range(len(result["tips"])))
    assert bool(entry["source_pending_tip_indices"]) == (f"{category}/{key}" in PARTIAL)
    assert "非逐字引文" in result["citation"]
    for source in entry["source_refs"]:
        assert source["source_pdf_pages"]
    for implementation in entry["implementation_refs"]:
        assert (ROOT / implementation["source_path"]).is_file()
    assert entry["independent_expert_review"] == "not_completed"
    assert entry["reality_prediction_efficacy"] == "not_tested"


def test_wenchang_cards_match_each_other_and_the_day_only_counterexample() -> None:
    first = calculate_knowledge_read(
        domain="bazi", category="education", key="文昌贵人"
    )
    duplicate = calculate_knowledge_read(domain="bazi", category="shensha", key="文昌")
    assert first["tips"] == duplicate["tips"]
    # All four pairs satisfy stem/branch parity and the month/hour formula.
    # A year-stem lookup would hit 巳, while actual 辛-day lookup has no 子.
    pillars = {
        "year": ("甲", "午"),
        "month": ("己", "巳"),
        "day": ("辛", "酉"),
        "hour": ("戊", "戌"),
    }
    result = build_topic_evidence(
        build_natal_evidence(pillars), pillars, "education", None, None, None
    )["markers"][0]
    assert result["target_branch"] == "子"
    assert result["natal_positions"] == []
    assert (
        "只按日干" in first["rendered_text"]
        and "不同时按年干另算" in first["rendered_text"]
    )
    assert "待校勘" in first["rendered_text"]


def test_repeated_wenchang_positions_are_retained_without_exam_prediction() -> None:
    pillars = {
        "year": ("甲", "子"),
        "month": ("丙", "子"),
        "day": ("辛", "酉"),
        "hour": ("戊", "子"),
    }
    result = build_topic_evidence(
        build_natal_evidence(pillars), pillars, "education", None, None, None
    )["markers"][0]
    assert result["natal_positions"] == ["year", "month", "hour"]


@pytest.mark.parametrize(
    "gender,expected",
    [("男", {"辛", "庚"}), ("女", {"丁"}), (None, {"辛", "庚", "丁"})],
)
def test_actual_child_counts_gender_basis_and_missing_timing_match_card(
    gender: str | None, expected
) -> None:
    pillars = {
        "year": ("辛", "酉"),
        "month": ("丁", "酉"),
        "day": ("甲", "午"),
        "hour": ("壬", "申"),
    }
    natal = build_natal_evidence(pillars)
    result = build_topic_evidence(natal, pillars, "children", gender, None, None)
    assert {
        row["stem"] for rows in result["stars"].values() for row in rows
    } == expected
    assert result["palaces"]["hour"]["pillar"] == "壬申"
    assert result["first_view"]["timing"] == []
    relatives = build_topic_evidence(natal, pillars, "relatives", gender, None, None)
    assert {row["pillar"] for row in relatives["stars"]["偏财"]} == {"hour"}
    assert relatives["stars"]["正印"] == []


def test_current_child_timing_is_a_supplied_relation_not_a_fertility_window() -> None:
    pillars = {
        "year": ("辛", "酉"),
        "month": ("丁", "酉"),
        "day": ("甲", "午"),
        "hour": ("壬", "申"),
    }
    result = build_topic_evidence(
        build_natal_evidence(pillars), pillars, "children", "男", None, ("辛", "巳")
    )
    layer = result["first_view"]["timing"][0]
    assert layer["pillar"] == "辛巳"
    assert "正官" in layer["topic_stars"]
    assert layer["palace_relation_count"] >= 1
    card = calculate_knowledge_read(domain="bazi", category="children", key="生育时机")
    assert "明干与藏干子女星" in card["rendered_text"]


def test_source_palace_order_is_disclosed_separately_from_current_module() -> None:
    card = calculate_knowledge_read(domain="bazi", category="relatives", key="六亲宫位")
    assert "年、月、日、时分别配祖、父、妻、子" in card["rendered_text"]
    assert "范围不等于上述原典宫分" in card["rendered_text"]
    assert card["provenance"]["entry_curation"]["source_refs"][0][
        "source_pdf_pages"
    ] == [52, 53, 54, 55]
