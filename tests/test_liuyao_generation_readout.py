"""Read the returned source, receiver, specific exclusion and final path."""

import gzip
import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from fatebridge.core.local_techniques.sixyao import build_sixyao_result

BASE = Path(__file__).parent / "fixtures/liuyao_generation_readout_v33"
CASES = json.loads((BASE / "cases.json").read_text(encoding="utf-8"))["cases"]
BEFORE = json.loads((BASE / "before-payloads.json").read_text(encoding="utf-8"))["rows"]


def edge(result, case):
    return next(
        r
        for r in result["liuyao_evidence"]["conditional_analysis"][
            "generation_conditions"
        ]["generations"]
        if (r["source_position"], r["target_position"])
        == (case["source_position"], case["target_position"])
    )


def edge_text(result, case):
    p = edge(result, case)
    prefix = f"第{p['source_position']}爻{p['source_branch']}生第{p['target_position']}爻{p['target_branch']}："
    lines = [
        line for line in result["snapshot_text"].splitlines() if line.startswith(prefix)
    ]
    assert len(lines) <= 1
    return lines[0] if lines else None


def assert_returned_gate_readout(result, case, *, check_snapshot=True):
    p = edge(result, case)
    assert {k: p.get(k) for k in case["expected"]} == case["expected"]
    cal = result["liuyao_evidence"]["calendar_conventions"]
    assert cal["month_branch"] == case["expected_month"]
    assert cal["day_ganzhi"] == case["expected_day_ganzhi"]
    old = next(r for r in BEFORE if r["id"] == case["id"])
    assert p["status"] == old["pair"]["status"]
    note = p.get("qualification_explanation")
    if case["expected_qualification_note"] == "excluded":
        assert isinstance(note, str)
        assert "巳寅申限定条款排除这一路寅木生扶" in note
        assert "本条生扶路径条件未匹配" in note
        assert "刑的总作用仍未裁定" in note
        assert p.get("benefit_now") is False
    else:
        assert note is None
    if not check_snapshot:
        return note
    text = edge_text(result, case)
    if note is not None:
        assert text is not None and text.endswith(note)
    else:
        assert text == edge_text(old["output"], case)
    return text


TERM_CLOCK_KEYS = ("datetime_with_offset", "timezone", "fold", "utc_offset_seconds")


def validate_added_term_clock_metadata(result):
    """Validate known serialization additions before the original full equality.

    These four fixed Shanghai cases have unambiguous modern wall times. This
    does not normalize arbitrary fields, alter any instant, or certify historic
    timezone behavior. Unknown additions still fail the full-result comparison.
    """
    context = result["calendar_context"]
    paths = [
        ("current_solar_term",),
        ("next_solar_term",),
        ("bazi_month_boundary", "start_term"),
        ("bazi_month_boundary", "next_term"),
        ("lunar_calendar", "previous_jieqi"),
        ("lunar_calendar", "next_jieqi"),
    ]
    for path in paths:
        term = context
        for key in path:
            term = term[key]
        if not any(key in term for key in TERM_CLOCK_KEYS):
            continue
        assert all(key in term for key in TERM_CLOCK_KEYS)
        assert context["timezone"] == "Asia/Shanghai"
        wall = datetime.fromisoformat(term["datetime"])
        assert wall.tzinfo is None and wall.year == 2000
        expected = wall.replace(tzinfo=ZoneInfo(context["timezone"]))
        assert term["timezone"] == context["timezone"]
        assert type(term["fold"]) is int and term["fold"] == expected.fold == 0
        assert type(term["utc_offset_seconds"]) in (int, float)
        assert term["utc_offset_seconds"] == expected.utcoffset().total_seconds()
        assert term["datetime_with_offset"] == expected.isoformat()
        for key in TERM_CLOCK_KEYS:
            term.pop(key)


def test_generation_readout_frozen_inputs_preserved():
    freeze = json.loads((BASE / "freeze.json").read_text(encoding="utf-8"))[
        "files_sha256"
    ]
    for name, digest in freeze.items():
        assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest
    raw = json.loads((BASE / "raw-freeze.json").read_text(encoding="utf-8"))
    assert (
        hashlib.sha256((BASE / "before-payloads.json").read_bytes()).hexdigest()
        == raw["before_payloads_sha256"]
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_generation_edge_snapshot_follows_all_returned_gates(case):
    assert_returned_gate_readout(build_sixyao_result(**case["payload"]), case)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_generation_readout_keeps_every_original_calculation_value(case):
    result = build_sixyao_result(**case["payload"])
    path = BASE.parent / "architecture_refactor_v1/sixyao-generation-before.json.gz"
    raw = path.read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "9957ee418987a5872a11885d2255b51cd4e2bb8bec0c0e8dcedf23cf0f9dc60b"
    )
    frozen = json.loads(gzip.decompress(raw))
    assert (
        hashlib.sha256((BASE / "cases.json").read_bytes()).hexdigest()
        == frozen["source_sha256"]
    )
    before = frozen["rows"][case["id"]]
    assert before["payload"] == case["payload"]
    assert result == before["output"]
    historical = next(r["output"] for r in BEFORE if r["id"] == case["id"])
    assert (
        historical["liuyao_evidence"]["conditional_analysis"]["ruleset_version"]
        == "2.18.0"
    )
    assert (
        result["liuyao_evidence"]["conditional_analysis"]["ruleset_version"] == "2.20.0"
    )
    assert_returned_gate_readout(result, case)
    # Retain every clock serialization tamper rejection at the original
    # instant. The later TT point receipts already predate this repair.
    for key, wrong in {
        "datetime_with_offset": "2000-01-01T00:00:00+00:00",
        "timezone": "UTC",
        "fold": 1,
        "utc_offset_seconds": 0,
    }.items():
        altered = deepcopy(result)
        term = altered["calendar_context"]["current_solar_term"]
        expected = datetime.fromisoformat(term["datetime"]).replace(
            tzinfo=ZoneInfo("Asia/Shanghai")
        )
        term.update(
            datetime_with_offset=expected.isoformat(),
            timezone="Asia/Shanghai",
            fold=0,
            utc_offset_seconds=expected.utcoffset().total_seconds(),
        )
        term[key] = wrong
        with pytest.raises(AssertionError):
            validate_added_term_clock_metadata(altered)
    validate_added_term_clock_metadata(deepcopy(result))
    assert result == before["output"]


@pytest.mark.parametrize(
    "benefit, phrase", [(False, "条件未匹配"), (None, "条件仍待审")]
)
def test_pending_specific_qualification_does_not_erase_another_failed_gate(
    benefit, phrase
):
    # Readout-only DTO states, not asserted as extra actual charts or accuracy samples.
    from fatebridge.core.liuyao_generation import pair_qualification_explanation

    note = pair_qualification_explanation(
        {"target_yin_generation_allowed": None, "benefit_now": benefit}
    )
    assert "活动前提待审" in note
    assert phrase in note
    assert "刑的总作用仍未裁定" in note


@pytest.mark.parametrize("benefit", [False, None, True])
def test_unrestricted_pair_keeps_existing_explanation(benefit):
    from fatebridge.core.liuyao_generation import pair_qualification_explanation

    assert (
        pair_qualification_explanation(
            {"target_yin_generation_allowed": True, "benefit_now": benefit}
        )
        is None
    )


def test_partial_generation_contract_accepts_explanation_without_siblings():
    from fatebridge.core.output_liuyao_generation import GenerationPair

    p = GenerationPair.model_validate(
        {"qualification_explanation": "本条生扶路径条件未匹配"}
    )
    assert p.qualification_explanation == "本条生扶路径条件未匹配"


def test_partial_generation_contract_rejects_wrong_explanation_type():
    from pydantic import ValidationError

    from fatebridge.core.output_liuyao_generation import GenerationPair

    with pytest.raises(ValidationError):
        GenerationPair.model_validate({"qualification_explanation": False})
