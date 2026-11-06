"""Control eligibility and unresolved activity are identical on three surfaces."""

import pytest
from jsonschema import Draft202012Validator

from tests.support.result_delivery import assert_same_run_receipt
from tests.support.transports import SPECS, business, surface_calls


@pytest.mark.parametrize(
    "day,changed,checks",
    [
        ("2000-02-27", "110100", [(5, 2, True), (2, 3, False)]),
        ("2000-02-27", "010110", [(2, 3, True), (2, 6, True)]),
        ("2000-02-27", "111110", [(2, 3, False), (5, 2, None), (2, 6, None)]),
        ("2000-02-28", "110100", [(5, 2, None), (2, 3, None)]),
    ],
)
def test_control_and_activity_conditions_survive_all_transports(
    day, changed, checks, surface_calls
):
    spec = SPECS["sixyao"]
    payload = {
        "date": day,
        "time": "12:00:00",
        "zone": "Asia/Shanghai",
        "gua_code": "110110",
        "changed_code": changed,
        "focus_line": 3,
    }
    root = "liuyao_evidence.conditional_analysis"
    fields = [
        f"{root}.control_conditions",
        f"{root}.lines",
        f"{root}.classical_assessment",
        f"{root}.role_effects",
    ]
    options = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    response, protocol, code, local = surface_calls(
        spec, payload, projection={**options, "response_char_limit": 0}
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for output in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        detail = output["liuyao_evidence"]["conditional_analysis"]
        by_pair = {
            (c["source_position"], c["target_position"]): c
            for c in detail["control_conditions"]["controls"]
        }
        for source, target, expected in checks:
            assert by_pair[(source, target)].get("condition_match") is expected
            assert by_pair[(source, target)]["status"]
        if changed == "111110":
            assert (
                detail["lines"][4]["activity_condition_status"]
                == "activity_prerequisites_unresolved"
            )
        assert (
            detail["control_conditions"]["adjudication"]
            == "directed_control_conditions_only"
        )


def test_control_source_leaf_projects_without_sibling_requirements(surface_calls):
    spec = SPECS["sixyao"]
    payload = {
        "date": "2000-02-27",
        "time": "12:00:00",
        "gua_code": "110110",
        "changed_code": "110100",
    }
    field = "liuyao_evidence.conditional_analysis.control_conditions.source_sha256"
    response, protocol, code, local = surface_calls(
        spec,
        payload,
        params={"fields": field, "strict_fields": True, "include_snapshot_text": False},
        options={
            "fields": [field],
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=[
            "--fields",
            field,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for output in [response.json(), local, protocol.structured_content]:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(output)
        assert output["liuyao_evidence"]["conditional_analysis"][
            "control_conditions"
        ] == {
            "source_sha256": "caac111bc5c5b1c08fd27b3828e7cf6b5430503800f2427d8f2b28809022abaa"
        }


def test_control_matrix_and_interpretation_are_recovered_from_same_run(
    tmp_path, monkeypatch, surface_calls
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.support.result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "control-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    spec = SPECS["sixyao"]
    payload = {
        "date": "2000-02-27",
        "time": "12:00:00",
        "gua_code": "110110",
        "changed_code": "111110",
        "focus_line": 3,
    }
    response, protocol, code, local = surface_calls(
        spec, payload, projection={"response_char_limit": 8192}
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    for shaped in [response.json(), local, protocol.structured_content]:
        ref = shaped["result_delivery"]
        original = reconstruct(store, ref["result_id"])
        assert_same_run_receipt(store, shaped, original)
        path = "liuyao_evidence.conditional_analysis.control_conditions"
        controls = reconstruct(store, ref["result_id"], path)
        assert (
            controls
            == original["liuyao_evidence"]["conditional_analysis"]["control_conditions"]
        )
        assert "暗动扶源待审，不能据原候选认定已活动" in original["snapshot_text"]
        assert "第2爻卯克第3爻丑：静爻不克活动爻" in original["snapshot_text"]
        assert controls["scope"] in original["snapshot_text"]
