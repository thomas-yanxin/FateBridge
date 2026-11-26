"""Published root views retain the same calculation on REST, MCP and CLI."""

import pytest

from fatebridge.application.examples import suggested_fields
from tests.support.transports import AS_OF, SPECS, business
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

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


@pytest.mark.parametrize("view", ["roots", "stem_roots"])
def test_published_root_views_match_three_protocols(view: str, surface_calls) -> None:
    spec = SPECS["bazi_timing"]
    fields = suggested_fields(spec, view=view)
    options = dict(fields=fields, detail="audit")
    response, protocol, code, cli = surface_calls(
        spec, PAYLOAD, projection=options, cli_first=False, rest_as_of=AS_OF
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


def test_root_view_retains_nodes_and_relations(rest) -> None:
    spec = SPECS["bazi_timing"]
    response = rest.post(
        spec.rest_path,
        json=PAYLOAD,
        params=dict(
            fields=suggested_fields(spec, view="roots"),
            as_of=AS_OF,
        ),
    )
    assert response.status_code == 200
    value = response.json()
    assert len(value["interaction_analysis"]["root_context"]["day_master_roots"]) == 5
    assert value["interaction_analysis"]["nodes"]
    assert value["interaction_analysis"]["relations"]
