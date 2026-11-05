"""Regional birth-offset selection agrees over the actual local three surfaces."""

import asyncio

import pytest

from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest
from tests.numerology.test_heluo_poem_transports import run_three
from tests.numerology.test_numerology_birth_fold import BASE, REFERENCE

rest = shared_rest


@pytest.fixture(autouse=True)
def native_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


@pytest.mark.parametrize("key", ["heluo", "canping"])
@pytest.mark.parametrize(
    "case", REFERENCE["cases"], ids=lambda c: c["birth_utc_offset"]
)
def test_region_offset_and_real_luck_boundaries_agree(
    key, case, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {**BASE, "birth_utc_offset": case["birth_utc_offset"]}
    fields = [
        "input_normalized",
        "four_pillars",
        "numerology_evidence.birth_clock",
        "snapshot_text",
    ]
    if key == "canping":
        fields += ["canping_timing", "dayun"]
    response, code, cli, mcp = run_three(spec, payload, fields, rest, tmp_path, capsys)
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        spec.output_model.model_validate(output)
        clock = output["numerology_evidence"]["birth_clock"]
        assert clock["timezone_spec"] == "America/Havana"
        assert clock["birth_instant_utc"] == case["utc"]
        assert clock["civil_fold"] == case["fold"]
        if key == "canping":
            assert output["canping_timing"]["start_at"] == case["appendix_start_at"]


@pytest.mark.parametrize("key", ["heluo", "canping"])
def test_offset_receipt_is_reachable_by_narrow_field_projection(
    key, rest, tmp_path, capsys
):
    fields = [
        "numerology_evidence.birth_clock.civil_fold",
        "numerology_evidence.birth_clock.requested_utc_offset",
    ]
    response, code, cli, mcp = run_three(
        SPECS[key],
        {**BASE, "birth_utc_offset": "-05:00"},
        fields,
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    assert (
        business(response.json()) == business(cli) == business(mcp.structured_content)
    )
    assert response.json()["numerology_evidence"]["birth_clock"] == dict(
        civil_fold=1, requested_utc_offset="-05:00"
    )


@pytest.mark.parametrize("key", ["heluo", "canping"])
@pytest.mark.parametrize(
    "change,status,error",
    [
        ({}, 400, "ambiguous local time"),
        ({"birth_utc_offset": "-03:00"}, 400, "birth_utc_offset"),
        (
            {
                "date": "1990-04-15",
                "time": "02:30",
                "zone": "Asia/Shanghai",
                "birth_utc_offset": "+09:00",
            },
            400,
            "nonexistent local time",
        ),
        ({"birth_utc_offset": "未知"}, 422, "birth_utc_offset"),
    ],
)
def test_invalid_or_unknown_clock_keeps_the_same_error_on_all_surfaces(
    key, change, status, error, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = {**BASE, **change}
    response = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    mcp = asyncio.run(native(spec, payload))
    assert response.status_code == status and code != 0 and mcp.is_error
    assert (
        error in str(response.json())
        and error in str(cli)
        and error in str(mcp.content)
    )
