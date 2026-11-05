"""Independent calendar mapping and actual own-Si evidence on all interfaces."""

import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
)
from tests.liuyao.test_liuyao_clash_transports import all_surfaces
from tests.liuyao.test_liuyao_metal_own_si import BASE, CASES, check
from tests.liuyao.test_liuyao_transports import assert_same_run_receipt

PUBLIC = json.loads((BASE / "public-payloads.json").read_text())["rows"]


def test_own_si_public_mapping_uses_frozen_independent_calendars():
    for name, digest in json.loads(
        (BASE / "public-mapping-freeze.json").read_text()
    ).items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    data = json.loads((BASE / "public-payloads.json").read_text())
    assert (
        data["reference_sha256"]
        == hashlib.sha256(
            (
                Path(__file__).parents[1] / "data/bazi_all_terms_v1/reference.json"
            ).read_bytes()
        ).hexdigest()
    )
    assert (
        data["day_anchor_sha256"]
        == hashlib.sha256(
            (BASE.parent / "liuyao_scan_v3/naoj-day-reference.json").read_bytes()
        ).hexdigest()
    )
    assert len(PUBLIC) == len(CASES) == 11


@pytest.mark.parametrize("public", PUBLIC, ids=lambda x: x["id"])
@pytest.mark.parametrize("project", [False, True])
def test_actual_own_si_evidence_and_remaining_obstructions_on_all_interfaces(
    public, project, rest, tmp_path, capsys
):
    spec = SPECS["sixyao"]
    fields = (
        [
            "liuyao_evidence.conditional_analysis",
            "liuyao_evidence.calendar_conventions",
            "liuyao_evidence.rule_trace",
            "snapshot_text",
        ]
        if project
        else None
    )
    flags = ["--response-char-limit", "0"]
    params = [("response_char_limit", 0)]
    options = dict(response_char_limit=0)
    if fields:
        flags += ["--fields", *fields, "--strict-fields", "true"]
        params += [("fields", f) for f in fields] + [("strict_fields", "true")]
        options.update(fields=fields, strict_fields=True)
    http = rest.post(spec.rest_path, json=public["payload"], params=params)
    code, cli = call_cli(spec, public["payload"], tmp_path, capsys, flags=flags)
    mcp = asyncio.run(native(spec, public["payload"], **options))
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    results = [http.json(), cli, mcp.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    case = next(c for c in CASES if c["id"] == public["id"])
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        check(result["liuyao_evidence"]["conditional_analysis"], case)
        cal = result["liuyao_evidence"]["calendar_conventions"]
        assert (cal["month_branch"], cal["day_ganzhi"]) == (
            public["month"],
            public["day"],
        )
        prefix = f"第{case['position']}爻{case['branch']}金本位化巳："
        text = [x for x in result["snapshot_text"].splitlines() if x.startswith(prefix)]
        if case.get("expected_applicable", True):
            assert len(text) == 1
            if case["expected_own_growth"] is True:
                assert "本位化巳按长生" in text[0] and "其他反制另审" in text[0]
            else:
                assert "不能将本项认定为已克或已生" in text[0]
                assert "回头克受阻爻位：[6]" not in result["snapshot_text"]
            trace = next(
                t
                for t in result["liuyao_evidence"]["rule_trace"]
                if t["rule_id"] == "metal_actual_own_si_growth_qualification"
            )
            for path in trace["proof_paths"]:
                value = result
                for part in path.split("."):
                    value = value[int(part)] if isinstance(value, list) else value[part]
                assert (
                    value["source_path"] == path
                    and value["source_sha256"] == trace["source_sha256"]
                )
        else:
            assert text == []
    if evidence := os.environ.get("FATEBRIDGE_V35_EVIDENCE_DIR"):
        folder = Path(evidence)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{public['id']}-{project}.json").write_text(
            json.dumps(
                dict(
                    input=public["payload"],
                    outputs=dict(zip(["rest", "cli", "mcp"], results)),
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )


def test_own_si_false_leaf_survives_strict_projection_without_siblings(
    rest, tmp_path, capsys
):
    payload = {**PUBLIC[0]["payload"], "focus_line": 6}
    fields = [
        "liuyao_evidence.conditional_analysis.growth_conditions.focus.own_changed_si.qualified_back_control_condition"
    ]
    for result in all_surfaces(payload, fields, rest, tmp_path, capsys, budget=0):
        assert result["liuyao_evidence"]["conditional_analysis"] == {
            "growth_conditions": {
                "focus": {"own_changed_si": {"qualified_back_control_condition": False}}
            }
        }


def test_changed_si_focus_does_not_borrow_visible_metal_identity(
    rest, tmp_path, capsys
):
    payload = {**PUBLIC[0]["payload"], "focus_line": 6, "focus_kind": "changed"}
    for result in all_surfaces(payload, None, rest, tmp_path, capsys, budget=0):
        ca = result["liuyao_evidence"]["conditional_analysis"]
        assert ca["focus"]["selected"]["location"] == "changed"
        assert ca["focus"]["selected"]["branch"] == "巳"
        assert ca["growth_conditions"]["focus"] is None
        assert (
            ca["growth_conditions"]["lines"][5]["own_changed_si"]["condition_match"]
            is True
        )
        assert all(
            e["target_position"] == 6
            for e in ca["interaction_edges"]
            if e["source_kind"] == "changed" and e["source_position"] == 6
        )


def test_budgeted_own_si_proof_is_recovered_from_the_original_run(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from fatebridge.application.examples import suggested_fields
    from tests.integration.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "own-si-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(
        PUBLIC[0]["payload"],
        suggested_fields(SPECS["sixyao"]),
        rest,
        tmp_path,
        capsys,
        budget=8192,
    ):
        actual = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, actual)
        assert "snapshot_text" not in actual
        own = actual["liuyao_evidence"]["conditional_analysis"]["growth_conditions"][
            "lines"
        ][5]["own_changed_si"]
        assert (
            own["condition_match"] is True
            and own["qualified_back_control_condition"] is False
        )
