"""Fictional frozen instants, independent birth resolution and three surfaces."""

import asyncio
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "ren_runyear_birth_clock", ROOT / "scripts/ren/audit_ren_runyear_birth_clock.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()
CASES = REFERENCE["cases"]


def test_all_frozen_chronology_cases_keep_the_complete_denominator_and_scope():
    report = AUDIT.audit()
    assert (
        report["expected_count"]
        == report["compared_count"]
        == report["matched_count"]
        == 18
    )
    assert not report["calculation_errors"]
    assert not report["implementation_changed_during_audit"]
    assert report["selected_clock_checks_passed"]
    assert not report["goal_complete"]
    assert not report["full_supported_calendar_domain_certified"]
    assert not report["classical_acceptance_passed"]


def test_frozen_reference_edit_cannot_turn_into_a_pass(tmp_path):
    corpus = tmp_path / "reference"
    shutil.copytree(AUDIT.CORPUS, corpus)
    p = corpus / "reference.json"
    data = json.loads(p.read_text())
    data["cases"][3]["expected"]["birth_fold"] = 1
    p.write_text(json.dumps(data, ensure_ascii=False))
    with pytest.raises(ValueError, match="Frozen runyear clock source changed"):
        AUDIT.reference(corpus)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("project", [False, True])
def test_birth_instants_chronology_and_failures_agree_across_transports(
    case, project, rest, tmp_path, capsys
):
    spec = SPECS["liureng_runyear"]
    fields = ["runyear", "liureng.calendar_policy.civil_instant_utc"]
    params = [("response_char_limit", "0")]
    flags, options = ["--response-char-limit", "0"], {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ]
        options = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=case["input"], params=params)
    code, cli = call_cli(spec, case["input"], tmp_path, capsys, flags=flags)
    protocol = asyncio.run(native(spec, case["input"], **options))
    bodies = [http.json(), cli, protocol.structured_content]
    expected = case["expected"]
    if "error" in expected:
        assert http.status_code == 400 and code == 1 and protocol.is_error
        for body in bodies:
            assert expected["error"] in body["error"]
            assert "runyear" not in body and "liureng" not in body
        return
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert business(bodies[0]) == business(bodies[1]) == business(bodies[2])
    for body in bodies:
        runyear = body["runyear"]
        clock = runyear["birth_civil_clock"]
        assert clock["instant_utc"] == expected["birth_instant_utc"]
        assert clock["fold"] == expected["birth_fold"]
        assert clock["timezone"] == case["input"]["birth_timezone"]
        assert (
            body["liureng"]["calendar_policy"]["civil_instant_utc"]
            == expected["analysis_instant_utc"]
        )
        assert (
            runyear["age"] == expected["age"]
            and runyear["ganzhi"] == expected["ganzhi"]
        )
        assert clock["method"] == "validated_birth_civil_clock"
        if case["input"]["birth_timezone"] in REFERENCE["zones"]:
            assert clock["timezone_rules"]["tzif_sha256"] == AUDIT.sha(
                AUDIT.CORPUS / "tzif" / case["input"]["birth_timezone"]
            )
        if not project:
            assert expected["birth_instant_utc"] in body["snapshot_text"]
            assert "出生时间未做太阳钟偏移" in body["snapshot_text"]


def test_birth_fold_does_not_move_analysis_board_or_solar_instant():
    base = dict(CASES[0]["input"])
    outputs = [
        AUDIT.calculate({**base, "birth_utc_offset": offset})
        for offset in ("-04:00", "-05:00")
    ]
    assert outputs[0]["liureng"] == outputs[1]["liureng"]
    assert outputs[0]["four_pillars"] == outputs[1]["four_pillars"]
    assert (
        outputs[0]["runyear"]["birth_civil_clock"]["instant_utc"]
        != outputs[1]["runyear"]["birth_civil_clock"]["instant_utc"]
    )
    assert outputs[0]["runyear"]["age"] == outputs[1]["runyear"]["age"]


def test_birth_utc_order_is_preserved_with_analysis_solar_clock_and_unknown_gender():
    case = CASES[3]
    plain = AUDIT.calculate(case["input"])
    solar = AUDIT.calculate(
        {
            **case["input"],
            "use_true_solar_time": True,
            "analysis_longitude": -82.3667,
            "gender": "未知",
        }
    )
    assert "error" not in solar
    assert (
        solar["runyear"]["birth_civil_clock"] == plain["runyear"]["birth_civil_clock"]
    )
    assert (
        solar["liureng"]["calendar_policy"]["civil_instant_utc"]
        == case["expected"]["analysis_instant_utc"]
    )
    assert solar["runyear"]["status"] == "not_calculated"
    assert solar["runyear"]["ganzhi"] is None
