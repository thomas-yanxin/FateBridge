"""The conditional root projection is one receipt across all three interfaces."""

import asyncio

import pytest

from fatebridge.application.examples import suggested_fields
from tests.bazi.test_bazi_timing_roots_transports import PAYLOAD
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _shared_rest
from tests.integration.test_result_delivery import reconstruct
from tests.integration.test_result_delivery import store as _store_fixture

store = _store_fixture


rest = _shared_rest


@pytest.mark.parametrize(
    "payload,node,status,stem_position",
    [
        (
            dict(
                birth_year=1973,
                birth_month=11,
                birth_day=1,
                birth_hour=20,
                analysis_year=2026,
                analysis_month=11,
                analysis_day=3,
            ),
            "timing.dayun",
            "projected",
            "month",
        ),
        (
            dict(
                birth_year=1988,
                birth_month=7,
                birth_day=5,
                birth_hour=8,
                analysis_year=2007,
                analysis_month=11,
                analysis_day=3,
            ),
            "timing.liunian",
            "blocked",
            None,
        ),
    ],
)
def test_unique_dayun_budget_and_unsupported_annual_match_have_three_surface_parity(
    payload, node, status, stem_position, rest, tmp_path, capsys
):
    spec = SPECS["timing_analysis"]
    payload = {
        **payload,
        "name": "虚构运干预算控制",
        "birth_minute": 0,
        "birth_second": 0,
        "birth_timezone": "Asia/Shanghai",
        "use_true_solar_time": False,
        "gender": "男",
        "analysis_hour": 12,
        "analysis_minute": 0,
    }
    fields = ["interaction_analysis.strength_projection"]
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    http = rest.post(spec.rest_path, json=payload, params={**options, "as_of": AS_OF})
    protocol = asyncio.run(native(spec, payload, **options))
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json())
        == business(protocol.structured_content)
        == business(local)
    )
    for value in (http.json(), protocol.structured_content, local):
        spec.output_model.model_validate(value)
        projection = value["interaction_analysis"]["strength_projection"]
        row = next(r for r in projection["layers"] if r["node_id"] == node)
        assert row["status"] == status
        assert projection["stem_binding_source"]["supported_layer"] == "dayun"
        if stem_position is not None:
            assert row["stem_retention_factors_exact"][stem_position] == "17/20"
        else:
            assert row["energies_exact"] == row["stem_retention_factors_exact"] == {}
            assert row["support_share_exact"] is None


def test_root_effect_view_matches_rest_mcp_cli_and_retains_unadjudicated_scope(
    rest, tmp_path, capsys
):
    spec = SPECS["timing_analysis"]
    fields = suggested_fields(spec, view="root_effects")
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    http = rest.post(spec.rest_path, json=PAYLOAD, params={**options, "as_of": AS_OF})
    protocol = asyncio.run(native(spec, PAYLOAD, **options))
    code, cli = call_cli(
        spec,
        PAYLOAD,
        tmp_path,
        capsys,
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    outputs = [http.json(), protocol.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        spec.output_model.model_validate(output)
        projection = output["interaction_analysis"]["strength_projection"]
        assert projection["full_timing_strength_status"] == "not_adjudicated"
        assert projection["month_command_node_id"] == "natal.month"
        assert len(projection["layers"]) == 5
        assert all(
            r["quantity_kind"] == "residual_natal_budget_only"
            for r in projection["layers"]
        )
        assert projection["baseline"]["parameters"]["strong_share"] == 0.6
        assert projection["baseline"]["parameters"]["weak_share"] == 0.4


def test_bounded_projection_retains_same_run_and_snapshot_explains_partial_force(
    rest, store
):
    spec = SPECS["timing_analysis"]
    response = rest.post(
        spec.rest_path,
        json=PAYLOAD,
        params=dict(
            fields=suggested_fields(spec, view="root_effects"),
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=8192,
            as_of=AS_OF,
        ),
    )
    assert response.status_code == 200
    value = response.json()
    complete = (
        reconstruct(store, value["result_delivery"]["result_id"])
        if "result_delivery" in value
        else value
    )
    assert complete["run_metadata"]["run_id"] == value["run_metadata"]["run_id"]
    assert len(complete["interaction_analysis"]["strength_projection"]["layers"]) == 5
    full = rest.post(
        spec.rest_path, json=PAYLOAD, params=dict(response_char_limit=0, as_of=AS_OF)
    )
    assert full.status_code == 200
    assert "残存原局数值档不是完整行运后旺衰" in full.json()["snapshot_text"]
