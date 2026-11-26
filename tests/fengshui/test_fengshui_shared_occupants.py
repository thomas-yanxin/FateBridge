"""Object users are a subset of residents, independent of other chart layers."""

import asyncio
import json
from copy import deepcopy
from itertools import combinations
from pathlib import Path

import pytest
from fastmcp import Client
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.cli import run
from fatebridge.core.fengshui.models import AssessRequest, Placement
from fatebridge.services.fengshui import assess as _assess
from tests.support.mcp_result_assertions import without_transport
from tests.support.transports import call_calculation, rest_client


def assess(**kwargs):
    return _assess(AssessRequest.model_validate(kwargs))


RESIDENTS = [
    {"subject_id": "a", "effective_birth_year": 1990, "gender_convention": "male"},
    {"subject_id": "b", "effective_birth_year": 2000, "gender_convention": "male"},
    {"subject_id": "c", "effective_birth_year": 1990, "gender_convention": "female"},
]
ROLES = {
    "door": "door_facing",
    "bed": "headboard",
    "desk": "desk_facing",
    "stove": "fire_mouth",
}
SUBSETS = [list(c) for n in range(1, 4) for c in combinations(["a", "b", "c"], n)]


def request(purpose="bed", selected=None):
    placement = {
        "object_id": "shared",
        "purpose": purpose,
        "location_direction": "N",
        "facing_direction": "E",
        "facing_role": ROLES[purpose],
    }
    if selected is not None:
        placement["subject_ids"] = selected
    else:
        pass
    return {
        "methods": ["bazhai"],
        "analyze_layout": True,
        "house": {"object_id": "home", "sitting_trigram": "坎"},
        "occupants": deepcopy(RESIDENTS),
        "placements": [placement],
    }


@pytest.mark.parametrize("purpose", ROLES)
@pytest.mark.parametrize("selected", SUBSETS)
def test_shared_subset_matches_same_users_in_isolation_for_all_directions(
    purpose, selected
) -> None:
    """Adding an unrelated resident cannot change this object's judgments."""
    for direction in ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]:
        inputs = request(purpose, selected)
        inputs["placements"][0].update(
            location_direction=direction, facing_direction=direction
        )
        subset = deepcopy(inputs)
        subset["occupants"] = [
            p for p in subset["occupants"] if p["subject_id"] in selected
        ]
        subset["placements"][0].pop("subject_ids")
        actual, isolated = assess(**inputs), assess(**subset)
        for key in [
            "placement_findings",
            "adjustment_options",
            "element_relationships",
        ]:
            assert actual["layout_analysis"][key] == isolated["layout_analysis"][key]
        assert (
            actual["layers"]["bazhai"]["placement_findings"]
            == isolated["layers"]["bazhai"]["placement_findings"]
        )
        subjects = {
            f["subject_id"] for f in actual["layout_analysis"]["placement_findings"]
        }
        assert subjects == set(selected) | {"home"}


def test_subset_removes_unrelated_person_from_common_direction_intersection() -> None:
    shared = assess(**request(selected=["a", "b"]))["layout_analysis"][
        "adjustment_options"
    ][0]
    all_residents = assess(**request())["layout_analysis"]["adjustment_options"][0]
    assert shared["agreed_matching_directions"]
    assert all_residents["agreed_matching_directions"] == []


def test_single_occupant_selector_and_subset_are_compatible_without_output_change() -> (
    None
):
    plural = request(selected=["a"])
    single = deepcopy(plural)
    single["placements"][0].pop("subject_ids")
    single["placements"][0]["subject_id"] = "a"
    assert assess(**plural) == assess(**single)
    assert assess(**request(selected=["a", "b", "c"])) == assess(**request())


def test_unselected_candidates_do_not_enter_element_binding_or_cross_scope_effects() -> (
    None
):
    inputs = request(selected=["a", "b"])
    inputs.update(
        methods=["bazhai", "annual_stars"],
        effective_year=2026,
        annual_remedy_ruleset_id="pang_2026_annual_v1",
    )
    inputs["placements"][0]["location_direction"] = "S"
    inputs["occupants"][2].pop("gender_convention")
    inputs["element_adjustments"] = [
        {
            "request_id": "outside",
            "object_id": "shared",
            "target_method": "bazhai",
            "subject_id": "c",
            "aspect": "location",
            "goal": "drain",
            "evidence": "测试未使用该物体的住户不能成为目标",
        }
    ]
    actual = assess(**inputs)["layout_analysis"]
    assert actual["element_remedies"][0]["status"] == "needs_computed_target"
    effects = actual["annual_remedies"]["findings"][0]["cross_scope_effects"]
    assert {e["subject_id"] for e in effects if e["subject_kind"] == "occupant"} == {
        "a",
        "b",
    }


@pytest.mark.parametrize(
    "scope",
    [
        {"subject_ids": []},
        {"subject_ids": ["a", "a"]},
        {"subject_id": "a", "subject_ids": ["a", "b"]},
    ],
)
def test_runtime_and_published_schema_reject_invalid_scope(scope) -> None:
    placement = {**request()["placements"][0], **scope}
    with pytest.raises(ValidationError):
        Placement.model_validate(placement)
    assert list(
        Draft202012Validator(Placement.model_json_schema()).iter_errors(placement)
    )


def test_subset_references_must_exist_in_the_request() -> None:
    with pytest.raises(ValidationError, match="未提供的住户"):
        AssessRequest.model_validate(request(selected=["a", "missing"]))


@pytest.mark.parametrize(
    "scope", [{"subject_ids": None}, {"subject_id": None, "subject_ids": ["a", "b"]}]
)
def test_explicit_null_is_consistent_between_schema_and_runtime(scope) -> None:
    placement = {**request()["placements"][0], **scope}
    Placement.model_validate(placement)
    Draft202012Validator(Placement.model_json_schema()).validate(placement)


@pytest.mark.parametrize("name", ["bazhai", "assess"])
def test_shared_subset_has_the_same_scope_on_rest_mcp_cli(
    name: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from fatebridge.mcp_server import create_mcp_app

    inputs = request(selected=["a", "b"])
    if name == "bazhai":
        inputs.pop("methods")
        inputs.pop("analyze_layout")
    else:
        pass
    fields = ["layers.bazhai.placement_findings"]
    if name == "assess":
        fields.append("layout_analysis.adjustment_options")
    else:
        pass
    controls = {"detail": "audit", "fields": fields}

    async def call():
        async with Client(create_mcp_app()) as client:
            return await call_calculation(
                client,
                "fengshui_" + name,
                {**inputs, **controls},
            )

    rest = rest_client(monkeypatch).post(
        "/api/fengshui/" + name, params=controls, json=inputs
    )
    mcp = asyncio.run(call())
    path = tmp_path / "shared.json"
    path.write_text(json.dumps(inputs))
    assert (
        run(
            [
                "fengshui_" + name,
                "--request-file",
                str(path),
                "--detail",
                "audit",
                "--fields",
                *fields,
            ]
        )
        == 0
    )
    cli = json.loads(capsys.readouterr().out)
    assert rest.status_code == 200 and not mcp.is_error
    assert (
        without_transport(rest.json())
        == without_transport(mcp.structured_content)
        == without_transport(cli)
    )
    findings = cli["layers"]["bazhai"]["placement_findings"]
    assert {f["subject_id"] for f in findings} == {"home", "a", "b"}
