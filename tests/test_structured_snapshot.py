"""Verify bounded structured rendering and service snapshot round-tripping."""

from fatebridge.services.bazi import calculate_bazi_marriage, calculate_bazi_wealth
from fatebridge.services.compatibility import calculate_compatibility_analysis
from fatebridge.services.structured_snapshot import (
    render_structured_snapshot_text,
)
from fatebridge.utils.birth_input import PersonInfo


def _person(name: str, year: int) -> PersonInfo:
    return PersonInfo(
        name=name,
        birth_year=year,
        birth_month=5,
        birth_day=15,
        birth_hour=10,
        birth_minute=30,
        gender="男",
    )


def test_renderer_emits_sectioned_format_and_translates_scalars():
    text = render_structured_snapshot_text(
        {"score": 88, "has_storage": True, "notes": ["稳健"]}, title="测试"
    )
    assert "[概要]" in text
    assert "类型：测试" in text
    assert "评分：88" in text  # score -> 评分
    assert "是" in text  # bool -> 是/否
    assert "[说明]" in text  # notes -> 说明 section


def test_renderer_bounds_deep_and_long_structures():
    deep = {"a": {"b": {"c": {"d": {"e": {"f": 1}}}}}}
    assert "略" in render_structured_snapshot_text(deep, title="d")

    long_list = {"items": [{"i": n} for n in range(100)]}
    text = render_structured_snapshot_text(long_list, title="l")
    assert "共 100 条" in text
    # Capped well below the raw length.
    assert len(text.splitlines()) < 40


def test_bazi_dimension_services_emit_roundtripping_snapshot():
    for service in (calculate_bazi_marriage, calculate_bazi_wealth):
        result = service(_person("甲", 1990))
        assert "error" not in result
        assert result["snapshot_text"]
        assert result["snapshot_export"]["export_text"] == result["snapshot_text"]


def test_compatibility_service_emits_roundtripping_snapshot():
    result = calculate_compatibility_analysis(_person("甲", 1990), _person("乙", 1992))
    assert "error" not in result
    assert result["snapshot_text"]
    assert "[概要]" in result["snapshot_text"]
    assert result["snapshot_export"]["export_text"] == result["snapshot_text"]
