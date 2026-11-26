"""Independent author predicates and AFSI diagrams, with explicit source scope."""

import json
from pathlib import Path

import pytest

from fatebridge.core.fengshui.layout_supplements import _effect
from fatebridge.services.fengshui import assess

REFERENCE = json.loads(
    (
        Path(__file__).parents[1]
        / "fixtures/fengshui-interior-authors-reference-v1.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize("reference", REFERENCE["rules"], ids=lambda r: r["id"])
def test_independent_author_predicates_keep_sources_and_candidate_endpoints(
    reference,
) -> None:
    objects = []
    for endpoint in ("source", "target"):
        role = reference[f"{endpoint}_role"]
        kind = (
            "opening"
            if role in {"main_entry_door", "bathroom_door"}
            else "furniture" if role in {"bed", "desk", "stove"} else "material_object"
        )
        objects.append(
            {
                "object_id": endpoint,
                "kind": kind,
                "role": role,
                "label": endpoint,
                "evidence": "核对原作者所指实际物件身份",
            }
        )
    result = assess(
        methods=[],
        environmental_context={
            "objects": objects,
            "interior_relations": [
                {
                    "relation_id": "independent-author",
                    "kind": reference["kind"],
                    "source_object_id": "source",
                    "target_object_id": "target",
                    "present": True,
                    "observation_basis": "user_confirmed",
                    "evidence": reference["predicate_scope"],
                }
            ],
        },
    )["layout_analysis"]["interior_analysis"]
    finding = result["findings"][0]
    assert finding["status"] == "authored_caution"
    assert finding["rule_id"] == reference["id"]
    assert finding["source_ids"] == reference["source_ids"]
    assert [
        [a["object_id"], a["operation"]] for a in result["action_options"]
    ] == reference["candidate_operations"]
    assert all(a["status"] == "conditional_option" for a in result["action_options"])
    if "separate_dissent" in reference:
        assert reference["separate_dissent"] in {
            d["source_id"] for d in finding["method_disagreements"]
        }
    else:
        pass


@pytest.mark.parametrize(
    "introduced,target,expected",
    [
        (introduced, target, REFERENCE["introduced_by_target_relationships"][i][j])
        for i, introduced in enumerate(REFERENCE["elements"])
        for j, target in enumerate(REFERENCE["elements"])
    ],
)
def test_all_element_pairs_match_independently_read_afsi_cycle_diagrams(
    introduced, target, expected
) -> None:
    assert _effect(introduced, target) == expected


@pytest.mark.parametrize("direction,goal", [("N", "drain"), ("W", "support")])
def test_afsi_water_candidate_keeps_clean_and_moving_source_qualifiers(
    direction: str, goal: str
) -> None:
    result = assess(
        methods=["annual_stars"],
        effective_year=2026,
        placements=[
            {"object_id": "desk", "purpose": "desk", "location_direction": direction}
        ],
        element_adjustments=[
            {
                "request_id": "source-water",
                "object_id": "desk",
                "target_method": "annual_stars",
                "goal": goal,
                "evidence": "仅核对AFSI原书代表物限定，不认证现场布水或现实效力",
            }
        ],
    )
    plan = result["layout_analysis"]["element_remedies"][0]
    assert plan["introduced_element"] == "水"
    assert any(
        "清洁" in item and "流动" in item for item in plan["representations"]["objects"]
    )


def test_bed_headboard_adjustment_cites_the_author_who_explicitly_describes_it() -> (
    None
):
    result = assess(
        methods=[],
        form_observations=[
            {
                "object_id": "bed",
                "purpose": "bed",
                "entrance_visible": True,
                "entrance_direct_line": False,
                "solid_backing": False,
                "observation_basis": "user_confirmed",
                "evidence": "已核对入口与床头实际支撑",
            }
        ],
    )
    checks = result["layout_analysis"]["form_analysis"]["findings"][0]["checks"]
    backing = next(c for c in checks if c["criterion"] == "solid_backing")
    assert "床头" in backing["adjustment"]
    assert {"F1", "F2"} <= set(backing["source_ids"])
