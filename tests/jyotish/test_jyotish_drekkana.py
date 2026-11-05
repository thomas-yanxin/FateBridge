"""Independent source selection, primary numerical tables and full oracle sums."""

import hashlib
import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.jyotish import GRAHAS, build_india, positions
from fatebridge.core.jyotish_sthana import COMPONENTS, calculate_sthana, drekkana
from fatebridge.core.requests.astrology import AstroChartPolyRequest, AstroIndiaRequest
from tests.fixtures.surface_payloads import astro_payload

FIXTURES = Path(__file__).parents[1] / "fixtures"
PRIMARY = json.loads((FIXTURES / "jyotish-drekkana-classical.json").read_text())
ORACLE = json.loads((FIXTURES / "jyotish-sthana-reference.json").read_text())


@pytest.mark.parametrize("profile", PRIMARY["sources"])
@pytest.mark.parametrize("planet", GRAHAS[:7])
@pytest.mark.parametrize("decanate", [1, 2, 3])
def test_all_source_categories_against_frozen_primary_tables(profile, planet, decanate):
    primary = PRIMARY["sources"][profile]
    key = ["first", "second", "third"][decanate - 1]
    actual = drekkana(decanate * 10 - 5, planet, profile)
    assert actual["value"] == (primary["value_virupa"] if planet in primary[key] else 0)
    assert actual["D1_decanate"] == decanate
    assert actual["source_section"] == primary["section"]


@pytest.mark.parametrize("sign", range(12))
def test_exact_d1_ten_degree_sides_are_not_transformed_d3_or_rounded(sign):
    for edge in [10, 20]:
        value = float(sign * 30 + edge)
        for longitude in [
            math.nextafter(value, -math.inf),
            value,
            math.nextafter(value, math.inf),
        ]:
            expected = edge // 10 if longitude < value else edge // 10 + 1
            for profile in PRIMARY["sources"]:
                for planet in GRAHAS[:7]:
                    assert (
                        drekkana(longitude, planet, profile)["D1_decanate"] == expected
                    )
    for profile in PRIMARY["sources"]:
        assert drekkana(sign * 30.0, "Sun", profile)["D1_decanate"] == 1
        assert drekkana(sign * 30.0 + 360, "Sun", profile)["D1_decanate"] == 1


def test_raman_primary_worked_example_and_conflicting_summary_are_both_retained():
    original = json.loads((FIXTURES / "jyotish-sthana-classical.json").read_text())[
        "raman_example9"
    ]
    raw = {
        "ascendant": 298.45,
        "longitudes": {
            p: d + m / 60 + s / 3600
            for p, (d, m, s) in original["longitudes_dms"].items()
        },
    }
    actual = calculate_sthana(raw, "raman_30", "raman_36")
    for planet, row in PRIMARY["sources"]["raman_36"]["standard_horoscope"].items():
        assert actual["summary"][planet]["drekkana_bala"] == row["value"]
        assert actual["evidence"][planet]["drekkana"]["D1_decanate"] == row["decanate"]
    conflict = actual["source_reading_conflicts"][0]
    assert (
        conflict["detailed_value_virupa"]
        == PRIMARY["conflicts"][0]["detailed_value"]
        == 15
    )
    assert (
        conflict["summary_value_virupa"]
        == PRIMARY["conflicts"][0]["summary_value"]
        == 60
    )
    assert (
        conflict["applies_to_selected_profile"]
        and not conflict["whole_book_acceptance"]
    )
    assert actual["shadbala_status"] == "not_complete"


@pytest.mark.parametrize("case", ORACLE["examples"])
def test_raman_aligned_all_five_components_and_complete_sum_against_pinned_oracle(
    case, monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    year, month, day = case["date"]
    hour, minute, second = case["time"]
    birth = build_astro_birth_info(
        birth_year=year,
        birth_month=month,
        birth_day=day,
        birth_hour=hour,
        birth_minute=minute,
        birth_second=second,
        birth_longitude=case["longitude"],
        birth_latitude=case["latitude"],
        birth_timezone=str(case["timezone_offset"]),
    )
    result = build_india(
        birth,
        divisions=[],
        node_mode=case["node_mode"],
        saptavargaja_profile="raman_30",
        drekkana_profile="raman_36",
    )
    assert result["profile"]["ephemeris_models"] == ["moshier"]
    for planet, expected in case["strength"].items():
        actual = result["strengths"]["sthana_bala"]["summary"][planet]
        for component in COMPONENTS:
            assert actual[component] == pytest.approx(
                expected[component], abs=0.0051, rel=0
            ), (planet, component)
        assert actual["total_virupa"] == pytest.approx(
            expected["total_virupa"], abs=0.0101, rel=0
        )
        assert actual["total_virupa"] == sum(actual[c] for c in COMPONENTS)


def test_profile_comparisons_hold_the_other_component_fixed():
    raw = {"ascendant": 0.0, "longitudes": dict.fromkeys(GRAHAS, 15.0)}
    for sapta in ["santhanam_27", "raman_30"]:
        old = calculate_sthana(raw, sapta)
        new = calculate_sthana(raw, sapta, "raman_36")
        for planet in GRAHAS[:7]:
            for component in COMPONENTS:
                if component != "drekkana_bala":
                    assert (
                        old["summary"][planet][component]
                        == new["summary"][planet][component]
                    )
            assert (
                new["drekkana_profile_comparison"]["santhanam_27_6"][planet][
                    "total_virupa"
                ]
                == old["summary"][planet]["total_virupa"]
            )
            for other in ["santhanam_27", "raman_30"]:
                selected = calculate_sthana(raw, other, "raman_36")["summary"][planet]
                assert new["profile_comparison"][other][planet][
                    "total_virupa"
                ] == pytest.approx(selected["total_virupa"], abs=1e-12, rel=0)


def test_every_sensitivity_point_uses_the_selected_component_not_the_default():
    from datetime import timedelta

    birth = build_astro_birth_info(**astro_payload())
    result = build_india(
        birth,
        divisions=[],
        birth_time_uncertainty_minutes=1,
        drekkana_profile="raman_36",
    )
    samples = [
        calculate_sthana(
            positions(birth, birth.utc_datetime + timedelta(seconds=s)),
            "santhanam_27",
            "raman_36",
        )
        for s in [-60, -30, 0, 30, 60]
    ]
    for planet in GRAHAS[:7]:
        for component in result["strengths"]["sthana_bala"]["summary"][planet]:
            values = [s["summary"][planet][component] for s in samples]
            assert result["birth_time_sensitivity"]["sthana_bala_sample_ranges"][
                planet
            ][component] == {"minimum": min(values), "maximum": max(values)}
    for topic in result["topic_evidence"].values():
        for factor in topic["factors"]:
            if factor["rule_id"] == "jyotish.sthana_bala.v1":
                assert "raman_36" in factor["traditional_interpretation"]
                assert (
                    factor["fact"]
                    == result["strengths"]["sthana_bala"]["summary"][
                        factor["fact_path"].rsplit(".", 1)[1]
                    ]
                )


def test_downstream_war_uses_the_selected_total_and_retains_its_source():
    from fatebridge.core.jyotish_war import war_bala
    from tests.jyotish.test_jyotish_war import inputs

    longitudes, components, _, dig = inputs()
    longitudes.update(Mars=15.0, Mercury=15.25)
    outputs = {}
    for profile in ["santhanam_27_6", "raman_36"]:
        sthana = calculate_sthana(
            {"ascendant": 0.0, "longitudes": longitudes}, "raman_30", profile
        )
        result = war_bala(
            longitudes,
            components,
            {"fixed": components["paksha_bala"]["summary"]},
            sthana,
            dig,
        )
        assert result["upstream_profile"]["sthana"]["drekkana_profile"]["id"] == profile
        for planet in ["Mars", "Mercury"]:
            assert (
                result["evidence"]["fixed"]["prewar_basis"][planet]["inputs"][
                    "sthana_bala"
                ]
                == sthana["summary"][planet]["total_virupa"]
            )
        outputs[profile] = result
    a, b = [
        outputs[p]["evidence"]["fixed"]["prewar_basis"]["Mercury"]["total_virupa"]
        for p in ["santhanam_27_6", "raman_36"]
    ]
    assert b - a == 15
    assert (
        outputs["santhanam_27_6"]["summary"]["Mars"]
        != outputs["raman_36"]["summary"]["Mars"]
    )


@pytest.mark.parametrize("profile", ["unknown", "raman_60", "santhanam_27"])
def test_unknown_or_unimplemented_summary_profiles_are_rejected(profile):
    with pytest.raises(ValidationError):
        AstroIndiaRequest.model_validate(
            {**astro_payload(), "drekkana_profile": profile}
        )
    with pytest.raises(ValueError, match="drekkana_profile"):
        calculate_sthana({"longitudes": {}}, drekkana_profile=profile)


@pytest.mark.parametrize("variant", ["chart", "germany", "chart13", "guolao_chart"])
def test_custom_drekkana_cannot_be_silently_discarded_on_non_indian_charts(variant):
    with pytest.raises(ValidationError, match="drekkana_profile"):
        AstroChartPolyRequest.model_validate(
            {
                **astro_payload(),
                "chart_variant": variant,
                "drekkana_profile": "raman_36",
            }
        )


def test_existing_oracle_reference_is_the_original_frozen_file():
    # No answers are regenerated to accommodate the newly selectable reading.
    assert ORACLE["provenance"]["version"] == "4.8.7"
    assert (
        hashlib.sha256(
            (FIXTURES / "jyotish-sthana-reference.json").read_bytes()
        ).hexdigest()
        == "e8d3e1872b488aebd6579410d49576d5c04277465ba39a9a12c2f515706f79ea"
    )
