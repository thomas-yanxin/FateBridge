"""Actual three-interface local growth, retained obstructions and same-run SHA."""

import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_metal_moving import BASE, CASES, check
from tests.test_liuyao_transports import assert_same_run_receipt

PUBLIC = json.loads((BASE / "public-payloads.json").read_text())["rows"]
HIDDEN = json.loads((BASE / "hidden-engineering.json").read_text())


def test_public_mapping_bytes_frozen_without_changing_original_logical_inputs():
    frozen = json.loads((BASE / "public-mapping-freeze.json").read_text())[
        "files_sha256"
    ]
    for name, value in frozen.items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == value
    assert len(PUBLIC) == len(CASES) == 8


@pytest.mark.parametrize("public", PUBLIC, ids=lambda p: p["id"])
@pytest.mark.parametrize("project", [False, True])
def test_local_growth_and_original_obstructions_on_every_protocol(
    public, project, rest, tmp_path, capsys
):
    case = next(c for c in CASES if c["id"] == public["id"])
    spec = SPECS["sixyao"]
    fields = [
        "liuyao_evidence.conditional_analysis",
        "liuyao_evidence.calendar_conventions",
        "snapshot_text",
    ]
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    options = dict(response_char_limit=0)
    if project:
        params += [("fields", f) for f in fields] + [("strict_fields", "true")]
        flags += ["--fields", *fields, "--strict-fields", "true"]
        options.update(fields=fields, strict_fields=True)
    http = rest.post(spec.rest_path, json=public["payload"], params=params)
    code, cli = call_cli(spec, public["payload"], tmp_path, capsys, flags=flags)
    mcp = asyncio.run(native(spec, public["payload"], **options))
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    results = [http.json(), cli, mcp.structured_content]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
        assert not result.get("projection_warnings")
        check(result["liuyao_evidence"]["conditional_analysis"], case)
        cal = result["liuyao_evidence"]["calendar_conventions"]
        assert (
            cal["month_branch"] == public["month"]
            and cal["day_ganzhi"] == public["day"]
        )
        sentence = next(
            x
            for x in result["snapshot_text"].splitlines()
            if x.startswith("第6爻酉金：")
        )
        if case["expected_growth"] is True:
            assert "有独立根的实际动土生扶" in sentence
            assert "其他反制另审" in sentence
        else:
            assert "尚待裁定" in sentence
    if evidence := os.environ.get("FATEBRIDGE_V34_EVIDENCE_DIR"):
        d = Path(evidence)
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{public['id']}-{project}.json").write_text(
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


def test_hidden_subject_consumes_the_same_qualified_calendar_rule(
    rest, tmp_path, capsys
):
    results = all_surfaces(HIDDEN["payload"], None, rest, tmp_path, capsys, budget=0)
    for result in results:
        h = next(
            x
            for x in result["liuyao_evidence"]["conditional_analysis"][
                "hidden_conditions"
            ]
            if x["position"] == HIDDEN["hidden_position"]
            and x["branch"] == HIDDEN["hidden_branch"]
        )
        reception = h["reception"]
        assert reception["calendar_growth_rule_applied"] is True
        assert (
            reception["calendar_growth_ruleset_id"]
            == "zengshan_metal_si_moving_support_v34"
        )
        assert reception["moving_support"]["condition_match"] is True
        assert reception["moving_support"]["application_source_url"].endswith(
            "#page=110"
        )
        assert "跨章适用" in reception["moving_support"]["application_interpretation"]
        assert (
            HIDDEN["expected_source_position"]
            in reception["moving_support"]["successful_positions"]
        )
        strikes = next(
            x
            for x in h["obstructing_conditions"]
            if x["rule_id"] == "hidden_calendar_struck"
        )
        daily = [x for x in strikes["actors"] if x["location"] == "day"]
        assert daily and all(x["control_condition_match"] is False for x in daily)
        # The original fire-month opposition remains; a local day exception is no global release.
        monthly = [x for x in strikes["actors"] if x["location"] == "month"]
        assert monthly and strikes["qualified_matched"] is True


def test_budgeted_first_view_restores_same_run_without_recalculating(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from fatebridge.application.examples import suggested_fields
    from tests.test_result_delivery import reconstruct

    spec = SPECS["sixyao"]
    case = CASES[0]
    public = next(x for x in PUBLIC if x["id"] == case["id"])
    store = delivery.ResultStore(tmp_path / "moving-growth-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    for shaped in all_surfaces(
        public["payload"], suggested_fields(spec), rest, tmp_path, capsys, budget=8192
    ):
        restored = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, restored)
        assert "snapshot_text" not in restored
        check(restored["liuyao_evidence"]["conditional_analysis"], case)
