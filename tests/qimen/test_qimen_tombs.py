"""Unadopted tomb readings must remain visible without changing formal rules."""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.local_techniques.qimen import build_qimen_with_options
from fatebridge.core.qimen_tombs import describe_wonder_tombs, palace_wonder_tombs
from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim
from fatebridge.validation.qimen import verify_qimen_pattern_quotes
from fatebridge.validation.qimen_tombs import audit_wonder_tomb_clauses
from tests.qimen.test_qimen_depth import fixed_board, seed

BUNDLE = Path(__file__).parents[1] / "fixtures/qimen_classical_v9"
REFERENCE = json.loads((BUNDLE / "sources-and-tomb-clauses.json").read_text())


def test_clause_audit_passes_observations_but_retains_two_unresolved_priorities():
    report = audit_wonder_tomb_clauses(BUNDLE)
    assert report["implementation_disagreements"] == []
    assert report["selected_explicit_rule_cells"] == 3
    assert report["unadopted_literal_candidate_cells"] == 3
    assert report["finite_stem_palace_comparisons"] == 24
    assert len(report["unresolved_source_priorities"]) == 2
    assert report["independent_original_chart_examples_added"] == 0
    assert not report["source_reading_adjudicated"]


@pytest.mark.parametrize("stem", list("乙丙丁"))
@pytest.mark.parametrize("trigram", list("坎坤震巽乾兑艮离"))
def test_literal_candidate_is_compared_but_never_promoted(stem, trigram):
    result = palace_wonder_tombs(trigram, [stem])
    s = REFERENCE["clauses"]["wangzhang_enumeration"]["mapping"][stem]
    c = REFERENCE["clauses"]["opening_sentence_literal_candidate"]["mapping"][stem]
    assert result["selected_matched_stems"] == ([stem] if s == trigram else [])
    assert result["unadopted_literal_candidate_matched_stems"] == (
        [stem] if c == trigram else []
    )
    assert result["disputed_stems_at_this_palace"] == (
        [stem] if (s == trigram) != (c == trigram) else []
    )
    assert not result["candidate_adopted"] and not result["source_priority_resolved"]


def test_agreement_on_bing_does_not_adjudicate_yi_and_ding():
    result = palace_wonder_tombs("乾", ["丙", "丁"])
    assert result["selected_matched_stems"] == ["丙"]
    assert result["unadopted_literal_candidate_matched_stems"] == ["丙", "丁"]
    assert result["disputed_stems_at_this_palace"] == ["丁"]
    assert not result["source_priority_resolved"]
    profile = describe_wonder_tombs()
    profile["selected_stem_trigrams"]["乙"] = "乾"
    profile["unadopted_literal_candidate"]["adopted"] = True
    assert describe_wonder_tombs()["selected_stem_trigrams"]["乙"] == "坤"
    assert not describe_wonder_tombs()["unadopted_literal_candidate"]["adopted"]


@pytest.mark.parametrize(
    "dun,ju", [(d, j) for d in ("阳遁", "阴遁") for j in range(1, 10)]
)
def test_formal_patterns_keep_named_enumeration_and_hosted_stems(monkeypatch, dun, ju):
    from fatebridge.core.metaphysics.common import SEXAGENARY_CYCLE

    selected = REFERENCE["clauses"]["wangzhang_enumeration"]["mapping"]
    for hour in SEXAGENARY_CYCLE:
        q = fixed_board(monkeypatch, {"dun": dun, "ju": ju, "hour": hour})
        expected = {
            (p["name"], s)
            for p in q["palaces"]
            if p["trigram"] != "中"
            for s in p["heaven_stems"]
            if selected.get(s) == p["trigram"]
        }
        actual = {
            (p["palace"], p["facts"]["heaven_stem"])
            for p in q["patterns"]
            if p["rule_id"] == "wonder_tomb"
        }
        assert actual == expected
        for p in q["patterns"]:
            if p["rule_id"] == "wonder_tomb":
                assert not p["qualification"]["tomb_evidence"]["candidate_adopted"]
                assert not p["qualification"]["tomb_evidence"][
                    "source_priority_resolved"
                ]


def test_actual_snapshot_keeps_selected_ding_gen_and_unadopted_difference():
    result = calculate_qimen_analysis(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=21,
        analysis_hour=0,
        analysis_timezone="Asia/Hong_Kong",
        use_true_solar_time=False,
        qimen_options={"ju_method": "chaibu"},
    )
    q = result["qimen"]
    ding = next(
        p
        for p in q["patterns"]
        if p["rule_id"] == "wonder_tomb" and p["facts"]["heaven_stem"] == "丁"
    )
    assert ding["palace"] == "艮八宫"
    assert ding["qualification"]["condition_observed"]
    assert "候选未采纳" in result["snapshot_text"]
    assert "王璋口径本宫命中丁" in result["snapshot_text"]
    assert "王璋口径本宫命中丁" in result["snapshot_export"]["export_text"]


def test_uncertain_candidate_is_not_a_selectable_certified_profile():
    with pytest.raises(ValueError, match="不支持的奇门选项"):
        build_qimen_with_options(
            seed(), {"tomb_profile": "opening_sentence_literal_candidate"}
        )


@pytest.fixture
def receipt():
    spec = next(s for s in CATALOG if s.tool_name == "qimen")
    payload = execute_tool(
        spec,
        spec.request_model.model_validate(
            {
                "analysis_year": 2026,
                "analysis_month": 1,
                "analysis_day": 21,
                "analysis_hour": 0,
                "analysis_timezone": "Asia/Hong_Kong",
                "use_true_solar_time": False,
                "qimen_options": {"ju_method": "chaibu"},
            }
        ),
        options=ExecutionOptions(as_of="2026-10-22T12:00:00+08:00"),
    )
    index = next(
        i
        for i, p in enumerate(payload["qimen"]["patterns"])
        if p["rule_id"] == "wonder_tomb"
    )
    claim = CalculationClaim(
        path=f"qimen.patterns.{index}",
        value=deepcopy(payload["qimen"]["patterns"][index]),
        run_id=payload["run_metadata"]["run_id"],
    )
    return payload, claim


def test_whole_tomb_quote_preserves_source_priority_limit(receipt):
    payload, claim = receipt
    assert (
        verify_qimen_pattern_quotes(payload, [claim])["status"]
        == "verified_structured_pattern_quotes"
    )


@pytest.mark.parametrize("change", ["drop", "adopt", "resolved", "erase_difference"])
def test_tomb_quote_cannot_erase_or_adopt_the_candidate(receipt, change):
    payload, claim = receipt
    altered = claim.model_dump()
    q = altered["value"]["qualification"]
    if change == "drop":
        q.pop("tomb_evidence")
    elif change == "adopt":
        q["tomb_evidence"]["candidate_adopted"] = True
    elif change == "resolved":
        q["tomb_evidence"]["source_priority_resolved"] = True
    else:
        q["tomb_evidence"]["disputed_stems_at_this_palace"] = []
    assert (
        verify_qimen_pattern_quotes(
            payload, [CalculationClaim.model_validate(altered)]
        )["status"]
        == "rejected"
    )


@pytest.mark.parametrize(
    "trigram,stems",
    [("中", ["乙"]), ("坤", []), ("乾", ["甲"]), ("乾", ["乙丙"]), ("乾", [""])],
)
def test_no_center_missing_plane_or_invalid_stem_is_reported_as_absence(trigram, stems):
    with pytest.raises(ValueError):
        palace_wonder_tombs(trigram, stems)


def test_reference_cannot_drop_a_clause_or_unresolved_priority(tmp_path):
    b = tmp_path / "fixture"
    shutil.copytree(BUNDLE, b)
    p = b / "sources-and-tomb-clauses.json"
    for key in ("clauses", "unresolved_priority_stems"):
        ref = json.loads((BUNDLE / p.name).read_text())
        if key == "clauses":
            ref[key].pop("opening_sentence_literal_candidate")
        else:
            ref[key].pop()
        p.write_text(json.dumps(ref))
        with pytest.raises(ValueError):
            audit_wonder_tomb_clauses(b)
    p.write_text((BUNDLE / p.name).read_text())
    (b / "siku-pages32-33.pdf").write_bytes(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        audit_wonder_tomb_clauses(b)
