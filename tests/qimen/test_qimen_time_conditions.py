"""Clock conditions must not turn into hidden-stem or moving-palace claims."""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.metaphysics.common import SEXAGENARY_CYCLE
from fatebridge.core.qimen_time_conditions import build_hour_branch_tomb
from fatebridge.services.metaphysics import calculate_qimen_analysis
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim
from fatebridge.validation.qimen_study import FrozenQimenPolicy, apply_policy
from fatebridge.validation.qimen_time_conditions import (
    audit_hour_branch_tombs,
    verify_qimen_time_condition_quotes,
)
from tests.qimen.test_qimen_depth import fixed_board

BUNDLE = Path(__file__).parents[1] / "fixtures/qimen_classical_v8"
REFERENCE = json.loads((BUNDLE / "sources-and-hours.json").read_text())


def test_six_prose_definitions_and_sixty_hour_scope_are_audited_separately():
    report = audit_hour_branch_tombs(BUNDLE)
    assert report["printed_literal_pair_definitions"] == 6
    assert report["finite_hour_values_checked"] == 60
    assert report["finite_nonlisted_hour_values"] == 54
    assert report["disagreements"] == []
    assert not report["verse_omission_treated_as_disagreement"]
    assert not report["heaven_stem_palace_tomb_rule_validated"]


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["hour_ganzhi"])
def test_literals_have_the_printed_element_polarity_and_verse_membership(case):
    condition = build_hour_branch_tomb(case["hour_ganzhi"], source=REFERENCE["source"])
    assert condition["matched"]
    assert condition["matched_definition"] == {
        k: case[k] for k in ("element", "polarity", "verse_listed")
    }
    assert not condition["jia_hidden_instrument_substituted"]
    assert not condition["heaven_stem_palace_tomb_evaluated"]


@pytest.mark.parametrize(
    "dun,ju", [(d, j) for d in ("阳遁", "阴遁") for j in range(1, 10)]
)
def test_all_1080_boards_use_literal_hour_independently_of_ju_and_palace(
    monkeypatch, dun, ju
):
    expected = {c["hour_ganzhi"] for c in REFERENCE["cases"]}
    for hour in SEXAGENARY_CYCLE:
        q = fixed_board(monkeypatch, {"dun": dun, "ju": ju, "hour": hour})
        clock = q["stem_context"]["hour_branch_tomb"]
        assert q["structure"]["hour_branch_tomb"] == (hour in expected)
        assert clock["hour_ganzhi"] == hour
        assert not clock["heaven_stem_palace_tomb_evaluated"]
        assert not any(p["rule_id"] == "hour_branch_tomb" for p in q["patterns"])
        step = next(t for t in q["rule_trace"] if t["rule_id"] == "hour_branch_tomb")
        assert step["outputs"] == clock


def test_jia_chen_hides_ren_but_is_not_the_literal_ren_chen_tomb(monkeypatch):
    q = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 1, "hour": "甲辰"})
    assert q["stem_context"]["hour"]["effective_stem"] == "壬"
    assert not q["structure"]["hour_branch_tomb"]
    assert q["stem_context"]["hour_branch_tomb"]["literal_stem"] == "甲"


def test_ji_chou_prose_supplement_is_kept_in_snapshot_and_export():
    result = calculate_qimen_analysis(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=22,
        analysis_hour=2,
        analysis_timezone="Asia/Hong_Kong",
        use_true_solar_time=False,
    )
    assert result["qimen"]["time_ganzhi"] == "己丑"
    assert result["qimen"]["structure"]["hour_branch_tomb"]
    assert "己丑为正文补列" in result["snapshot_text"]
    assert "己丑为正文补列" in result["snapshot_export"]["export_text"]


def test_true_solar_crossing_uses_actual_selected_hour_not_input_clock_label():
    args = dict(
        analysis_year=2026,
        analysis_month=1,
        analysis_day=22,
        analysis_hour=3,
        analysis_minute=5,
        analysis_timezone="Asia/Hong_Kong",
        analysis_longitude=100.0,
    )
    civil = calculate_qimen_analysis(**args, use_true_solar_time=False)
    solar = calculate_qimen_analysis(**args, use_true_solar_time=True)
    assert civil["qimen"]["time_ganzhi"] == "庚寅"
    assert not civil["qimen"]["structure"]["hour_branch_tomb"]
    assert solar["qimen"]["time_ganzhi"] == "己丑"
    assert solar["qimen"]["structure"]["hour_branch_tomb"]


def test_research_policy_reads_this_known_clock_fact_even_with_day_jia_unknown(
    monkeypatch,
):
    q = fixed_board(monkeypatch, {"dun": "阳遁", "ju": 1, "hour": "壬辰"}, day="甲子")
    policy = FrozenQimenPolicy(
        policy_id="synthetic",
        target_definition="synthetic",
        ju_method="chaibu",
        god_profile="yanyi_text",
        season_profile="yanyi_vol1_verse",
        use_true_solar_time=False,
        source_disagreement_action="use_declared_rules",
        rules=[
            {
                "rule_id": "test-only-not-calibrated",
                "all_of": [{"feature": "hour_branch_tomb", "equals": True}],
                "probability": 0.8,
            }
        ],
        fallback_probability=None,
    )
    assert q["stem_context"]["day"]["status"] == "unresolved_jia_identity"
    assert apply_policy(q, policy)["probability"] == 0.8


@pytest.fixture
def receipt():
    spec = next(s for s in CATALOG if s.tool_name == "qimen")
    payload = execute_tool(
        spec,
        spec.request_model.model_validate(
            {
                "analysis_year": 2026,
                "analysis_month": 1,
                "analysis_day": 22,
                "analysis_hour": 2,
                "analysis_timezone": "Asia/Hong_Kong",
                "use_true_solar_time": False,
            }
        ),
        options=ExecutionOptions(as_of="2026-10-22T12:00:00+08:00"),
    )
    claim = CalculationClaim(
        path="qimen.stem_context.hour_branch_tomb",
        value=deepcopy(payload["qimen"]["stem_context"]["hour_branch_tomb"]),
        run_id=payload["run_metadata"]["run_id"],
    )
    return payload, claim


def test_whole_time_quote_preserves_semantic_limits(receipt):
    payload, claim = receipt
    report = verify_qimen_time_condition_quotes(payload, [claim])
    assert report["status"] == "verified_structured_time_condition"
    assert (
        not report["free_text_semantics_validated"]
        and not report["real_world_efficacy_validated"]
    )


@pytest.mark.parametrize(
    "change", ["scope", "palace", "jia", "verse", "flag_only", "different_run"]
)
def test_quotes_cannot_drop_limits_or_turn_clock_into_palace_evidence(receipt, change):
    payload, claim = receipt
    altered = claim.model_dump()
    if change == "scope":
        altered["value"].pop("interpretation_limit")
    elif change == "palace":
        altered["value"]["heaven_stem_palace_tomb_evaluated"] = True
    elif change == "jia":
        altered["value"]["jia_hidden_instrument_substituted"] = True
    elif change == "verse":
        altered["value"]["matched_definition"]["verse_listed"] = True
    elif change == "flag_only":
        altered.update(path="qimen.structure.hour_branch_tomb", value=True)
    else:
        altered["run_id"] = "different-run"
    assert (
        verify_qimen_time_condition_quotes(
            payload, [CalculationClaim.model_validate(altered)]
        )["status"]
        == "rejected"
    )


def test_cannot_delete_sixth_definition_or_change_source(tmp_path):
    b = tmp_path / "fixture"
    shutil.copytree(BUNDLE, b)
    p = b / "sources-and-hours.json"
    r = json.loads(p.read_text())
    r["cases"].pop()
    p.write_text(json.dumps(r))
    with pytest.raises(ValueError, match="全部六时"):
        audit_hour_branch_tombs(b)
    p.write_text((BUNDLE / p.name).read_text())
    (b / "siku-page33.pdf").write_bytes(b"changed")
    with pytest.raises(ValueError, match="指纹"):
        audit_hour_branch_tombs(b)


@pytest.mark.parametrize("hour", ["甲丑", "壬戍", "example", ""])
def test_invalid_hour_is_not_silently_reported_as_a_negative(hour):
    with pytest.raises(ValueError):
        build_hour_branch_tomb(hour, source=REFERENCE["source"])
