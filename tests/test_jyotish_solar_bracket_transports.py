import pytest

from tests.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
@pytest.mark.parametrize(
    "month,day,latitude,lord", [(2, 23, 80, "Moon"), (8, 27, -80, "Jupiter")]
)
def test_first_polar_day_components_survive_three_real_surfaces(
    monkeypatch, capsys, key, month, day, latitude, lord
):
    data = dict(
        birth_year=2026,
        birth_month=month,
        birth_day=day,
        birth_hour=12,
        birth_timezone="UTC",
        birth_latitude=latitude,
        birth_longitude=0,
        divisions=[],
        birth_time_uncertainty_minutes=0,
    )
    if key == "astro_chart":
        data["chart_variant"] = "india_chart"
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        data,
        [
            "india.strengths.kala_bala.solar_context",
            "india.strengths.kala_bala.components",
            "india.birth_time_sensitivity.solar_bracket_states_on_grid",
            "india.topic_evidence",
            "india.rule_trace",
        ],
    )
    kala = result["india"]["strengths"]["kala_bala"]
    assert (
        kala["solar_context"]["sunrise_day_status"]
        == kala["solar_context"]["active_arc_status"]
        == "bracketed"
    )
    assert (
        kala["components"]["dina_bala"]["ruler"]
        == kala["components"]["hora_bala"]["ruler"]
        == lord
    )
    assert kala["components"]["tribhaga_bala"]["ruler"] == "Sun"
    assert result["india"]["birth_time_sensitivity"][
        "solar_bracket_states_on_grid"
    ] == [
        {
            "sunrise_day_status": "bracketed",
            "active_arc_status": "bracketed",
            "sample_count": 1,
        }
    ]


def test_component_dependency_statuses_support_nested_strict_projection(
    monkeypatch, capsys
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_india",
        dict(
            birth_year=2026,
            birth_month=6,
            birth_day=21,
            birth_hour=12,
            birth_timezone="UTC",
            birth_latitude=80,
            birth_longitude=0,
            divisions=[],
        ),
        [
            "india.strengths.kala_bala.solar_context.sunrise_day_status",
            "india.strengths.kala_bala.solar_context.active_arc_status",
            "india.strengths.kala_bala.components.tribhaga_bala.summary.Jupiter",
        ],
    )
    kala = result["india"]["strengths"]["kala_bala"]
    assert kala["solar_context"] == {
        "sunrise_day_status": "not_bracketed",
        "active_arc_status": "not_bracketed",
    }
    assert kala["components"]["tribhaga_bala"]["summary"]["Jupiter"] == 60
