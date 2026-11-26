"""Keep scoped Ba Zhai facts faithful through inverse layout and readable output."""

import asyncio
import json
from pathlib import Path

import pytest

from fatebridge.cli import run
from fatebridge.core.fengshui.models import AssessRequest, BazhaiRequest
from fatebridge.services.fengshui import assess as _assess
from fatebridge.services.fengshui import calculate_bazhai as _calculate_bazhai
from tests.support.fengshui_transports import mcp_call
from tests.support.mcp_result_assertions import without_transport
from tests.support.transports import rest_client


def assess(**kwargs):
    return _assess(AssessRequest.model_validate(kwargs))


def calculate_bazhai(**kwargs):
    return _calculate_bazhai(BazhaiRequest.model_validate(kwargs))

EVIDENCE = (
    "star",
    "expected_polarity",
    "matches_convention",
    "matches_convention_scope",
    "you_nian_trace",
    "palace_star_relationship",
    "rule_id",
    "source_ids",
    "application_scope",
)


def request(*, unknown_convention=False):
    occupant = {"subject_id": "resident", "effective_birth_year": 1990}
    if not unknown_convention:
        occupant["gender_convention"] = "male"
    else:
        pass
    return {
        "methods": ["bazhai"],
        "analyze_layout": True,
        "house": {"sitting_trigram": "坎"},
        "occupants": [occupant],
        "placements": [
            {
                "object_id": "bed",
                "purpose": "bed",
                "location_direction": "E",
                "subject_id": "resident",
            }
        ],
    }


def test_inverse_matching_direction_keeps_the_countervailing_element_fact() -> None:
    result = assess(**request())
    option = result["layout_analysis"]["adjustment_options"][0]
    house = next(s for s in option["scopes"] if s["subject_kind"] == "house")
    east = house["matching_direction_evidence"]["E"]
    # Literal star/operation fixtures: 坎 -> 震 is 天医土, six operations;
    # the E palace is wood. Basic star polarity does not remove wood -> earth.
    assert east["star"]["name"] == "天医" and east["star"]["element"] == "土"
    assert east["matches_convention"] is True
    assert east["palace_star_relationship"]["traditional_label"] == "宫克星"
    assert east["you_nian_trace"]["operation_count"] == 6
    assert east["you_nian_trace"]["net_changed_line_count"] == 2
    assert house["matching_evidence_basis"]["you_nian_trace"]["source_ids"] == ["S11"]
    assert house["matching_evidence_basis"]["palace_star_relationship"][
        "source_ids"
    ] == ["S10", "S13"]
    assert house["matching_directions"] == ["N", "E", "SE", "S"]
    assert option["current_result_scope"] == house["matches_convention_scope"]


@pytest.mark.parametrize("purpose", ["door", "bed", "desk", "stove"])
@pytest.mark.parametrize("aspect", ["location", "facing"])
def test_current_and_inverse_lookup_share_application_evidence_and_facing_role(
    purpose: str, aspect: str
) -> None:
    data = request()
    role = {
        "door": "door_facing",
        "bed": "headboard",
        "desk": "desk_facing",
        "stove": "fire_mouth",
    }[purpose]
    placement = {
        "object_id": "object",
        "purpose": purpose,
        f"{aspect}_direction": "E",
    }
    if aspect == "facing":
        placement["facing_role"] = role
    else:
        pass
    data["placements"] = [placement]
    result = assess(**data)
    options = result["layout_analysis"]["adjustment_options"]
    assert len(options) == 1
    scopes = options[0]["scopes"]
    expected = (
        "inauspicious" if (purpose, aspect) == ("stove", "location") else "auspicious"
    )
    for finding in result["layers"]["bazhai"]["placement_findings"]:
        scope = next(s for s in scopes if s["subject_id"] == finding["subject_id"])
        assert {k: scope[k] for k in EVIDENCE} == {k: finding[k] for k in EVIDENCE}
        assert scope["expected_polarity"] == expected
        assert scope["matches_convention"] == (expected == "auspicious")
        assert scope["facing_role"] == (role if aspect == "facing" else None)
        assert set(scope["matching_direction_evidence"]) == set(
            scope["matching_directions"]
        )


def test_each_proposed_direction_reproduces_a_fresh_forward_calculation() -> None:
    data = request()
    result = assess(**data)
    option = result["layout_analysis"]["adjustment_options"][0]
    for direction in ["N", "E", "SE", "S"]:
        forward = calculate_bazhai(
            house=data["house"],
            occupants=data["occupants"],
            placements=[{**data["placements"][0], "location_direction": direction}],
        )["layers"]["bazhai"]["placement_findings"]
        for finding in forward:
            scope = next(
                s for s in option["scopes"] if s["subject_id"] == finding["subject_id"]
            )
            proposed = scope["matching_direction_evidence"][direction]
            assert proposed["star"] == finding["star"]
            for key, metadata in scope["matching_evidence_basis"].items():
                assert {**metadata, **proposed[key]} == finding[key]


def test_unconfirmed_personal_candidates_remain_distinct_in_every_scope() -> (
    None
):
    data = request(unknown_convention=True)
    data.pop("house")
    result = assess(**data)
    option = result["layout_analysis"]["adjustment_options"][0]
    assert option["resolution"] == "no_confirmed_scope"
    assert option["agreed_matching_directions"] == []
    assert option["current_result"] == "no_confirmed_scope"
    assert len(option["scopes"]) == 2
    assert all(s["candidate_only"] for s in option["scopes"])
    by_conv = {s["gender_convention"]: s for s in option["scopes"]}
    assert by_conv["male"]["matches_convention"] is True
    assert by_conv["male"]["star"]["name"] == "天医"
    assert by_conv["male"]["palace_star_relationship"]["traditional_label"] == "宫克星"
    assert by_conv["male"]["matching_directions"] == ["N", "E", "SE", "S"]
    assert by_conv["female"]["matches_convention"] is False
    assert by_conv["female"]["star"]["name"] == "六煞"
    assert by_conv["female"]["palace_star_relationship"]["traditional_label"] == "星生宫"
    assert by_conv["female"]["matching_directions"] == ["NE", "SW", "W", "NW"]


def test_house_and_person_conflict_keeps_per_scope_proof_without_common_direction() -> (
    None
):
    data = request()
    data["occupants"][0]["gender_convention"] = "female"
    result = assess(**data)
    option = result["layout_analysis"]["adjustment_options"][0]
    assert option["current_result"] == "scope_difference"
    assert option["agreed_matching_directions"] == []
    assert [s["matches_convention"] for s in option["scopes"]] == [True, False]
    for scope in option["scopes"]:
        assert not scope["candidate_only"]
        assert scope["palace_star_relationship"]["star_name"] == scope["star"]["name"]


@pytest.mark.parametrize("variant", ["confirmed", "candidate", "stove_facing"])
def test_layout_proof_and_readable_candidate_scopes_match_all_transports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    variant: str,
) -> None:
    data = request(unknown_convention=variant == "candidate")
    if variant == "stove_facing":
        data["placements"] = [
            {
                "object_id": "stove",
                "purpose": "stove",
                "facing_direction": "E",
                "facing_role": "fire_mouth",
            }
        ]
    else:
        pass
    http = rest_client(monkeypatch).post(
        "/api/fengshui/assess", json=data, params={"detail": "audit"}
    )
    protocol = asyncio.run(mcp_call("assess", data))
    path = tmp_path / "fidelity.json"
    path.write_text(json.dumps(data))
    assert run(["fengshui_assess", "--request-file", str(path), "--detail", "audit"]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert http.status_code == 200 and not protocol.is_error
    assert (
        without_transport(http.json())
        == without_transport(protocol.structured_content)
        == without_transport(cli)
    )
    assert "matching_direction_evidence" in http.text
    assert "current_result_scope" in http.text


def test_strict_projection_delivers_complete_inverse_evidence_on_real_mcp() -> None:
    data = {
        **request(unknown_convention=True),
        "fields": ["layout_analysis.adjustment_options", "rulesets", "rule_trace"],
    }
    result = asyncio.run(mcp_call("assess", data))
    assert not result.is_error
    body = result.structured_content
    assert set(body) == {"layout_analysis", "rulesets", "rule_trace", "run_metadata"}
    option = body["layout_analysis"]["adjustment_options"][0]
    for scope in option["scopes"]:
        for evidence in scope["matching_direction_evidence"].values():
            assert evidence["matches_convention"] is True
            for key, metadata in scope["matching_evidence_basis"].items():
                assert metadata["source_ids"]
                assert "rule_id" in metadata and "scope" in metadata
                assert evidence[key]
