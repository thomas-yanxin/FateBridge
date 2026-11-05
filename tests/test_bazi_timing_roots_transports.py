"""Published root views retain the same calculation on REST, MCP and CLI."""

import asyncio

import pytest

from fatebridge.application.examples import suggested_fields
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
)
from tests.test_agentic_nested_outputs import rest as _shared_rest
from tests.test_result_delivery import reconstruct
from tests.test_result_delivery import store as _shared_store

PAYLOAD = dict(
    birth_year=1990,
    birth_month=5,
    birth_day=15,
    birth_hour=10,
    birth_minute=30,
    gender="男",
    birth_timezone="Asia/Shanghai",
    use_true_solar_time=False,
    analysis_year=2028,
    analysis_month=1,
    analysis_day=20,
    analysis_hour=12,
)


rest = _shared_rest
store = _shared_store


@pytest.mark.parametrize("view", ["roots", "stem_roots"])
def test_published_root_views_match_three_protocols(view, rest, tmp_path, capsys):
    spec = SPECS["timing_analysis"]
    fields = suggested_fields(spec, view=view)
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    response = rest.post(
        spec.rest_path, json=PAYLOAD, params={**options, "as_of": AS_OF}
    )
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
    assert response.status_code == 200 and not protocol.is_error and code == 0
    outputs = [response.json(), protocol.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        spec.output_model.model_validate(output)
        context = output["interaction_analysis"]["root_context"]
        assert context["method_id"] == "natal_timing_root_support_v1"
        assert context["effective_force_status"] == "not_adjudicated"
        key, count = (
            ("day_master_roots", 5)
            if view == "roots"
            else ("timing_stem_natal_roots", 20)
        )
        assert len(context[key]) == count
        assert all(
            r["classification"]["effect_status"] == "root_effect_not_adjudicated"
            for r in context[key]
        )
        relations = {r["id"] for r in output["interaction_analysis"]["relations"]}
        assert all(set(r["branch_relation_ids"]) <= relations for r in context[key])


def test_bounded_first_view_retains_full_same_run_and_snapshot_uses_root_receipt(
    rest, store
):
    spec = SPECS["timing_analysis"]
    response = rest.post(
        spec.rest_path,
        json=PAYLOAD,
        params=dict(
            fields=suggested_fields(spec, view="roots"),
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=8192,
            as_of=AS_OF,
        ),
    )
    assert response.status_code == 200
    value = response.json()
    if "result_delivery" in value:
        ref = value["result_delivery"]
        complete = reconstruct(store, ref["result_id"])
        assert complete["run_metadata"]["run_id"] == value["run_metadata"]["run_id"]
    else:
        complete = value
    assert (
        len(complete["interaction_analysis"]["root_context"]["day_master_roots"]) == 5
    )
    assert complete["interaction_analysis"]["nodes"]
    assert complete["interaction_analysis"]["relations"]
    full = rest.post(
        spec.rest_path,
        json=PAYLOAD,
        params=dict(
            include_snapshot_text=True,
            response_char_limit=0,
            as_of=AS_OF,
        ),
    )
    assert full.status_code == 200
    assert "根类与冲合刑触点分列" in full.json()["snapshot_text"]
