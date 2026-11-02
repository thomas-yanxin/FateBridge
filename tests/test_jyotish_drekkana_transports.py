import pytest

from tests.fixtures.surface_payloads import astro_payload
from tests.test_jyotish_transports import call_surfaces


@pytest.mark.parametrize("key", ["astro_india", "astro_vimshottari", "astro_chart"])
@pytest.mark.parametrize("sapta", ["santhanam_27", "raman_30"])
def test_independently_selected_drekkana_and_conflict_survive_real_surfaces(
    monkeypatch, capsys, key, sapta
):
    payload = {
        **astro_payload(),
        "saptavargaja_profile": sapta,
        "drekkana_profile": "raman_36",
        "divisions": [],
        "birth_time_uncertainty_minutes": 0,
    }
    if key == "astro_chart":
        payload["chart_variant"] = "india_chart"
    result = call_surfaces(
        monkeypatch,
        capsys,
        key,
        payload,
        [
            "india.profile.drekkana_profile",
            "india.strengths.sthana_bala",
            "india.birth_time_sensitivity.sthana_bala_sample_ranges",
            "india.topic_evidence",
            "india.rule_trace",
        ],
    )
    india = result["india"]
    strength = india["strengths"]["sthana_bala"]
    assert (
        india["profile"]["drekkana_profile"]
        == strength["profile"]["drekkana_profile"]["id"]
        == "raman_36"
    )
    assert strength["profile"]["id"] == sapta
    assert strength["source_reading_conflicts"][0]["summary_value_virupa"] == 60
    for planet, values in strength["summary"].items():
        assert (
            strength["drekkana_profile_comparison"]["raman_36"][planet]["total_virupa"]
            == values["total_virupa"]
        )
        assert india["birth_time_sensitivity"]["sthana_bala_sample_ranges"][planet][
            "total_virupa"
        ] == {"minimum": values["total_virupa"], "maximum": values["total_virupa"]}


def test_conflicting_primary_coefficient_supports_nested_strict_projection(
    monkeypatch, capsys
):
    result = call_surfaces(
        monkeypatch,
        capsys,
        "astro_india",
        {**astro_payload(), "drekkana_profile": "raman_36"},
        [
            "india.strengths.sthana_bala.profile.drekkana_profile.source_section",
            "india.strengths.sthana_bala.source_reading_conflicts",
            "india.strengths.sthana_bala.drekkana_profile_comparison.raman_36.Venus.total_virupa",
        ],
    )
    assert (
        result["india"]["strengths"]["sthana_bala"]["source_reading_conflicts"][0][
            "detailed_value_virupa"
        ]
        == 15
    )
