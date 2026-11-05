"""Public cautions use final scoped activity; no second triad calculation."""

import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_liuyao_clash_transports import all_surfaces
from tests.test_liuyao_roles import classical
from tests.test_liuyao_transports import assert_same_run_receipt

BASE = Path(__file__).parent / "fixtures/liuyao_explanation_v30"
CASES = json.loads((BASE / "cases.json").read_text())["cases"]


def assert_caution(detail, position, expected):
    row = detail["lines"][position - 1]
    fact = detail["penalty_conditions"]["lines"][position - 1]
    assert fact["condition_match"] is expected
    cautions = [text for text in row["stage_cautions"] if "刑" in text]
    if expected is False:
        assert cautions == []
        return
    assert len(cautions) == 1
    assert "刑的总作用未裁定" in cautions[0]
    if expected is None:
        assert "活动资格待审" in cautions[0]
        assert "三支条件已核" not in cautions[0]
    else:
        assert "三支条件已核" in cautions[0]
        assert fact["effect_condition_match"] is None


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_final_scope_and_caution_agree(case):
    result = classical(case)
    assert_caution(result, case["position"], case["expected_presence"])
    for fact in result["penalty_conditions"]["lines"]:
        assert_caution(result, fact["position"], fact["condition_match"])
    if case["id"] == "own-yin-day-relief-still-excluded":
        gate = result["back_generation_conditions"]["sources"][0]
        assert gate["raw_condition_match"] is None
        assert gate["month_break_qualified_gate"] is True
        assert gate["condition_match"] is False
        assert "本位变寅" in result["lines"][0]["stage_cautions"][0]


def test_case_protocol_and_primary_source_stay_frozen():
    for name, digest in json.loads((BASE / "freeze.json").read_text())[
        "sha256"
    ].items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    protocol = json.loads((BASE / "adjudication.json").read_text())
    pdf = BASE.parent / "liuyao_scan_v3/sources/nlc-1925-zengshan.pdf"
    assert (
        hashlib.sha256(pdf.read_bytes()).hexdigest() == protocol["primary_pdf_sha256"]
    )


PUBLIC = [
    ("static-own-chart-label-not-actual", "2000-06-25"),
    ("pending-dark-shen", "2000-06-25"),
    ("qualified-dark-shen", "2000-04-26"),
    ("own-yin-day-relief-still-excluded", "2000-08-24"),
    ("own-yin-no-yin-day", "2000-06-19"),
]


@pytest.mark.parametrize("case_id,day", PUBLIC)
@pytest.mark.parametrize("project", [False, True])
def test_caution_and_snapshot_use_same_final_context(
    case_id, day, project, rest, tmp_path, capsys
):
    case = next(c for c in CASES if c["id"] == case_id)
    spec = SPECS["sixyao"]
    payload = dict(
        date=day,
        time="12:00:00",
        zone="Asia/Shanghai",
        gua_code=case["base_code"],
        changed_code=case["changed_code"],
        focus_line=case["position"],
        timing_days=0,
    )
    root = "liuyao_evidence.conditional_analysis"
    fields = [
        root + "." + part
        for part in ["lines", "penalty_conditions", "back_generation_conditions"]
    ] + ["snapshot_text"]
    flags = ["--response-char-limit", "0"]
    params = [("response_char_limit", 0)]
    options = dict(response_char_limit=0)
    if project:
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "true",
        ]
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "true"),
        ]
        options.update(fields=fields, strict_fields=True, include_snapshot_text=True)
    http = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    mcp = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [http.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for body in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(body)
        detail = body["liuyao_evidence"]["conditional_analysis"]
        assert_caution(detail, case["position"], case["expected_presence"])
        for fact, row in zip(detail["penalty_conditions"]["lines"], detail["lines"]):
            warnings = [text for text in row["stage_cautions"] if "刑" in text]
            if warnings:
                assert (
                    f"第{row['position']}爻巳火：{warnings[0]}。"
                    in body["snapshot_text"]
                )
            else:
                assert (
                    f"第{row['position']}爻巳火：巳寅申三支"
                    not in body["snapshot_text"]
                )
        assert not body.get("projection_warnings")
    evidence = os.environ.get("FATEBRIDGE_V30_EVIDENCE_DIR")
    if evidence:
        folder = Path(evidence)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{case_id}-{project}.json").write_text(
            json.dumps(
                dict(input=payload, outputs=dict(zip(["rest", "cli", "mcp"], outputs))),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )


def test_same_run_full_hash_preserves_unknown_caution(
    rest, tmp_path, capsys, monkeypatch
):
    import fatebridge.api as api
    from fatebridge.application import result_delivery as delivery
    from tests.test_result_delivery import reconstruct

    store = delivery.ResultStore(tmp_path / "same-run-results")
    monkeypatch.setattr(delivery, "RESULT_STORE", store)
    monkeypatch.setattr(api, "RESULT_STORE", store)
    payload = dict(
        date="2000-06-25",
        time="12:00:00",
        gua_code="000111",
        changed_code="000111",
        focus_line=2,
        timing_days=0,
    )
    for shaped in all_surfaces(payload, None, rest, tmp_path, capsys, budget=8192):
        original = reconstruct(store, shaped["result_delivery"]["result_id"])
        assert_same_run_receipt(store, shaped, original)
        detail = original["liuyao_evidence"]["conditional_analysis"]
        assert_caution(detail, 2, None)
        path = detail["penalty_conditions"]["lines"][1]["source_path"]
        assert (
            reconstruct(store, shaped["result_delivery"]["result_id"], path)
            == detail["penalty_conditions"]["lines"][1]
        )
