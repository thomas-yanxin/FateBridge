"""The explicit source policy agrees across actual local REST/MCP/CLI calls."""

import asyncio
import json

import pytest

from tests.test_agentic_nested_outputs import SPECS, call_cli, inputs, native, rest
from tests.test_western_origin_preflight import directories, selected


@pytest.mark.parametrize(
    "key",
    [
        "astro_chart",
        "astro_hellen",
        "astro_chart13",
        "astro_germany",
        "astro_horary",
        "astro_election",
        "profection",
        "astro_harmonic",
    ],
)
@pytest.mark.parametrize("mode", ["empty", "planet_only", "full"])
def test_actual_public_adapters_share_explicit_source_policy(
    key, mode, selected, rest, tmp_path, capsys
):
    spec = SPECS[key]
    selected(mode)
    payload = {**inputs(spec), "ephemeris_policy": "require_data_files"}
    http = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(
        spec, payload, tmp_path, capsys, ["--response-char-limit", "0"]
    )
    protocol = asyncio.run(native(spec, payload))
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    if mode == "full":
        assert http.status_code == 200 and code == 0 and not protocol.is_error
        for value in values:
            receipt = value["ephemeris_data_policy"]
            assert receipt["requested"] == "require_data_files"
            assert receipt["physical_calls_by_model"]["swieph"] > 0
            assert receipt["accuracy_certified"] is False
        assert (
            values[0]["ephemeris_data_policy"]
            == values[1]["ephemeris_data_policy"]
            == values[2]["ephemeris_data_policy"]
        )
    else:
        assert http.status_code == 503 and code == 1 and protocol.is_error
        for value in values:
            assert value["error_code"] == "ephemeris_source_inconsistent"
            assert value["issues"][0]["code"] == (
                "required_data_files_fallback"
                if mode == "empty"
                else "swiss_dependency_unavailable"
            )
            assert value["retryable"] is False
            assert "ephemeris_data_policy" not in value and "score" not in value
    for index, value in enumerate(values):
        (tmp_path / f"{key}-{mode}-{index}.json").write_text(json.dumps(value))


def test_policy_evidence_view_projects_the_same_receipt_on_all_adapters(
    selected, rest, tmp_path, capsys
):
    from fatebridge.application.examples import suggested_fields

    selected("full")
    spec = SPECS["astro_chart"]
    payload = {**inputs(spec), "ephemeris_policy": "require_data_files"}
    fields = suggested_fields(spec, view="data_files")
    http = rest.post(
        spec.rest_path,
        json=payload,
        params={
            "fields": fields,
            "strict_fields": "true",
            "include_snapshot_text": "false",
        },
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        [
            "--fields",
            "ephemeris_data_policy",
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    assert (
        values[0]["ephemeris_data_policy"]
        == values[1]["ephemeris_data_policy"]
        == values[2]["ephemeris_data_policy"]
    )
    assert all(
        "planets" not in value and "snapshot_text" not in value for value in values
    )
