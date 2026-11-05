"""The same plane facts are discoverable and delivered on all public BaZi routes."""

import asyncio

import pytest

from fatebridge.application.examples import evidence_views, suggested_fields
from fatebridge.core.output_element_presence import ElementPresence
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest

KEYS = [
    "bazi_birth",
    "bazi_career",
    "bazi_wealth",
    "bazi_health",
    "bazi_children",
    "bazi_education",
    "bazi_personality",
    "bazi_relatives",
    "bazi_marriage",
    "bazi_romance",
    "analyze_destiny",
]


def descend(result, path):
    for key in path.split("."):
        result = result[key]
    return result


rest = _shared_rest


@pytest.mark.parametrize("key", KEYS)
def test_presence_view_on_rest_native_mcp_and_cli(key, rest, tmp_path, capsys):
    spec = SPECS[key]
    payload = inputs(spec)
    fields = evidence_views(spec)["element_presence"]["fields"]
    rest_spec = SPECS["bazi_birth"] if key == "analyze_destiny" else spec
    response = rest.post(
        rest_spec.rest_path,
        json=payload,
        params={
            "fields": (
                ["bazi_birth." + f for f in fields]
                if key == "analyze_destiny"
                else fields
            ),
            "strict_fields": "true",
            "include_snapshot_text": "false",
            "response_char_limit": 0,
        },
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
    )
    mcp = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert response.status_code == 200, response.text
    assert code == 0 and not mcp.is_error
    rest_business = business(response.json())
    if key == "analyze_destiny":
        rest_business = rest_business["bazi_birth"]
    assert rest_business == business(cli) == business(mcp.structured_content)
    facts = descend(cli, fields[0])
    ElementPresence.model_validate(facts)
    assert facts["calculation_effect"] == "none"
    assert "snapshot_text" not in response.json()


def test_career_first_view_keeps_preexisting_strength_facts_and_declares_full_energy_view(
    rest,
):
    spec = SPECS["bazi_career"]
    payload = inputs(spec)
    first_fields = suggested_fields(spec)
    # Direction omits timing fields by design; compare only their common
    # strength receipt, preserving each view's independently declared scope.
    assert {f for f in first_fields if ".strength_context." in f} == {
        f
        for f in evidence_views(spec)["direction"]["fields"]
        if ".strength_context." in f
    }
    controls = {
        "strict_fields": "true",
        "include_snapshot_text": "false",
        "response_char_limit": 0,
    }
    first = rest.post(
        spec.rest_path, json=payload, params={**controls, "fields": first_fields}
    )
    deep = rest.post(
        spec.rest_path,
        json=payload,
        params={**controls, "fields": evidence_views(spec)["depth"]["fields"]},
    )
    assert first.status_code == deep.status_code == 200
    path = "career_analysis.evidence_chain.strength_context"
    summary, complete = descend(first.json(), path), descend(deep.json(), path)
    old_keys = {
        "strength_level",
        "method_id",
        "status",
        "requires_special_structure_review",
        "candidate_strengths",
        "root_effect_policy",
        "root_qualifications",
        "storage_movement_effects",
    }
    assert old_keys <= set(summary)
    assert {k: summary[k] for k in old_keys} == {k: complete[k] for k in old_keys}
    assert summary["stem_energy_accounting"] == {
        k: complete["stem_energy_accounting"][k]
        for k in ("method_id", "arithmetic_policy", "conversion_policy")
    }
    assert len(complete["stem_energy_accounting"]["ledger"]) == 3
    assert evidence_views(spec)["stem_energy"]["fields"]
