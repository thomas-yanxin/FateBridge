"""The actual focused source and target remain distinct in every delivery."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core.local_techniques.sixyao import build_sixyao_result
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest
from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_transports import assert_same_run_receipt

REFERENCE = Path(__file__).parent / "fixtures/liuyao_focus_v25"
CASES = json.loads((REFERENCE / "cases.json").read_text())["cases"]
ROOT = "liuyao_evidence.conditional_analysis.generation_conditions"


def payload(case):
    return {
        **{
            key: case[key] for key in ("date", "gua_code", "changed_code", "focus_line")
        },
        "time": "12:00:00",
        "zone": "Asia/Shanghai",
        "timing_days": 0,
    }


def assert_focus(detail, case):
    focus = detail["focus"]
    assert focus["source_condition_match"] is case["source"]
    assert focus["target_reception_condition"] is case["target"]
    source = detail["sources"][case["focus_line"] - 1]
    assert focus["source_condition_match"] is source["condition_match"]
    assert focus["source_status"] == source["status"]
    assert focus["source_condition_path"] == source["source_path"]
    if case["source"] is False:
        assert "向外生扶受阻" in focus["source_explanation"]
        assert "回头克" in focus["source_explanation"]
    elif case["source"] is True:
        assert "来源资格已匹配" in focus["source_explanation"]
    else:
        assert "来源资格仍待审" in focus["source_explanation"]
    assert "作为受生爻" in focus["target_explanation"]


def test_focus_examples_and_initial_annotation_error_are_frozen():
    frozen = json.loads((REFERENCE / "case-freeze.json").read_text())
    for name, digest in frozen["files_sha256"].items():
        assert hashlib.sha256((REFERENCE / name).read_bytes()).hexdigest() == digest
    initial = json.loads((REFERENCE / "cases-initial.json").read_text())["cases"]
    assert initial[2]["focus_line"] == 5 and CASES[2]["focus_line"] == 6


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_focused_source_target_and_explanation_follow_the_same_calculation(case):
    result = build_sixyao_result(**payload(case))
    detail = result["liuyao_evidence"]["conditional_analysis"]["generation_conditions"]
    assert_focus(detail, case)
    assert detail["focus"]["source_explanation"] in result["snapshot_text"]
    assert detail["focus"]["target_explanation"] in result["snapshot_text"]


@pytest.mark.parametrize(
    "extra",
    [
        {
            "gua_code": "100000",
            "changed_code": "100100",
            "focus_kind": "changed",
            "focus_line": 4,
        },
        {
            "gua_code": "011111",
            "changed_code": "011111",
            "focus_kind": "hidden",
            "focus_line": 2,
        },
        {"focus_kind": "day", "focus_line": None},
        {"focus_kind": "month", "focus_line": None},
        {"focus_line": None},
    ],
)
def test_other_focus_kinds_do_not_borrow_visible_parent_generation(extra):
    result = build_sixyao_result(**{**payload(CASES[0]), **extra})
    analysis = result["liuyao_evidence"]["conditional_analysis"]
    assert analysis["generation_conditions"]["focus"] is None
    assert "本爻向外生扶的来源资格已匹配" not in result["snapshot_text"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
@pytest.mark.parametrize("leaf_only", [False, True])
def test_qualified_focus_survives_strict_projection_on_all_three_surfaces(
    case, leaf_only, rest, tmp_path, capsys
):
    fields = (
        [
            ROOT + ".focus." + part
            for part in ["source_condition_match", "target_reception_condition"]
        ]
        if leaf_only
        else [ROOT]
    )
    outputs = all_surfaces(payload(case), fields, rest, tmp_path, capsys)
    for output in outputs:
        Draft202012Validator(SPECS["sixyao"].output_model.model_json_schema()).validate(
            output
        )
        detail = output["liuyao_evidence"]["conditional_analysis"][
            "generation_conditions"
        ]
        if leaf_only:
            assert detail == {
                "focus": {
                    "source_condition_match": case["source"],
                    "target_reception_condition": case["target"],
                }
            }
        else:
            assert_focus(detail, case)
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_focused_qualification_is_recovered_from_the_same_hash_verified_run(
    case, rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "focused-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(
        payload(case), None, rest, tmp_path, capsys, budget=8192
    ):
        result_id = shaped["result_delivery"]["result_id"]
        original = reconstruct(store, result_id)
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"][
            "generation_conditions"
        ]
        assert_focus(detail, case)
        assert reconstruct(store, result_id, ROOT + ".focus") == detail["focus"]


def test_misspelled_new_source_leaf_is_rejected_consistently(rest, tmp_path, capsys):
    spec = SPECS["sixyao"]
    field = ROOT + ".focus.source_conditon_match"
    response = rest.post(
        spec.rest_path,
        json=payload(CASES[0]),
        params={"fields": field, "strict_fields": "true"},
    )
    code, cli = call_cli(
        spec,
        payload(CASES[0]),
        tmp_path,
        capsys,
        flags=["--fields", field, "--strict-fields", "true"],
    )
    protocol = asyncio.run(
        native(spec, payload(CASES[0]), fields=[field], strict_fields=True)
    )
    assert response.status_code == 422 and code == 1 and protocol.is_error
    for result in [response.json(), cli, protocol.structured_content]:
        assert result["issues"] == [{"path": field, "code": "unknown_projection_path"}]
