"""Witness differences and unsupported conclusions must survive transport."""

import asyncio
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from tests.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.test_agentic_nested_outputs import (
    test_nested_fact_faults_are_internal_failures_on_all_surfaces as reject_fault,
)
from tests.test_ren_transports import PAYLOAD

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "strength_scan_audit", ROOT / "scripts/audit_jinkou_strength.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_raw_scan_failure_and_old_witness_remain_distinct():
    report = AUDIT.audit()
    assert report["scan_case_count"] == 12
    assert report["scan_matched_count"] == 11
    assert report["older_online_matched_count"] == 12
    assert [c["id"] for c in report["scan_failures"]] == ["S01"]
    failure = report["scan_failures"][0]
    assert failure["raw_diagram_elements"] == list("土土火木")
    assert failure["expected_anchor"] == "土"
    assert failure["actual_anchor"] is None
    assert failure["actual_candidates"] == ["火", "木"]
    assert failure["expected_god_power"] == "旺"
    assert failure["actual_god_power"] is None
    assert len(report["witness_row_differences"]) == 1
    assert report["raw_scan_excerpt_conformance"] is False
    assert report["classical_acceptance_passed"] is False
    assert report["goal_complete"] is False
    assert report["implementation_unchanged_during_audit"]


def test_modified_primary_label_rejected(tmp_path):
    corpus = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, corpus)
    path = corpus / "reference.json"
    ref = json.loads(path.read_text())
    ref["cases"][0]["elements"][-1] = "水"
    path.write_text(json.dumps(ref, ensure_ascii=False))
    with pytest.raises(ValueError, match="Frozen strength source changed"):
        AUDIT.reference(corpus)


@pytest.mark.parametrize("project", [False, True])
def test_actual_witness_and_correct_locator_on_all_surfaces(
    project, rest, tmp_path, capsys
):
    spec = SPECS["jinkou"]
    payload = {**PAYLOAD, "di_fen": "子"}
    fields = ["jinkou.internal_strength", "jinkou.use_evidence", "jinkou.ruleset"]
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=payload, params=params)
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, payload, **options))
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    bodies = [http.json(), cli, protocol.structured_content]
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        spec.output_model.model_validate(body)
        board = body["jinkou"]
        evidence = board["internal_strength"]["source_evidence"]
        assert evidence["selected_witness"] == "online_transcription"
        assert (
            evidence["scan_collation_status"] == "unresolved_diagram_prose_difference"
        )
        assert evidence["daily_five_states_adjudicated"] is False
        assert evidence["complete_classical_acceptance"] is False
        assert evidence["scan_source_sha256"] == AUDIT.reference()["source_sha256"]
        assert board["use_evidence"]["source_evidence"]["no_control_pdf_page"] == 18
        assert board["use_evidence"]["source_evidence"]["no_control_footer_page"] == 17
        assert board["use_evidence"]["comprehensive_position"] is None
        assert board["ruleset"]["version"] == "1.16.0"
        if not project:
            assert evidence["note"] in body["snapshot_text"]
            trace = next(
                t
                for t in board["rule_trace"]
                if t["rule_id"] == "jinkou.internal_strength"
            )
            assert trace["result"] == board["internal_strength"]


@pytest.mark.parametrize(
    "payload",
    [
        {"jinkou": {"use_evidence": {"comprehensive_position": "贵神"}}},
        {"jinkou": {"use_evidence": {"comprehensive_position": False}}},
        {
            "jinkou": {
                "internal_strength": {
                    "source_evidence": {"daily_five_states_adjudicated": True}
                }
            }
        },
        {
            "jinkou": {
                "internal_strength": {
                    "source_evidence": {"complete_classical_acceptance": True}
                }
            }
        },
        {
            "jinkou": {
                "use_evidence": {
                    "source_evidence": {"combined_priority_status": "adjudicated"}
                }
            }
        },
    ],
)
def test_unsupported_certainty_is_internal_error_before_projection(
    payload, rest, monkeypatch, tmp_path, capsys
):
    reject_fault("jinkou", payload, rest, monkeypatch, tmp_path, capsys)
