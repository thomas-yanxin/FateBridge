"""Protocol defaults must not masquerade as supplied birth-record components."""

import asyncio

import pytest

from tests.bazi.test_bazi_birth_seconds import BASE, SPECS
from tests.bazi.test_bazi_birth_seconds_transports import leaf, receipt_path
from tests.support.transports import AS_OF, call_cli, inputs, native
from tests.support.transports import rest as _shared_rest


def omitted_payload(spec):
    result = {**inputs(spec), **BASE}
    result.pop("birth_minute", None)
    result.pop("birth_second", None)
    return result


rest = _shared_rest


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.key)
def test_mcp_preserves_omitted_minute_on_every_actual_bazi_and_timing_entry(spec):
    payload = omitted_payload(spec)
    result = asyncio.run(
        native(
            spec,
            payload,
            fields=[receipt_path(spec)],
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert not result.is_error
    receipt = leaf(result.structured_content, receipt_path(spec))
    assert receipt["omitted_components"] == ["minute", "second"]
    assert receipt["calculation_defaults"] == {"minute": 0, "second": 0}
    assert "minute" not in receipt["supplied_components"]


@pytest.mark.parametrize(
    "key", ["analyze_destiny", "bazi_birth", "bazi_career", "timing_analysis"]
)
@pytest.mark.parametrize(
    "components,expected",
    [
        ({}, ["minute", "second"]),
        ({"birth_minute": 0, "birth_second": None}, ["second"]),
        ({"birth_minute": 0, "birth_second": 0}, []),
    ],
)
def test_component_presence_agrees_on_actual_rest_mcp_and_cli(
    key, components, expected, rest, tmp_path, capsys
):
    spec = next(s for s in SPECS if s.key == key)
    payload = {**omitted_payload(spec), **components}
    flags = [
        "--fields",
        receipt_path(spec),
        "--strict-fields",
        "true",
        "--include-snapshot-text",
        "false",
        "--response-char-limit",
        "0",
    ]
    opts = dict(
        fields=[receipt_path(spec)], strict_fields=True, include_snapshot_text=False
    )
    result = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert not result.is_error and code == 0
    values = [
        leaf(result.structured_content, receipt_path(spec)),
        leaf(cli, receipt_path(spec)),
    ]
    if spec.rest_path:
        response = rest.post(
            spec.rest_path,
            json=payload,
            params={"as_of": AS_OF, "response_char_limit": 0, **opts},
        )
        assert response.status_code == 200
        values.append(leaf(response.json(), receipt_path(spec)))
    assert all(value == values[0] for value in values)
    assert values[0]["omitted_components"] == expected


@pytest.mark.parametrize(
    "key", ["analyze_destiny", "bazi_birth", "bazi_career", "dayun_analysis"]
)
def test_missing_minute_is_not_filled_before_second_validation(
    key, rest, tmp_path, capsys
):
    spec = next(s for s in SPECS if s.key == key)
    payload = {**omitted_payload(spec), "birth_second": 0}
    result = asyncio.run(native(spec, payload))
    code, _ = call_cli(spec, payload, tmp_path, capsys)
    assert result.is_error and code != 0
    if spec.rest_path:
        assert rest.post(spec.rest_path, json=payload).status_code == 422
