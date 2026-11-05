"""The expanded reference library must preserve its source and method boundaries."""

from copy import deepcopy
from datetime import date

import pytest

from fatebridge.core.fengshui.directions import rule_data
from fatebridge.core.fengshui.method_details import (
    method_details,
    method_reference_provenance,
)
from fatebridge.core.fengshui.output import Ruleset
from fatebridge.services.fengshui import assess


def walk_records(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk_records(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_records(item)


def test_all_reference_sources_have_inspectable_version_and_locator():
    details = method_details()
    provenance = method_reference_provenance()
    Ruleset.model_validate(provenance)
    sources = {source["source_id"]: source for source in provenance["sources"]}
    assert set(provenance["source_ids"]) == set(sources)
    for source in sources.values():
        assert all(
            source[key]
            for key in (
                "title",
                "kind",
                "scope",
                "source_version",
                "locator",
                "retrieved_at",
            )
        )
        date.fromisoformat(source["retrieved_at"])
        assert source["url"] or source["kind"] in {
            "user_supplied_expert_requirements",
            "authored_observation_reference",
        }
    for record in walk_records(details):
        if "source_ids" in record:
            assert set(record["source_ids"]) <= set(sources)
    assert sources["MEIHUA_TRIGRAM_SYMBOLS"]["kind"].startswith("cross_text_")
    assert "oldid=2690596" in sources["MEIHUA_TRIGRAM_SYMBOLS"]["url"]
    assert sources["JOEY_YAP_2018_STAR_THEMES"]["kind"].startswith(
        "author_published_modern_"
    )
    assert "二十山" in sources["CHEN_YIFENG_FORM_COMMENTARY"]["title"]


def test_actual_arriving_star_routes_independently_of_fixed_direction():
    result = assess(scene="home", methods=["annual_stars"], effective_year=2026)
    details = result["method_details"]
    north = result["layers"]["annual_stars"]["palaces"]["N"]
    arriving = details["flying_star_references"][str(north["annual_star_number"])]
    assert details["palaces"]["N"]["fixed_palace_element"] == "水"
    assert details["palaces"]["N"]["fixed_palace_trigram"] == "坎"
    assert arriving["number"] == 6 and arriving["element"] == "金"
    assert arriving["symbolic_trigram"] == "乾"
    assert arriving["reference_frame"] == "arriving_flying_star"
    assert arriving["symbolic_person_and_object_reference"]["family_symbol"] == "父"
    assert "not_actual_occupant" in arriving["symbol_scope"]
    # A six at north is not permission to relabel the household's north as father.
    assert "family_role" not in arriving
    assert result["status"] == "complete"
    assert list(result["layers"]) == ["annual_stars"]


def test_nine_star_entries_cover_symbols_without_inventing_a_ninth_family_role():
    details = method_details()
    stars = details["flying_star_references"]
    assert set(stars) == {str(i) for i in range(1, 10)}
    for number, star in stars.items():
        assert star["name"] == rule_data("annual_stars")[number]["name"]
        assert star["element"] == rule_data("annual_stars")[number]["element"]
        assert star["modern_teaching_theme"]["scope"].endswith(
            "not_natal_combination_judgment"
        )
        if number != "5":
            symbols = star["symbolic_person_and_object_reference"]
            assert symbols["object_symbols"]
            assert symbols["family_symbol_scope"].endswith(
                "not_actual_household_identity"
            )
    assert stars["5"]["symbolic_trigram"] is None
    assert stars["5"]["symbolic_person_and_object_reference"] is None
    assert stars["5"]["profession_reference"]["examples"] == []
    assert details["palaces"]["C"]["cross_text_symbol_reference"] is None


def test_classical_roles_and_modern_profession_examples_keep_distinct_sources():
    details = method_details()
    symbols = details["cross_text_trigram_symbols"]
    assert "舟人" in symbols["坎"]["ancient_role_symbols"]
    assert "农夫" in symbols["坤"]["ancient_role_symbols"]
    assert "文人" in symbols["离"]["ancient_role_symbols"]
    assert "译人" in symbols["兑"]["ancient_role_symbols"]
    assert all(
        symbol["occupation_scope"] == "ancient_role_nouns_not_modern_job_suitability"
        for symbol in symbols.values()
    )
    stars = details["flying_star_references"]
    assert stars["4"]["profession_reference"]["examples"] == [
        "学术人员",
        "研究人员",
        "写作者",
    ]
    assert stars["4"]["profession_reference"]["source_ids"] == [
        "JOEY_YAP_2009_REFERENCE"
    ]
    conditioned = stars["3"]["profession_reference"]
    assert conditioned["status"] == "conditioned_example_only"
    assert conditioned["conditions"] == {
        "example_year": 2009,
        "example_sector": "NE",
        "natal_pair": [4, 6],
        "annual_star": 3,
    }
    assert "universal_star_3_profession_mapping" in conditioned["not_inferred"]
    # An author theme is not a missing profession list to fill by analogy.
    for number in ["1", "2", "5", "6", "7", "8", "9"]:
        assert stars[number]["profession_reference"]["status"] == "not_covered"
        assert stars[number]["profession_reference"]["examples"] == []
    assert "meihua_preheaven_numbers" in symbols["坎"]["not_imported"]


def test_bazhai_shared_star_names_do_not_reuse_flying_star_elements():
    details = method_details(["bazhai"])
    assert list(details["methods"]) == ["bazhai"]
    assert details["bazhai_you_nian_references"]["生气"]["element"] == "木"
    assert details["flying_star_references"]["1"]["element"] == "水"
    assert details["bazhai_you_nian_references"]["六煞"]["element"] == "水"
    assert details["flying_star_references"]["4"]["element"] == "木"
    assert len(details["mapping_boundaries"]["routes"]) == 4
    assert len(details["mapping_boundaries"]["counterexamples"]) == 2
    references = details["methods"]["bazhai"]["application_references"]
    assert references["status"] == "reference_only"
    assert {r["reference_id"] for r in references["references"]} == {
        "door",
        "bed",
        "stove",
    }
    stove = references["references"][2]
    assert "现代电磁灶" in stove["engine_scope"]
    assert "不从旋钮、电线或厨门猜向" in stove["engine_scope"]


def test_sand_water_and_furniture_references_request_facts_without_classifying():
    details = method_details(["jinsuo"])
    for reference in details["object_observation_references"]:
        assert reference["classification"] == "requires_independent_confirmation"
        assert reference["prescription_status"] == "not_provided"
        assert reference["classical_objects"] and reference["confirm"]
        assert reference["modern_scope"].startswith("authored_observation_prompt_")
    references = details["methods"]["jinsuo"]["application_references"]
    assert references["status"] == "reference_only"
    conditions = references["form_condition_references"]
    assert len(conditions) == 3
    assert "八宫基础砂水层不据此运行24山细断" in conditions[1]["scope"]
    assert "不能把所有盆栽" in conditions[2]["scope"]
    assert "distance_thresholds_without_source" in references["not_adopted"]
    assert details["sand_water_reference"]["status"] == "observation_candidates_only"
    assert method_details([])["methods"] == {}


def test_shape_symbols_do_not_become_afsi_material_or_placement_prescriptions():
    details = method_details()
    material = details["material_shape_reference"]
    sources = {s["source_id"] for s in details["ruleset"]["sources"]}
    assert material["status"] == "reference_only"
    assert set(material["ruleset"]["source_ids"]) <= sources
    assert {"M_AFSI", "M_FSI"} <= sources
    assert material["shapes"]["round"]["element"] == "金"
    assert material["shapes"]["triangular"]["element"] == "火"
    assert "not_placement_prescriptions" in material["scope"]
    # Cross-text wood furniture images do not qualify processed wood as an
    # AFSI living-wood representative or as an object every room needs.
    assert (
        "木桌"
        in details["object_observation_references"][2]["modern_observation_candidates"]
    )
    assert "processed_wood" not in material["materials"]


def test_expansion_does_not_change_calculation_or_add_sourced_advice():
    raw = assess(methods=["annual_stars"], effective_year=2026)
    expanded = assess(scene="home", methods=["annual_stars"], effective_year=2026)
    assert raw["layers"] == expanded["layers"]
    assert expanded["method_details"]["status"] == "reference_only"
    assert expanded["method_details"]["ruleset"]["version"] == "1.1.0"
    for record in walk_records(expanded["method_details"]):
        assert "success_probability" not in record
        assert "recommended_placement" not in record
        assert "immediate_action" not in record


@pytest.mark.parametrize(
    "path",
    [
        ("flying_star_references", "4", "profession_reference", "examples"),
        ("cross_text_trigram_symbols", "坎", "object_symbols"),
        ("methods", "bazhai", "application_references", "references"),
    ],
)
def test_expanded_nested_data_is_isolated_between_calls(path):
    original = method_details()
    changed = original
    for key in path:
        changed = changed[key]
    expected = deepcopy(changed)
    changed.clear()
    fresh = method_details()
    for key in path:
        fresh = fresh[key]
    assert fresh == expected
