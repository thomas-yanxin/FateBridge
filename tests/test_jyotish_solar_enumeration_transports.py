"""A formerly lost sunrise must reach real REST, native MCP and CLI callers."""

import pytest

from tests.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
def test_second_rise_in_one_ut1_date_on_three_real_surfaces(monkeypatch, capsys, key):
    payload = dict(
        birth_year=2026,
        birth_month=3,
        birth_day=24,
        birth_hour=0,
        birth_minute=10,
        birth_timezone="UTC",
        birth_latitude=30,
        birth_longitude=91,
        divisions=[],
        birth_time_uncertainty_minutes=0,
    )
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.strengths.kala_bala.solar_context",
            "india.strengths.kala_bala.components",
            "india.strengths.kala_bala.solar_events.enumeration",
            "india.rule_trace",
        ],
    )
    kala = result["india"]["strengths"]["kala_bala"]
    assert kala["solar_context"]["status"] == "bracketed"
    assert kala["solar_context"]["hora_number"] == 1
    assert kala["components"]["dina_bala"]["ruler"] == "Mars"
    assert kala["components"]["hora_bala"]["ruler"] == "Mars"
    assert kala["components"]["tribhaga_bala"]["ruler"] == "Mercury"
    assert kala["solar_events"]["enumeration"]["post_event_search_advance_seconds"] == 1
    assert any(
        r["rule_id"] == "jyotish.solar_event_enumeration.v1"
        for r in result["india"]["rule_trace"]
    )


def test_uncertainty_across_restored_sunrise_keeps_both_actual_day_lords(
    monkeypatch, capsys
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_india",
        dict(
            birth_year=2026,
            birth_month=3,
            birth_day=24,
            birth_hour=0,
            birth_minute=10,
            birth_timezone="UTC",
            birth_latitude=30,
            birth_longitude=91,
            divisions=[],
            birth_time_uncertainty_minutes=12,
        ),
        ["india.birth_time_sensitivity"],
    )
    sensitivity = result["india"]["birth_time_sensitivity"]
    assert sensitivity["status"] == "changes_detected"
    alternatives = sensitivity["time_lord_alternatives"]["dina_bala"]
    assert set(alternatives) == {"Moon", "Mars"}
