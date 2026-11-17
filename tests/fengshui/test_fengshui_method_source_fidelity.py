"""Fixed author tables and scoped classical nouns, independent of permission."""

import json
from pathlib import Path

import pytest

from fatebridge.core.fengshui.method_details import method_details
from fatebridge.core.fengshui.snapshot import sections
from fatebridge.services.fengshui import assess, calculate_annual_stars
from tests.fengshui.test_fengshui_measured_workstation import measured_request

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/fengshui-method-authors-reference-v1.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize("star", REFERENCE["stars"], ids=lambda r: str(r["number"]))
def test_each_author_star_theme_element_and_symbol_route(star):
    references = method_details(["annual_stars"])
    actual = references["flying_star_references"][str(star["number"])]
    assert actual["element"] == star["element"]
    assert actual["symbolic_trigram"] == star["trigram"]
    assert actual["modern_teaching_theme"]["label"] == star["theme"]
    assert actual["modern_teaching_theme"]["source_ids"] == [
        "JOEY_YAP_2018_STAR_THEMES"
    ]
    assert "not_natal_combination_judgment" in actual["modern_teaching_theme"]["scope"]


@pytest.mark.parametrize(
    "year,direction,number",
    [
        (int(year), direction, number)
        for year, chart in REFERENCE["author_annual_charts"].items()
        for direction, number in chart.items()
    ],
)
def test_annual_numbers_equal_the_two_original_author_diagrams(year, direction, number):
    result = calculate_annual_stars(effective_year=year)
    assert (
        result["layers"]["annual_stars"]["palaces"][direction]["annual_star_number"]
        == number
    )


@pytest.mark.parametrize(
    "symbol", REFERENCE["classical_symbols"], ids=lambda r: r["trigram"]
)
def test_classical_families_and_object_nouns_keep_the_adopted_source_categories(symbol):
    actual = method_details()["cross_text_trigram_symbols"][symbol["trigram"]]
    assert actual["family_symbol"] == symbol["family"]
    assert actual["object_symbols"] == symbol["objects"]
    assert actual["family_symbol_scope"].endswith("not_actual_household_identity")


@pytest.mark.parametrize(
    "reference", REFERENCE["observation_references"], ids=lambda r: r["id"]
)
def test_modern_observation_prompts_are_retained_with_correct_classical_sources(
    reference,
):
    actual = next(
        r
        for r in method_details()["object_observation_references"]
        if r["reference_id"] == reference["id"]
    )
    assert actual["classical_objects"] == reference["classical_objects"]
    assert reference["required_classical_source"] in actual["source_ids"]
    assert (
        reference["retained_modern_candidate"]
        in actual["modern_observation_candidates"]
    )
    assert actual["classification"] == "requires_independent_confirmation"
    assert actual["prescription_status"] == "not_provided"


@pytest.mark.parametrize(
    "selection",
    [
        [],
        ["desktop_bagua_btb_v1"],
        ["wofs_desktop_compass_v1"],
        ["desktop_bagua_btb_v1", "wofs_desktop_compass_v1"],
    ],
)
def test_workstation_reference_snapshot_does_not_deny_explicit_measured_rules(
    selection,
):
    request = measured_request()
    scene = request["workstation_layout"]["scene"]
    scene["desktops"][0]["ruleset_ids"] = selection
    scene["bodies"].append(
        dict(
            object_id="floor_barrier",
            kind="plant",
            footprint=dict(
                center=dict(x=2, y=-1), width_m=0.2, depth_m=0.2, rotation_degrees=0
            ),
            bottom_m=0,
            top_m=1,
            blocks_view=False,
        )
    )
    result = assess(**request)
    layout = result["layout_analysis"]
    assert (
        layout["workstation_analysis"]["non_btb_desktop_reference"][
            "placement_rules_enabled"
        ]
        is False
    )
    active = [
        r
        for r in layout["workstation_layout_analysis"]["rule_comparisons"]
        if r["rule_id"].startswith("wofs_desktop_compass_v1.")
    ]
    assert bool(active) is ("wofs_desktop_compass_v1" in selection)
    if active:
        lines = [line for _, part in sections(result) for line in part]
        assert not any("WOFS" in line and "未启用摆放规则" in line for line in lines)
