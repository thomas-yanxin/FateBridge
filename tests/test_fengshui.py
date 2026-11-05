"""Sources, complete relationship oracle, observations and calendar boundaries."""

import json
from datetime import timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.fengshui.bazhai import minggua, sectors
from fatebridge.core.fengshui.calendar import lichun
from fatebridge.core.fengshui.directions import bearing_context, provenance, rule_data
from fatebridge.core.fengshui.models import (
    AnnualRequest,
    AssessRequest,
    BazhaiRequest,
    DirectionsRequest,
    JinsuoRequest,
    MingguaRequest,
)
from fatebridge.core.fengshui.output import FengshuiOutput
from fatebridge.services.fengshui import (
    assess,
    calculate_annual_stars,
    calculate_bazhai,
    calculate_directions,
    calculate_jinsuo,
    calculate_minggua,
)
from tests.fixtures.fengshui import payload

REFERENCE = json.loads(
    (Path(__file__).parent / "data" / "fengshui-reference.json").read_text()
)


def test_independent_minggua_400_and_direction_table_64():
    assert REFERENCE["commit"] == "2666304c5cb4ac13091c8c1fcdd4e40c218b275a"
    assert len(REFERENCE["minggua_numbers"]) == 200
    for year, male, female in REFERENCE["minggua_numbers"]:
        for convention, expected in [("male", male), ("female", female)]:
            actual = minggua(
                MingguaRequest(effective_birth_year=year, gender_convention=convention)
            )
            assert actual["candidates"][0]["palace_number"] == expected, (
                year,
                convention,
            )
    for base, expected in REFERENCE["bazhai_table"].items():
        actual = sectors(base, "test", "test")
        assert {
            direction: p["star"]["name"] for direction, p in actual.items()
        } == expected


@pytest.mark.parametrize(
    "year,male,female",
    [
        (1864, 1, 5),
        (1924, 4, 2),
        (1984, 7, 8),
        (2044, 1, 5),
        (1990, 1, 5),
        (2000, 9, 6),
        (2100, 8, 7),
    ],
)
def test_epoch_and_century_raw_numbers(year, male, female):
    for convention, raw in [("male", male), ("female", female)]:
        candidate = calculate_minggua(
            effective_birth_year=year, gender_convention=convention
        )["layers"]["minggua"]["candidates"][0]
        assert candidate["raw_number"] == raw
        assert candidate["palace_number"] == (
            (2 if convention == "male" else 8) if raw == 5 else raw
        )


def test_raw_five_is_mapped_after_not_during_year_cycle():
    a = calculate_minggua(effective_birth_year=1864, gender_convention="female")
    b = calculate_minggua(effective_birth_year=1865, gender_convention="female")
    assert a["layers"]["minggua"]["candidates"][0]["palace_number"] == 8
    assert b["layers"]["minggua"]["candidates"][0]["palace_number"] == 6


def test_unknown_convention_is_two_candidates_and_missing_birth_is_partial():
    result = calculate_minggua(effective_birth_year=1990)
    assert result["status"] == "partial"
    assert [c["trigram"] for c in result["layers"]["minggua"]["candidates"]] == [
        "坎",
        "艮",
    ]
    assert calculate_minggua()["layers"]["minggua"]["candidates"] == []
    assert calculate_annual_stars()["status"] == "partial"


@pytest.mark.parametrize("boundary,expected", [("lichun", 2025), ("january_1", 2026)])
def test_birth_year_boundary_is_explicit(boundary, expected):
    result = calculate_minggua(
        birth_at="2026-01-15T12:00:00+08:00",
        gender_convention="male",
        year_boundary=boundary,
    )
    assert result["layers"]["minggua"]["time_context"]["effective_year"] == expected


def test_lichun_before_at_after_and_timezone_equivalence(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    boundary = lichun(2026, "Asia/Shanghai")
    moments = [
        (boundary - timedelta(seconds=1), 2025),
        (boundary, 2026),
        (boundary + timedelta(seconds=1), 2026),
        (boundary.astimezone(timezone.utc), 2026),
    ]
    for moment, expected in moments:
        annual = calculate_annual_stars(query_at=moment)["layers"]["annual_stars"]
        personal = calculate_minggua(birth_at=moment, gender_convention="male")[
            "layers"
        ]["minggua"]
        # Keep every original one-second/exact/UTC case. The packaged model's
        # five-second candidate policy requires uncertainty here; this is not
        # the separate one-second TT implementation acceptance threshold.
        for context in (annual["time_context"], personal["time_context"]):
            assert context["effective_year"] is None
            assert context["effective_year_status"] == "requires_confirmation"
            assert context["candidate_effective_years"] == [2025, 2026]
            assert context["provisional_effective_year"] == expected
            assert context["boundary_resolution"]["operational_guard_seconds"] == 5
        assert annual["palaces"] == {}
    for seconds, expected in ((-6, 2025), (6, 2026)):
        moment = boundary + timedelta(seconds=seconds)
        annual = calculate_annual_stars(query_at=moment)["layers"]["annual_stars"]
        personal = calculate_minggua(birth_at=moment, gender_convention="male")[
            "layers"
        ]["minggua"]
        assert (
            annual["effective_year"]
            == personal["time_context"]["effective_year"]
            == expected
        )
    same = calculate_annual_stars(
        query_at=boundary.astimezone(timezone.utc), timezone_name="UTC"
    )
    assert same["layers"]["annual_stars"]["time_context"]["effective_year"] is None
    outside = calculate_annual_stars(
        query_at=(boundary + timedelta(seconds=6)).astimezone(timezone.utc),
        timezone_name="UTC",
    )
    assert outside["layers"]["annual_stars"]["time_context"]["valid_from"].endswith(
        "+00:00"
    )


def test_published_2026_annual_chart_and_period_wrap():
    actual = calculate_annual_stars(effective_year=2026)["layers"]["annual_stars"]
    # Joey Yap official TG26 booklet, printed p67. Literal external chart.
    assert {d: p["annual_star_number"] for d, p in actual["palaces"].items()} == {
        "SE": 9,
        "S": 5,
        "SW": 7,
        "E": 8,
        "C": 1,
        "W": 3,
        "NE": 4,
        "N": 6,
        "NW": 2,
    }
    assert actual["palaces"]["N"]["palace_number"] == 1
    assert actual["palaces"]["N"]["annual_star"]["element"] == "金"
    assert actual["center_star_number"] == 1
    assert actual["current_period"]["number"] == 9
    assert (
        calculate_annual_stars(effective_year=2044)["layers"]["annual_stars"][
            "current_period"
        ]["number"]
        == 1
    )
    assert (
        calculate_annual_stars(effective_year=2023)["layers"]["annual_stars"][
            "current_period"
        ]["number"]
        == 8
    )
    assert (
        calculate_annual_stars(effective_year=2027)["layers"]["annual_stars"][
            "center_star_number"
        ]
        == 9
    )


@pytest.mark.parametrize(
    "angle,direction,mountain",
    [
        (0, "N", "子"),
        (360, "N", "子"),
        (7.499, "N", "子"),
        (7.5, "N", "癸"),
        (22.499, "N", "癸"),
        (22.5, "NE", "丑"),
        (67.5, "E", "甲"),
        (337.5, "N", "壬"),
        (352.5, "N", "子"),
    ],
)
def test_half_open_compass_and_mountain_boundaries(angle, direction, mountain):
    context = bearing_context(angle, "magnetic")
    assert (context["direction"], context["mountain"]) == (direction, mountain)
    assert context["north_reference"] == "magnetic"
    assert bearing_context(angle, "true")["north_reference"] == "true"


def test_house_uses_sitting_opposite_facing_and_keeps_each_resident():
    result = calculate_bazhai(**payload("bazhai"))["layers"]["bazhai"]
    assert result["house"]["sitting_trigram"] == "坎"
    assert result["house"]["sectors"]["S"]["star"]["name"] == "延年"
    assert [o["candidates"][0]["trigram"] for o in result["occupants"]] == ["坎", "艮"]
    assert (
        result["occupants"][0]["candidates"][0]["sectors"]["N"]["star"]["name"]
        == "伏位"
    )
    assert (
        result["occupants"][1]["candidates"][0]["sectors"]["N"]["star"]["name"]
        == "五鬼"
    )
    reverse = calculate_bazhai(
        house={"facing_degrees": 0, "north_reference": "magnetic"}
    )
    assert reverse["layers"]["bazhai"]["house"]["sitting_trigram"] == "离"


def test_stove_location_and_fire_mouth_are_separate_and_opposite_preferences():
    findings = calculate_bazhai(**payload("bazhai"))["layers"]["bazhai"][
        "placement_findings"
    ]
    personal = [
        f
        for f in findings
        if f["object_id"] == "stove" and f["subject_kind"] == "occupant"
    ]
    assert len(personal) == 2
    seat, mouth = personal
    assert seat["direction"] == "NE" and seat["star"]["name"] == "五鬼"
    assert seat["expected_polarity"] == "inauspicious" and seat["matches_convention"]
    assert mouth["direction"] == "S" and mouth["facing_role"] == "fire_mouth"
    assert mouth["expected_polarity"] == "auspicious" and mouth["matches_convention"]
    assert all(
        f["subject_id"] != "b" for f in findings if f["subject_kind"] == "occupant"
    )


def test_jinsuo_all_eight_preferences_unknown_mixed_and_no_object_inference():
    prefs = calculate_jinsuo()["layers"]["jinsuo"]["preferences"]
    assert {d: p["preferred_classification"] for d, p in prefs.items()} == {
        "N": "sand",
        "NE": "water",
        "E": "sand",
        "SE": "sand",
        "S": "water",
        "SW": "sand",
        "W": "water",
        "NW": "water",
    }
    features = [
        dict(
            object_id=d,
            direction=d,
            classification=p["preferred_classification"],
            classification_basis="user_confirmed",
            evidence="已确认",
        )
        for d, p in prefs.items()
    ]
    assert calculate_jinsuo(features=features)["status"] == "complete"
    assert all(
        f["finding"] == "matches_preference"
        for f in calculate_jinsuo(features=features)["layers"]["jinsuo"][
            "feature_findings"
        ]
    )
    for classification in ["mixed", "unknown", "water"]:
        feature = {**features[0], "classification": classification, "label": "镜子"}
        result = calculate_jinsuo(features=[feature])
        assert result["layers"]["jinsuo"]["feature_findings"][0]["finding"] == (
            "undetermined" if classification != "water" else "opposes_preference"
        )
        assert result["status"] == (
            "partial" if classification != "water" else "complete"
        )


def test_three_method_output_preserves_scopes_sources_and_differences():
    result = assess(**payload("assess"))
    FengshuiOutput.model_validate(result)
    assert result["status"] == "complete"
    assert set(result["layers"]) == {"bazhai", "jinsuo", "annual_stars"}
    assert "score" not in result
    south = next(
        c
        for c in result["conflicts"]
        if c["kind"] == "distinct_scope_overlay" and c["direction"] == "S"
    )
    assert south["bazhai_house_star"]["name"] == "延年"
    assert south["jinsuo_preference"] == "water" and south["annual_star_number"] == 5
    assert any(
        c["kind"] == "personal_direction_difference" and c["direction"] == "N"
        for c in result["conflicts"]
    )
    assert "xuankong_natal" in result["coverage"]["not_requested_layers"]
    for name, layer in result["layers"].items():
        ruleset = layer["ruleset"]
        assert (
            ruleset["version"]
            == {"bazhai": "1.1.0", "jinsuo": "1.0.0", "annual_stars": "1.0.0"}[name]
        )
        assert ruleset["source_ids"] == [s["source_id"] for s in ruleset["sources"]]
        assert all(
            s["url"].startswith("https://") and s["scope"] for s in ruleset["sources"]
        )


def test_missing_inputs_are_layer_specific_and_unselected_layers_not_computed():
    result = assess(methods=["bazhai", "jinsuo", "annual_stars"], effective_year=2026)
    assert result["status"] == "partial"
    assert result["layers"]["annual_stars"]["status"] == "complete"
    assert "confirmed_environment_features" in result["coverage"]["missing_inputs"]
    selected = assess(methods=["annual_stars"], effective_year=2026)
    assert selected["status"] == "complete"
    assert set(selected["layers"]) == {"annual_stars"}
    assert selected["coverage"]["not_requested_layers"] == [
        "bazhai",
        "jinsuo",
        "monthly_stars",
        "xuankong_natal",
    ]
    unknown = payload("bazhai")
    unknown["occupants"][1].pop("gender_convention")
    result = calculate_bazhai(**unknown)
    assert not any(
        c["kind"] == "personal_direction_difference" for c in result["conflicts"]
    )


@pytest.mark.parametrize(
    "model,inputs",
    [
        (DirectionsRequest, {"bearing_degrees": -1, "north_reference": "true"}),
        (DirectionsRequest, {"bearing_degrees": 361, "north_reference": "true"}),
        (
            DirectionsRequest,
            {"bearing_degrees": float("nan"), "north_reference": "true"},
        ),
        (DirectionsRequest, {"bearing_degrees": 10}),
        (
            BazhaiRequest,
            {
                "house": {
                    "sitting_trigram": "乾",
                    "facing_degrees": 180,
                    "north_reference": "true",
                }
            },
        ),
        (MingguaRequest, {"gender_convention": "unknown"}),
        (MingguaRequest, {"birth_at": "2026-01-01T00:00:00"}),
        (
            MingguaRequest,
            {"effective_birth_year": 2026, "birth_at": "2026-01-01T00:00:00+08:00"},
        ),
        (MingguaRequest, {"ruleset_id": "future_v2"}),
        (AnnualRequest, {"effective_year": 2026, "query_at": "2026-01-01T00:00:00Z"}),
        (AnnualRequest, {"timezone_name": "invalid/zone"}),
        (AnnualRequest, {"query_at": "1799-01-01T00:00:00Z"}),
        (
            JinsuoRequest,
            {
                "features": [
                    {
                        "object_id": "x",
                        "direction": "C",
                        "classification": "water",
                        "classification_basis": "measured",
                        "evidence": "x",
                    }
                ]
            },
        ),
        (
            JinsuoRequest,
            {
                "features": [
                    {"object_id": "x", "direction": "N", "classification": "water"}
                ]
            },
        ),
        (BazhaiRequest, {"occupants": [{"subject_id": "x"}, {"subject_id": "x"}]}),
        (
            BazhaiRequest,
            {
                "placements": [
                    {
                        "object_id": "x",
                        "purpose": "bed",
                        "location_direction": "N",
                        "subject_id": "missing",
                    }
                ]
            },
        ),
        (
            BazhaiRequest,
            {
                "placements": [
                    {
                        "object_id": "x",
                        "purpose": "stove",
                        "location_direction": "N",
                        "facing_direction": "S",
                        "facing_role": "headboard",
                    }
                ]
            },
        ),
        (AssessRequest, {"methods": ["bazhai", "bazhai"]}),
        (AssessRequest, {"methods": ["unsupported_method"]}),
        (AssessRequest, {"features": [payload("jinsuo")["features"][0]] * 2}),
        (AssessRequest, {"floorplan_image": "cannot_infer"}),
    ],
)
def test_invalid_inputs_never_silently_default(model, inputs):
    with pytest.raises(ValidationError):
        model.model_validate(inputs)


def test_rule_registry_is_not_mutable_through_response():
    copy = provenance("jinsuo_basic_fixed_v1")
    copy["sources"][0]["scope"] = "changed"
    copy["conventions"].clear()
    assert provenance("jinsuo_basic_fixed_v1")["sources"][0]["scope"] != "changed"
    copy = calculate_directions()
    copy["layers"]["directions"]["directions"]["N"]["palace_number"] = 99
    assert rule_data("directions")["N"]["palace_number"] == 1


def test_layered_snapshot_export_preserves_actual_facts_and_sources():
    result = assess(**payload("assess"))
    exported = result["snapshot_export"]
    assert not exported["missing_selected_sections"]
    assert not exported["unknown_detected_sections"]
    assert "S 固定宫数9 年星5 五黄廉贞" in exported["export_text"]
    assert "宅盘 S 延年" in exported["export_text"]
    assert "住户a male" in exported["export_text"]
    assert "住户b female" in exported["export_text"]
    assert "jinsuo_basic_fixed_v1@1.0.0" in exported["export_text"]
    assert "https://" in exported["export_text"]
