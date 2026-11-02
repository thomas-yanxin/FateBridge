"""Frozen source witnesses and reused geometries; no outcome observations."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from fatebridge.core.meihua_reputation import reputation_ruleset
from fatebridge.core.requests.meihua import MeihuaInterpretationOptions
from fatebridge.services.divination import calculate_meihua_analysis
from fatebridge.services.meihua import calculate_meihua_cast

FIXTURE = Path(__file__).parent / "fixtures/meihua_reputation_v1"
PROFILE = json.loads((FIXTURE / "profile.json").read_text())
GEOMETRY = json.loads((FIXTURE / "geometry384.json").read_text())
CONDITIONS = json.loads((FIXTURE / "contexts.json").read_text())
LITERAL = json.loads((FIXTURE / "literal-candidates.json").read_text())


def resolve(result, path):
    for key in path.split("."):
        result = result[int(key)] if isinstance(result, list) else result[key]
    return result


def test_frozen_source_precedes_implementation_and_profile_is_detached():
    freeze = json.loads((FIXTURE / "reference-freeze.json").read_text())
    assert not freeze["new_module_present"]
    assert not freeze["new_packaged_profile_present"]
    assert not freeze["new_request_context_present"]
    assert not freeze["independent_human_expert_authentication"]
    assert freeze["new_real_world_observations"] == 0
    # Raw baseline business files are retained in the sealed audit, not duplicated
    # into the small reusable fixture. Every copied source witness stays hashed.
    archive_only = {
        "business-before.json.gz",
        "reputation-before.jsonl.gz",
        "git-before.z",
    }
    for name, sha in freeze["files"].items():
        if name not in archive_only:
            assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == sha
    primary = FIXTURE.parent / "meihua_journeys_v1/nlc-original.pdf"
    assert (
        hashlib.sha256(primary.read_bytes()).hexdigest() == freeze["primary_pdf_sha256"]
    )
    for name, sha in freeze["page_images"].items():
        assert (
            hashlib.sha256((FIXTURE / "pages" / name).read_bytes()).hexdigest() == sha
        )
    assert reputation_ruleset() == PROFILE
    copied = reputation_ruleset()
    copied["time_classes"]["震"]["quote"] = "changed"
    assert reputation_ruleset() == PROFILE


@pytest.mark.parametrize("case", GEOMETRY, ids=lambda c: f"{c['code']}:{c['line']}")
@pytest.mark.parametrize("context", CONDITIONS["contexts"], ids=lambda c: c["id"])
def test_all_reused_geometries_and_declared_conditions_keep_own_roles(case, context):
    result = calculate_meihua_cast(
        casting={
            "method": "existing",
            "hexagram_code": case["code"],
            "moving_line": case["line"],
        },
        interpretation_topic="reputation",
        reputation_context=context["context"],
    )
    assert "error" not in result
    q = result["interpretation"]["topic_reading"]["chapter_qualifications"]
    attackers = [r for r in case["rows"] if r["relation"] == "用克体"]
    supporters = [r for r in case["rows"] if r["relation"] == "用生体"]
    expected = next(
        r
        for r in CONDITIONS["conditions"]
        if r["context_id"] == context["id"]
        and r["has_inner_attacker"] == bool(attackers)
    )
    assert q["original_body"] == case["body"] == resolve(result, q["body_fact_path"])
    for actual, reference in zip(q["actual_roles"], case["rows"], strict=True):
        assert (actual["role"], actual["trigram"], actual["relation"]) == (
            reference["role"],
            reference["trigram"],
            reference["relation"],
        )
        assert resolve(result, actual["trigram_fact_path"]) == actual["trigram"]
        assert resolve(result, actual["relation_fact_path"]) == actual["relation"]
        assert (
            resolve(result, actual["countercontrol_fact_path"])
            == actual["countercontrol_qualification"]
        )
    assert [r["role"] for r in q["support_time_references"]] == [
        r["role"] for r in supporters
    ]
    assert [r["role"] for r in q["attacker_time_references"]] == [
        r["role"] for r in attackers
    ]
    for row in q["support_time_references"] + q["attacker_time_references"]:
        time = row["time_reference"]
        assert time["quote"] == PROFILE["time_classes"][row["trigram"]]["quote"]
        assert (
            time["calendar_anchor"]
            is time["calendar_month_basis"]
            is time["numeric_day_count"]
            is time["candidate_event_dates"]
            is None
        )
    office = q["office_qualification"]
    assert office["selected_clause_applies"] is expected["office_clause_applies"]
    assert office["real_personnel_or_hazard_verdict"] is None
    absent = q["no_attacker_qualification"]
    assert (
        absent["selected_internal_scope_matches"]
        is expected["selected_inner_no_attacker"]
    )
    assert (
        absent["full_source_clause_applies"]
        is expected["full_no_attacker_clause_applies"]
    )
    assert not absent["full_inner_outer_absence_authenticated"]
    assert (absent["body_time_reference"] is None) == bool(attackers)
    direction = q["appointment_direction"]
    changed = case["rows"][-1]["trigram"]
    assert (
        direction["selected_trigram"]
        == changed
        == resolve(result, direction["trigram_fact_path"])
    )
    assert (
        direction["selected_table_symbol"]
        == PROFILE["fangdao_classes"][changed]["quote"]
    )
    assert (
        direction["selected_policy_applies"]
        is expected["appointment_declared_condition"]
    )
    assert direction["source_direction_conflict"] == (changed == "巽")
    assert (
        direction["single_geographic_direction"]
        is direction["actual_appointment_location"]
        is direction["numeric_bearing"]
        is None
    )
    assert (
        q["event_time"]
        is q["candidate_event_dates"]
        is q["success_probability"]
        is q["real_outcome"]
        is q["net_effect"]
        is None
    )
    assert q["summary"] in result["summary"]


@pytest.mark.parametrize("basis", ["raw_counts", "trigram_numbers"])
@pytest.mark.parametrize("season", [None, "午"])
def test_literal_candidates_keep_different_body_time_direction_and_office_condition(
    basis,
    season,
):
    result = calculate_meihua_cast(
        casting={**LITERAL["arguments"], "line_sum_basis": basis},
        interpretation_topic="reputation",
        season_month_branch=season,
        reputation_context={
            "label": "人工在任及求职任条件",
            "currently_in_office": True,
            "seeking_official_appointment": True,
        },
    )
    for i, row in enumerate(result["interpretation"]["casting_readings"]):
        q = row["topic_clause"]["chapter_qualifications"]
        expected = LITERAL[row["line_sum_basis"]]
        assert q["original_body"] == expected["body"]
        assert [r["role"] for r in q["support_time_references"]] == expected[
            "generation_roles"
        ]
        assert [r["role"] for r in q["attacker_time_references"]] == expected[
            "attacker_roles"
        ]
        assert q["office_qualification"]["selected_clause_applies"] is bool(
            expected["attacker_roles"]
        )
        assert (
            q["appointment_direction"]["selected_table_symbol"]
            == expected["selected_table_symbol"]
        )
        assert q["body_fact_path"].startswith(f"meihua.counting_variants.{i}.")
        assert resolve(result, q["body_fact_path"]) == expected["body"]
        for role in q["actual_roles"]:
            assert (
                resolve(result, role["countercontrol_fact_path"])
                == role["countercontrol_qualification"]
            )
            if season is not None:
                assert (
                    resolve(result, role["strength_fact_path"])
                    == role["seasonal_strength"]
                )
        assert q["summary"] in row["traditional_judgement"]
        assert q["summary"] in result["summary"]


def test_primary_variants_remain_literal_and_never_become_elapsed_days():
    assert "五金" in PROFILE["time_classes"]["乾"]["quote"]
    assert "一四九" in PROFILE["time_classes"]["乾"]["comparison_reading"]["quote"]
    assert "春二月" in PROFILE["time_classes"]["震"]["quote"]
    assert "春三月" in PROFILE["time_classes"]["震"]["comparison_reading"]["quote"]
    direction = PROFILE["fangdao_classes"]["巽"]
    assert direction["quote"] == "東"
    assert direction["comparison_reading"]["quote"] == "東南"
    assert direction["intra_edition_parallel"][0]["quote"] == "東南方之地"
    rules = {r["id"]: r for r in PROFILE["rules"]}
    assert "上責罰" in rules["in_office"]["quote"]
    assert "退職" in rules["in_office"]["quote"]
    assert "八卦萬物所屬" in rules["office_time"]["quote"]


@pytest.mark.parametrize("bad", ["true", 1, [], {}])
@pytest.mark.parametrize(
    "field", ["currently_in_office", "seeking_official_appointment"]
)
def test_declarations_are_strict_booleans_not_text_inferences(field, bad):
    with pytest.raises(ValueError):
        MeihuaInterpretationOptions(
            interpretation_topic="reputation",
            reputation_context={"label": "人工", field: bad},
        )


def test_unknown_labels_and_question_do_not_become_source_context():
    args = {"casting": LITERAL["arguments"], "interpretation_topic": "reputation"}
    result = calculate_meihua_cast(
        **args,
        question="已在任并求任所",
        reputation_context={"label": "我已在任求任所"},
    )
    for row in result["interpretation"]["casting_readings"]:
        q = row["topic_clause"]["chapter_qualifications"]
        assert q["office_qualification"]["declared_currently_in_office"] is None
        assert q["appointment_direction"]["declared_appointment_condition_met"] is None
    assert calculate_meihua_cast(**args) == calculate_meihua_cast(
        **args, reputation_context=None
    )
    with pytest.raises(ValueError, match="reputation_context"):
        MeihuaInterpretationOptions(reputation_context={"label": "人工"})
    with pytest.raises(ValueError):
        MeihuaInterpretationOptions(
            interpretation_topic="reputation", reputation_context={"label": "   "}
        )


def test_time_cast_strength_paths_resolve_to_actual_result_not_new_strength():
    result = calculate_meihua_analysis(
        analysis_year=2026,
        analysis_month=10,
        analysis_day=26,
        analysis_hour=12,
        analysis_timezone="Asia/Shanghai",
        interpretation_topic="reputation",
        reputation_context={"label": "人工"},
    )
    assert "error" not in result
    q = result["interpretation"]["topic_reading"]["chapter_qualifications"]
    assert resolve(result, q["context_declaration"]["fact_path"]) == {"label": "人工"}
    for role in q["actual_roles"]:
        assert resolve(result, role["strength_fact_path"]) == role["seasonal_strength"]


def test_frozen_before_request_cache_omitted_and_null_remain_compatible():
    script = r"""
import importlib,importlib.util,json,sys
from pathlib import Path
fixture=Path(sys.argv[1]);importlib.import_module('fatebridge.core.requests')
name='fatebridge.core.requests.meihua';spec=importlib.util.spec_from_file_location(name,fixture/'before-request-meihua.py');module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
setattr(sys.modules['fatebridge.core.requests'],'meihua',module)
assert 'reputation_context' not in module.MeihuaInterpretationOptions.model_fields
from fatebridge.services.meihua import calculate_meihua_cast
from fatebridge.services.divination import calculate_meihua_analysis
rows=[]
for topic in ['general','reputation']:
 for kind in ['cast','time']:
  args={'casting':{'method':'existing','hexagram_code':'111111','moving_line':1}} if kind=='cast' else {'analysis_year':2026,'analysis_month':10,'analysis_day':26,'analysis_hour':12,'analysis_timezone':'Asia/Shanghai'}
  fn=calculate_meihua_cast if kind=='cast' else calculate_meihua_analysis
  args['interpretation_topic']=topic
  old=fn(**args);null=fn(**args,reputation_context=None)
  assert 'error' not in old and old==null
  assert 'reputation_context' not in old.get('input_normalized',old.get('analysis_context',{}))
  rows.append([kind,topic,'omitted_equals_null'])
  supplied=fn(**args,reputation_context={'label':'人工未发布字段'})
  assert supplied['error_code']=='validation_error' and supplied['status_code']==400
print(json.dumps(rows))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script, str(FIXTURE)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    assert len(json.loads(proc.stdout)) == 4
