"""Textual uncertainty survives same-course output and public delivery."""

import copy
import hashlib
import json
import shutil
from dataclasses import replace

import pytest
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.core.output_jinkou_breaks import JinkouBranchBreaks
from scripts.ren.audit_jinkou_break_witnesses import CORPUS, audit, reference
from tests.ren.test_jinkou_branch_breaks import PAYLOAD, SPEC, course, raw
from tests.support.transports import AS_OF, business, rest, surface_calls


def test_exact_reading_keeps_one_yin_and_the_unread_witness():
    expected = reference()
    for role in ("primary", "natal_course", "year_fate"):
        board = course(raw(), role)
        evidence = board["branch_breaks"]["witness_evidence"]
        assert evidence == expected
        assert "亥破寅破巳" in evidence["witnesses"][0]["literal_break_sequence"]
        assert "寅寅" not in evidence["witnesses"][0]["literal_break_sequence"]
        assert evidence["witnesses"][1]["literal_break_sequence"] is None
        assert evidence["witnesses"][1]["extra_phrase_present"] is None
        assert all(w["enumerated_pair_count"] is None for w in evidence["witnesses"])
        assert evidence["readable_corroboration_count"] == 1
        assert evidence["unresolved_witness_count"] == 1
        assert evidence["reader_count"] == 1
        assert evidence["author_intent"] is evidence["effective_break"] is None
        assert evidence["effect_direction"] is None
        assert evidence["independent_transmission_established"] is False
        assert evidence["whole_book_conformance"] is False
        assert board["ruleset"]["version"] == "1.16.0"


@pytest.mark.parametrize("change", ["image", "evidence", "joint"])
def test_frozen_pages_and_reading_cannot_be_relabelled(tmp_path, change):
    target = tmp_path / "witness"
    shutil.copytree(CORPUS, target)
    name = "waseda-48.jpg" if change == "image" else "evidence.json"
    path = target / name
    path.write_bytes(path.read_bytes() + b" ")
    if change == "joint":
        manifest = json.loads((target / "freeze.json").read_text())
        manifest["files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (target / "freeze.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Frozen textual-witness"):
        reference(target)


def test_sparse_projection_does_not_fill_missing_readings():
    partial = dict(
        witness_evidence=dict(witnesses=[{}, dict(extra_phrase_present=None)])
    )
    assert (
        JinkouBranchBreaks.model_validate(partial).model_dump(exclude_unset=True)
        == partial
    )
    for flag in (False, True):
        with pytest.raises(ValidationError):
            JinkouBranchBreaks.model_validate(
                dict(
                    witness_evidence=dict(
                        witnesses=[{}, dict(extra_phrase_present=flag)]
                    )
                )
            )


@pytest.mark.parametrize("project", [False, True])
def test_three_ports_preserve_both_witnesses_in_all_courses(project, surface_calls):
    fields = [
        "jinkou.branch_breaks.witness_evidence",
        "jinkou.natal_course.course.branch_breaks.witness_evidence",
        "jinkou.year_fate.course.branch_breaks.witness_evidence",
    ]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags, options = ["--response-char-limit", "0"], {}
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
    http, protocol, code, cli = surface_calls(
        SPEC, PAYLOAD, params=params, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(cli) == business(protocol.structured_content)
    )
    for body in (http.json(), cli, protocol.structured_content):
        for role in ("primary", "natal_course", "year_fate"):
            assert (
                course(body, role)["branch_breaks"]["witness_evidence"] == reference()
            )


@pytest.mark.parametrize("role", ["primary", "natal_course", "year_fate"])
@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize(
    "fault",
    ["missing", "unread_as_false", "duplicate_yin", "whole_book", "wrong_source"],
)
def test_faults_are_rejected_before_projection_on_three_ports(
    role, project, fault, monkeypatch, surface_calls
):
    bad = copy.deepcopy(raw())
    block = course(bad, role)["branch_breaks"]
    evidence = block["witness_evidence"]
    if fault == "missing":
        del block["witness_evidence"]
    elif fault == "unread_as_false":
        evidence["witnesses"][1]["extra_phrase_present"] = False
    elif fault == "duplicate_yin":
        witness = evidence["witnesses"][0]
        witness["literal_break_sequence"] = witness["literal_break_sequence"].replace(
            "亥破寅破巳", "亥破寅寅破巳"
        )
    elif fault == "whole_book":
        evidence["whole_book_conformance"] = True
    else:
        evidence["witnesses"][0]["source_sha256"] = "invented"
    with pytest.raises(execution.OutputContractError):
        execution.validate_output(SPEC, bad)
    original = execution.execute_spec

    def broken(spec, request):
        if spec.key == "jinkou":
            spec = replace(spec, bind=lambda _: (lambda: copy.deepcopy(bad), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    params = dict(as_of=AS_OF, response_char_limit="0")
    flags, options = ["--response-char-limit", "0"], {}
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
        options = dict(fields=["analysis_type"], strict_fields=True)
    http, protocol, code, cli = surface_calls(
        SPEC, PAYLOAD, params=params, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert cli["error_code"] == "internal_error"


def test_joint_runtime_asset_and_validator_rewrite_is_not_a_source_oracle(
    monkeypatch, tmp_path
):
    import fatebridge.core.metaphysics.jinkou_break_witnesses as production

    evidence = reference()
    evidence["witnesses"][0]["source_url"] = "https://invalid.example/fabricated.pdf"
    asset = tmp_path / "fabricated.json"
    asset.write_text(json.dumps(evidence))
    monkeypatch.setattr(production, "ASSET", asset)
    monkeypatch.setattr(
        production, "ASSET_SHA256", hashlib.sha256(asset.read_bytes()).hexdigest()
    )
    result = audit()
    assert result["bounded_textual_evidence_passed"] is False
    assert len(result["failures"]) == 1728
    assert result["independent_evidence"] == reference()
