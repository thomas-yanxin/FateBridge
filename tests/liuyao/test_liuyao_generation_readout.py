"""Read the returned source, receiver, specific exclusion and final path."""

import json
from pathlib import Path

import pytest

from fatebridge.core.local_techniques.sixyao import build_sixyao_result

BASE = Path(__file__).parents[1] / "fixtures/liuyao_generation_readout_v33"
CASES = json.loads((BASE / "cases.json").read_text(encoding="utf-8"))["cases"]


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
    return text


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_generation_edge_snapshot_follows_all_returned_gates(case):
    assert_returned_gate_readout(build_sixyao_result(**case["payload"]), case)


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
