"""Selected author conditions and monthly scope, independent of action permission."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.services.fengshui import assess
from tests.fengshui.test_fengshui_surfaces_authored import surface_input

REFERENCE = json.loads(
    (
        Path(__file__).parents[1]
        / "fixtures/fengshui-desktop-authors-reference-v1.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize("representation", REFERENCE["botanical_representations"])
@pytest.mark.parametrize("state", REFERENCE["health_states"], ids=lambda s: s["id"])
def test_botanical_conditions_follow_the_selected_author_without_guessing_state(
    representation, state
):
    inputs = surface_input()
    item = inputs["surface_layouts"][0]["items"][0]
    item["representation"] = representation
    if state["input"] != "omit":
        item["healthy"] = deepcopy(state["input"])
    result = assess(**inputs)
    layout = result["layout_analysis"]
    surface = layout["surface_analysis"]
    action = surface["findings"][0]["action_options"][0]
    rule = REFERENCE["botanical_rule"]
    assert action["rule_id"] == rule["rule_id"]
    assert action["to_zone"] == rule["zone"]
    assert action["source_ids"] == rule["source_ids"]
    assert action["status"] == state["expected_action"]
    assert action["application_conditions_met"] is state["application_conditions_met"]
    assert surface["analysis_progress"]["assessment_complete"] is True
    assert surface["analysis_progress"]["follow_up"]["conclusion_candidates"] == []
    if state["expected_action"] == "blocked":
        assert action["pending_confirmations"] == []
        assert "representation_condition_not_met" in action["constraint_reasons"]
    elif state["expected_action"] == "conditional_option":
        assert any(
            pending["path"].endswith(".healthy") and pending["required_for"] == "action"
            for pending in action["pending_confirmations"]
        )
    else:
        assert action["pending_confirmations"] == []


@pytest.mark.parametrize("companion", ["none", "annual", "forms", "annual_and_forms"])
def test_monthly_numeric_completion_does_not_erase_its_unsupported_usage_scope(
    companion,
):
    inputs = {
        "methods": ["monthly_stars"],
        "monthly": {"effective_solar_year": 2026, "solar_month_number": 9},
        "analyze_layout": True,
        "placements": [
            {"object_id": "desk", "purpose": "desk", "location_direction": "N"}
        ],
    }
    if "annual" in companion:
        inputs["methods"].append("annual_stars")
        inputs["effective_year"] = 2026
    if "forms" in companion:
        inputs["form_observations"] = [
            {
                "object_id": "desk",
                "purpose": "desk",
                "entrance_visible": True,
                "entrance_direct_line": False,
                "solid_backing": True,
                "observation_basis": "user_confirmed",
                "evidence": "其他作者条件独立确认",
            }
        ]
    result = assess(**inputs)
    layout = result["layout_analysis"]
    monthly = next(
        f for f in layout["placement_findings"] if f["method"] == "monthly_stars"
    )
    scope = REFERENCE["monthly_scope"]
    assert monthly["application_scope"] == scope["application_scope"]
    assert monthly["usage_interpretation"] == scope["usage_interpretation"]
    assert "monthly_usage_fortune_or_action_rules" in layout["unsupported_queries"]
    assert layout["analysis_progress"]["assessment_complete"] is True
    assert (
        layout["analysis_progress"]["rule_coverage_status"]
        == scope["rule_coverage_status"]
    )
    assert result["coverage"]["analysis_progress"] == layout["analysis_progress"]
