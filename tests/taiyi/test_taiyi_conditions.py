"""Freeze explicit clauses separately from historical source observations."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core.metaphysics.taiyi_conditions import five_general_conditions
from fatebridge.core.metaphysics.taiyi_year import (
    cyclic_core,
    structural_patterns,
    yearly_core,
)
from fatebridge.core.output_taiyi_conditions import TaiyiConditionAssessment
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from scripts.taiyi.audit_taiyi_historical import audit

CORPUS = Path(__file__).parents[1] / "fixtures/taiyi_jinjing_v4"
TRUTH = json.loads((CORPUS / "predicate-cases.json").read_text())["cases"]
HISTORY = json.loads((CORPUS / "historical-cases.json").read_text())["cases"]


def test_complete_frozen_evidence_and_separate_oracle_kinds():
    manifest = json.loads((CORPUS / "manifest.json").read_text())
    for item in manifest["source_files"]:
        assert (
            hashlib.sha256((CORPUS / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )
    assert len(TRUTH) == 8 and len(HISTORY) == 10
    assert {
        (r["shiji_blocked"], r["wenchang_blocked"], r["generals_connected"])
        for r in TRUTH
    } == {
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, False),
        (True, False, True),
        (False, True, True),
        (True, True, True),
    }
    assert manifest["completion_claim"] is False
    assert (
        "synthetic"
        in json.loads((CORPUS / "predicate-cases.json").read_text())["oracle_kind"]
    )


@pytest.mark.parametrize("case", TRUTH, ids=lambda c: c["id"])
def test_each_of_three_clauses_is_required_and_all_blockers_survive(case):
    patterns = []
    for field, name, subject in [
        ("shiji_blocked", "掩", "始击"),
        ("wenchang_blocked", "迫", "文昌"),
        ("generals_connected", "关", "主大将"),
    ]:
        if case[field]:
            patterns.append({"name": name, "subject": subject, "variant": name})
    assessment = five_general_conditions(patterns)
    TaiyiConditionAssessment.model_validate(assessment)
    # The frozen eight Boolean rows still verify the old evaluated-relation
    # conjunction. A list without the same core cannot prove full absence.
    assert (
        assessment["five_generals"]["assessed_conditions_satisfied"] is case["expected"]
    )
    expected = None if case["expected"] else False
    assert assessment["five_generals"]["conditions_satisfied"] is expected
    clauses = assessment["five_generals"]["clauses"]
    assert sum(len(c["blockers"]) for c in clauses) == len(patterns)
    assert assessment["menju_jiangfa"] is expected
    assert assessment["three_gates"]["status"] == "not_assessed"


@pytest.mark.parametrize(
    "name,subject", [("掩", "始击"), ("击", "始击"), ("囚", "文昌"), ("迫", "文昌")]
)
def test_every_explicit_eye_condition_can_block_alone(name, subject):
    result = five_general_conditions(
        [{"name": name, "subject": subject, "variant": "independent boundary"}]
    )
    assert result["five_generals"]["conditions_satisfied"] is False
    assert result["menju_jiangfa"] is False


def test_passing_five_clauses_does_not_erase_other_relations_or_certify_gates():
    # Volume 3 Yang 23: Wen-chang 乾 is opposite Taiyi 巽. 對 is a separate
    # relation; the explicit volume-4 clause does not say "no relation at all".
    core = cyclic_core(23)
    assert core["taiyi_palace"] == "巽" and core["wenchang_palace"] == "乾"
    patterns = structural_patterns(core)
    assert any(p["name"] == "对" and p["subject"] == "文昌" for p in patterns)
    result = five_general_conditions(patterns, core=core)
    assert result["five_generals"]["conditions_satisfied"] is True
    assert result["menju_jiangfa"] is None
    assert "三门条件未定" in result["summary"]


def resolve(root, path):
    for key in path.split("."):
        root = root[int(key)] if isinstance(root, list) else root[key]
    return root


@pytest.mark.parametrize("mode", ["year", "month", "hour"])
def test_returned_blockers_and_snapshot_resolve_to_this_same_board(mode):
    result = calculate_taiyi_analysis(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=4,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        calculation_mode=mode,
        use_true_solar_time=False,
    )
    assessment = result["taiyi"]["condition_assessment"]
    assert assessment["summary"] in result["snapshot_text"]
    for clause in assessment["five_generals"]["clauses"]:
        for reference in clause["blockers"]:
            actual = resolve(result, reference["source_path"])
            assert all(
                actual[key] == reference[key] for key in ("name", "subject", "variant")
            )
            assert reference["source_path"] in result["snapshot_text"]
    from fatebridge.core.metaphysics.taiyi_conditions import conjunction

    assert assessment["menju_jiangfa"] is conjunction(
        assessment["five_generals"]["conditions_satisfied"],
        assessment["three_gates"].get("conditions_satisfied"),
    )


def test_all_144_ju_keep_each_blocking_relation_and_no_others():
    for yin in (False, True):
        for counter in range(1, 73):
            core = cyclic_core(counter, yin=yin)
            patterns = structural_patterns(core)
            result = five_general_conditions(patterns, core=core)
            blockers = [
                b for c in result["five_generals"]["clauses"] for b in c["blockers"]
            ]
            expected = [
                (i, p)
                for i, p in enumerate(patterns)
                if (p["subject"] == "始击" and p["name"] in {"掩", "击"})
                or (p["subject"] == "文昌" and p["name"] in {"囚", "迫"})
                or p["name"] == "关"
            ]
            assert len(blockers) == len(expected)
            assert {b["source_path"] for b in blockers} == {
                f"taiyi.patterns.{i}" for i, p in expected
            }


@pytest.mark.parametrize("case", HISTORY, ids=lambda c: c["historical_label"])
def test_entire_independent_historical_list_without_selecting_successful_years(case):
    if "year_ce" in case:
        core = yearly_core(case["year_ce"])
    else:
        # Historical 1 BCE -> astronomical year 0. This verifies a cyclic
        # reference fact; it does not enable ancient dates in the public API.
        astro_year = 1 - case["year_bce"]
        core = cyclic_core(1937281 + astro_year - 724)
        core["kook_year"] = ("理天", "理地", "理人")[(core["accumulation"] - 1) % 3]
    assert (core["accumulation"] - 1) % 360 + 1 == case["yuan_ju"]
    assert core["taiyi_number"] == case["taiyi_number"]
    if case["historical_label"] == "宋元徽二年":
        # Keep the published 理地. Do not silently correct it to the rule.
        assert case["kook_year"] == "理地" and core["kook_year"] == "理人"
    else:
        assert core["kook_year"] == case["kook_year"]


def test_published_historical_disagreement_remains_a_failing_audit():
    report = audit()
    assert report["checked_fields"] == 30 and report["matching_fields"] == 29
    assert report["historical_reference_acceptance_passed"] is False
    assert report["calendar_adapter_validated_for_ancient_dates"] is False
    assert report["disagreements"] == [
        {
            "historical_label": "宋元徽二年",
            "field": "kook_year",
            "source_value": "理地",
            "rule_derived_value": "理人",
            "status": "published_reading_confirmed_disagreement_retained",
        }
    ]


@pytest.mark.parametrize("attempt", ["drop_row", "drop_field", "alter_image"])
def test_historical_audit_rejects_deleted_failure_or_changed_source(tmp_path, attempt):
    corpus = tmp_path / "corpus"
    shutil.copytree(CORPUS, corpus)
    if attempt == "alter_image":
        (corpus / "ncl06604-page56.jpg").write_bytes(b"changed")
        with pytest.raises(ValueError, match="指纹"):
            audit(corpus)
        return
    path = corpus / "historical-cases.json"
    data = json.loads(path.read_text())
    if attempt == "drop_row":
        data["cases"].pop(8)
    else:
        del data["cases"][8]["kook_year"]
    path.write_text(json.dumps(data))
    manifest_path = corpus / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["source_files"]:
        if item["file"] == path.name:
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="10.*3"):
        audit(corpus)


def test_contract_does_not_coerce_unknown_gate_status_or_text_booleans():
    with pytest.raises(ValidationError):
        TaiyiConditionAssessment.model_validate({"menju_jiangfa": "true"})
    with pytest.raises(ValidationError):
        TaiyiConditionAssessment.model_validate(
            {"five_generals": {"conditions_satisfied": "false"}}
        )
