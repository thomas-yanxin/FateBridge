"""A named primary witness supports the twelve rows without repairing CNTS."""

import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest

from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.fixtures.surface_payloads import REST_POST_CASES

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/jinkou_waseda_strength_v1"
PIN = "17bade2ba4ee89f20cf1b3b8d71de75a6351275b595e7d438bd8a268c98e6628"


def reference():
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(CORPUS / "freeze.json") == PIN
    manifest = json.loads((CORPUS / "freeze.json").read_text())["files"]
    assert {p.name for p in CORPUS.iterdir()} == set(manifest) | {"freeze.json"}
    assert all(sha(CORPUS / n) == h for n, h in manifest.items())
    return json.loads((CORPUS / "readings.json").read_text())


REF = reference()


def output(**extra):
    spec = SPECS["jinkou"]
    payload = {**REST_POST_CASES[spec.rest_path](), **extra}
    fn, args, kw = spec.bind(spec.request_model.model_validate(payload))
    result = fn(*args, **kw)
    assert "error" not in result
    return result


def test_primary_witness_reaches_the_actual_main_and_annual_course():
    body = output(birth_year_ganzhi="甲子", year_fate_age=43, gender="男")
    main = body["jinkou"]["internal_strength"]["source_evidence"]
    assert "primary_witness" in main
    assert main["selected_witness"] == "online_transcription"
    assert main["primary_witness"]["source_sha256"] == REF["witness"]["source_sha256"]
    assert main["primary_witness"]["symbolic_example_count"] == 12
    assert main["witness_difference"]["original_elements"] == list("土土火木")
    assert main["witness_difference"]["primary_elements"] == list("土土火水")
    assert main["witness_difference"]["authorial_resolution"] is None
    course = body["jinkou"]["year_fate"]["course"]
    assert course["internal_strength"]["source_evidence"] == main
    assert body["jinkou"]["use_evidence"]["comprehensive_position"] is None
    assert main["complete_classical_acceptance"] is False
    assert main["note"] in body["snapshot_text"]


def test_source_url_cannot_be_forged_in_an_otherwise_correct_complete_result():
    from fatebridge.application.execution import OutputContractError, validate_output

    result = output()
    result["jinkou"]["internal_strength"]["source_evidence"][
        "source_url"
    ] = "https://example.invalid/forged"
    with pytest.raises(OutputContractError):
        validate_output(SPECS["jinkou"], result)


@pytest.mark.parametrize("case", REF["cases"], ids=lambda c: c["id"])
def test_every_original_waseda_phase_and_judgement(case):
    from fatebridge.core.metaphysics.jinkou_strength import internal_strength

    rows = [
        dict(label=p, element=e) for p, e in zip(REF["positions"], case["elements"])
    ]
    value = internal_strength(rows)
    assert value["anchor_element"] == case["stated_anchor"]
    assert value["powers"]["贵神"] == case["stated_god_power"]


@pytest.mark.parametrize("project", [False, True])
def test_actual_three_transports_keep_this_primary_source_and_old_conflict(
    project, rest, tmp_path, capsys
):
    spec = SPECS["jinkou"]
    payload = {
        **REST_POST_CASES[spec.rest_path](),
        "birth_year_ganzhi": "甲子",
        "year_fate_age": 43,
        "gender": "男",
    }
    fields = ["jinkou.internal_strength", "jinkou.year_fate", "jinkou.ruleset"]
    params = [("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    opts = {}
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
        opts.update(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=payload, params=params)
    protocol = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    evidence = http.json()["jinkou"]["internal_strength"]["source_evidence"]
    assert evidence["primary_witness"]["original_pdf_pages"] == list(range(54, 60))
    assert evidence["scan_collation_status"] == "unresolved_diagram_prose_difference"
    assert evidence["witness_difference"]["authorial_resolution"] is None


@pytest.mark.parametrize(
    "fault",
    [
        "hash",
        "count",
        "pages",
        "old_ground",
        "resolution",
        "complete",
        "trace_url",
        "trace_note",
        "trace_header_url",
        "trace_header_section",
        "independence",
        "full_volume",
        "missing",
    ],
)
def test_full_source_ledger_and_its_trace_reject_inventions(fault):
    from fatebridge.application.execution import OutputContractError, validate_output

    body = copy.deepcopy(output())
    source = body["jinkou"]["internal_strength"]["source_evidence"]
    if fault == "missing":
        del source["primary_witness"]
    elif fault == "hash":
        source["primary_witness"]["source_sha256"] = "0" * 64
    elif fault == "count":
        source["primary_witness"]["symbolic_example_count"] = 11
    elif fault == "pages":
        source["primary_witness"]["original_pdf_pages"] = [55]
    elif fault == "old_ground":
        source["witness_difference"]["original_elements"][-1] = "水"
    elif fault == "resolution":
        source["witness_difference"]["authorial_resolution"] = "printer_error"
    elif fault == "complete":
        source["complete_classical_acceptance"] = True
    elif fault == "independence":
        source["primary_witness"]["independent_transmission_adjudicated"] = True
    elif fault == "full_volume":
        source["primary_witness"]["full_volume_collation"] = True
    else:
        trace = next(
            t
            for t in body["jinkou"]["rule_trace"]
            if t["rule_id"] == "jinkou.internal_strength"
        )
        trace["result"] = copy.deepcopy(trace["result"])
        if fault in ("trace_header_url", "trace_header_section"):
            trace["source_url" if fault == "trace_header_url" else "source_section"] = (
                "forged source"
            )
        else:
            trace["result"]["source_evidence"][
                "source_url" if fault == "trace_url" else "note"
            ] = "forged source"
    with pytest.raises(OutputContractError):
        validate_output(SPECS["jinkou"], body)


def test_primary_source_can_be_projected_without_the_live_rows():
    spec = SPECS["jinkou"]
    spec.output_model.model_validate(
        {
            "jinkou": {
                "internal_strength": {
                    "source_evidence": {
                        "primary_witness": {
                            "source_sha256": REF["witness"]["source_sha256"]
                        }
                    }
                }
            }
        }
    )
