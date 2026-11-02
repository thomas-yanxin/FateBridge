"""Source cases, counterexamples and actual public transport parity."""

import asyncio
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.analysis.marriage import MarriageAnalysis
from fatebridge.application.examples import suggested_fields
from fatebridge.core.bazi_evidence import build_natal_evidence, build_topic_evidence
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_bazi_evidence import BaziEvidenceChain
from tests.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)
from tests.test_result_delivery import reconstruct, store

CASES = json.loads(
    (Path(__file__).parent / "fixtures/bazi_classical_v1/cases.json").read_text()
)


def pillars(values):
    return {n: tuple(p) for n, p in zip(("year", "month", "day", "hour"), values)}


def source_case(case_id):
    return pillars(next(c["pillars"] for c in CASES if c["id"] == case_id))


def check(result, key):
    return next(c for c in result["structure_checks"] if c["id"] == key)


@pytest.mark.parametrize(
    "case_id,distance,intervening,combination",
    [
        ("ZP31-XUE", 2, ["day"], False),
        ("ZP31-LONE", 1, [], True),
        ("ZP41-DUTONG", 3, ["month", "day"], True),
        ("ZP41-CHENGXIANG", 3, ["month", "day"], True),
    ],
)
def test_frozen_book_cases_retain_financial_seal_separation(
    case_id, distance, intervening, combination
):
    # These spatial distinctions are explicitly described on PDF65/66/84.
    result = build_natal_evidence(source_case(case_id))
    relation = result["financial_seal_positions"][0]
    assert relation["distance"] == distance
    assert relation["intervening_positions"] == intervening
    assert relation["stem_combination"] is combination
    # 丁壬 separated by 戊己 still have a pair relation, not an automatic 合去.
    assert relation["adjudication"] == "position_observation_only"


def test_frozen_liang_food_wealth_keeps_root_in_wei_and_unresolved_force():
    result = build_natal_evidence(source_case("ZP37-LIANG"))
    wealth = result["ten_gods"]["偏财"]
    visible = next(e for e in wealth if e["location"] == "天干")
    assert visible["stem"] == "丁" and visible["pillar"] == "year"
    assert {
        "pillar": "year",
        "branch": "未",
        "stem": "丁",
        "hidden_rank": 1,
        "kind": "same_stem",
    } in visible["roots"]
    c = check(result, "food_generates_wealth")
    assert c["status"] == "pending_adjudication"
    assert c["formation_status"] == "not_adjudicated"
    assert (
        next(x for x in c["conditions"] if x["id"] == "strength_and_relative_force")[
            "status"
        ]
        == "unknown"
    )


def test_hurt_seal_cooccurrence_is_refuted_by_no_root_and_not_certified_by_root():
    no_root = pillars(["甲午", "丙午", "甲午", "壬午"])
    rooted = {**no_root, "hour": ("壬", "子")}
    a = check(build_natal_evidence(no_root), "hurt_with_seal")
    b = check(build_natal_evidence(rooted), "hurt_with_seal")
    assert a["status"] == "prerequisite_not_met"
    assert b["status"] == "pending_adjudication"
    assert a["formation_status"] == b["formation_status"] == "not_adjudicated"
    assert (
        next(c for c in a["conditions"] if c["id"] == "helper_present")["status"]
        == "matched"
    )


def test_root_kind_does_not_fabricate_yin_growth_phase_hidden_stems():
    result = build_natal_evidence(pillars(["乙午", "丁酉", "甲戌", "癸丑"]))
    yi = result["visible_stems"][0]
    ding = result["visible_stems"][1]
    assert all(r["branch"] != "午" for r in yi["roots"])
    assert all(r["branch"] != "酉" for r in ding["roots"])
    assert any(
        r["pillar"] == "year" and r["stage"] == "长生" for r in yi["growth_phase_roots"]
    )
    assert any(
        r["pillar"] == "month" and r["stage"] == "长生"
        for r in ding["growth_phase_roots"]
    )


def test_yin_growth_reference_is_not_rejected_as_certainly_rootless():
    result = build_natal_evidence(pillars(["乙午", "戊午", "丁午", "己巳"]))
    condition = next(
        c
        for c in check(result, "hurt_with_seal")["conditions"]
        if c["id"] == "helper_root_present"
    )
    assert condition["status"] == "unknown"


def test_rob_wealth_in_month_is_not_automatically_yang_blade():
    # The frozen 孤官无辅 case is 戊 in 未; its 乙官 is actually 透 in 时.
    month = build_natal_evidence(source_case("ZP31-LONE"))["month_command"]
    assert month["label"] == "正官格"  # 杂气透乙、卯未会支，不能误作月刃。
    assert month["legacy_label"] == "月刃格"  # 旧标签保留，不能覆盖校正结果。
    assert not month["yang_blade_seat"]
    assert month["legacy_blade_qualification_conflict"]
    officer = next(c for c in month["candidates"] if c["ten_god"] == "正官")
    assert officer["visible_in"] == ["hour"]


def test_timing_retains_hidden_wealth_and_joint_dayun_liunian_bureau():
    p = pillars(["庚申", "丁巳", "甲午", "丙寅"])
    natal = build_natal_evidence(p)
    before = copy.deepcopy(natal)
    result = build_topic_evidence(natal, p, "wealth", "男", ("甲", "子"), ("丙", "辰"))
    assert any(
        g["kind"] == "三合" and set(g["branches"]) == set("申子辰")
        for g in result["timing"]["combined_groups"]
    )
    assert all(
        g["effect_status"] == "relation_only"
        for g in result["timing"]["combined_groups"]
    )
    changed = build_topic_evidence(natal, p, "wealth", "男", None, ("辛", "未"))
    assert any(
        e["stem"] == "己" and e["location"] == "地支藏干" and e["in_topic"]
        for e in changed["timing"]["layers"][0]["stars"]
    )
    assert natal == before  # Changing target time cannot mutate the natal chart.


def test_book_weak_label_is_not_replaced_by_modern_strength_as_classical_truth():
    p = source_case("ZP41-BO")
    strength = ElementAnalysis.analyze_day_master_strength(p)
    result = build_natal_evidence(p, strength)
    condition = next(
        c
        for c in check(result, "hurt_with_seal")["conditions"]
        if c["id"] == "strength_and_relative_force"
    )
    assert condition["status"] == "unknown"
    assert (
        condition["model_observation"]["strength_level"] == strength["strength_level"]
    )
    assert result["strength_context"]["requires_special_structure_review"] is True


def test_spouse_star_only_in_day_palace_is_not_lost():
    p = pillars(["甲寅", "丙寅", "甲戌", "丙寅"])
    result = MarriageAnalysis._analyze_spouse_star(p, "甲", True)
    assert any(
        e["position"] == "day_hidden" and e["stem"] == "戊"
        for e in result["spouse_star_positions"]
    )


def test_unknown_gender_does_not_execute_female_marriage_scoring():
    p = source_case("ZP31-LONE")
    result = MarriageAnalysis.analyze_marriage(p)
    assert result["gender_basis"] == "unselected_gender_alternatives"
    assert result["marriage_quality"]["score"] is None
    assert set(result["spouse_star"]["alternatives"]) == {"male", "female"}


def test_shensha_target_without_actual_branch_is_not_a_hit():
    # 子年/子日 -> 红鸾卯、天喜酉、咸池酉、孤辰寅、寡宿戌，均未出现。
    p = pillars(["甲子", "乙丑", "丙子", "己丑"])
    assert MarriageAnalysis._check_marriage_shensha(p) == []
    hit = MarriageAnalysis._check_marriage_shensha({**p, "hour": ("丁", "卯")})
    assert [e["name"] for e in hit] == ["红鸾"]


def test_male_tomb_lookup_uses_wealth_not_officer_element():
    p = pillars(["戊戌", "乙丑", "甲子", "辛丑"])
    # 土为甲财，不在该四墓简表；辛金是官，不能被男命误当配偶星。
    risks = MarriageAnalysis._identify_risk_factors(p, "甲", "子", True)
    assert not any(r["type"] == "配偶星入墓" for r in risks)
    fire_wealth = pillars(["丙戌", "乙丑", "壬子", "辛丑"])
    risks = MarriageAnalysis._identify_risk_factors(fire_wealth, "壬", "子", True)
    assert any(r["type"] == "配偶星入墓" and "丙" in r["description"] for r in risks)
    assert not any("健康或运势需关注" in r["description"] for r in risks)


def test_marriage_index_does_not_generate_late_marriage_or_affair_advice():
    result = MarriageAnalysis.analyze_marriage(source_case("ZP31-LI"), "女")
    assert result["marriage_quality"]["score_kind"] == "traditional_rule_index"
    assert not any("建议晚婚" in s for s in result["suggestions"])
    assert not any("第三者风险增加" in s for s in result["marriage_quality"]["notes"])


@pytest.mark.parametrize(
    "topic",
    [
        "career",
        "wealth",
        "marriage",
        "romance",
        "education",
        "personality",
        "relatives",
        "children",
        "health",
    ],
)
@pytest.mark.parametrize("gender", ["男", "未知"])
def test_nine_depth_views_match_actual_rest_mcp_cli(
    topic, gender, rest, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    request = inputs(spec)
    request.pop("dayun_pillar", None)
    request.pop("liunian_pillar", None)
    request.update(gender=gender, analysis_year=2027, analysis_month=2, analysis_day=4)
    fields = suggested_fields(spec, view="depth")
    flags = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
    }
    http = rest.post(spec.rest_path, json=request, params=flags)
    protocol = asyncio.run(native(spec, request, **flags))
    code, output = call_cli(
        spec,
        request,
        tmp_path,
        capsys,
        [
            "--no-metadata",
            "--fields",
            *fields,
            "--strict-fields",
            "--no-include-snapshot-text",
            "--response-char-limit",
            "0",
        ],
    )
    assert http.status_code == 200, http.text
    assert not protocol.is_error and code == 0
    assert business(http.json()) == business(protocol.structured_content) == output
    analysis = output[topic + "_analysis"]
    evidence = analysis["evidence_chain"]
    assert evidence["topic"]["topic"] == topic
    assert evidence["strength_context"]["method_id"]
    assert evidence["rulesets"][0]["source_sha256"]
    assert (
        evidence["topic"]["timing"]["layers"][-1]["pillar"]
        == analysis["timing_context"]["liunian_pillar"]
    )
    assert analysis["timing_context"]["boundary_status"] == "year_boundary_day"
    if gender == "未知":
        assert analysis["timing_context"]["dayun_pillar"] is None
        assert (
            analysis["timing_context"]["dayun_status"] == "unavailable_gender_direction"
        )
        assert len(evidence["topic"]["timing"]["layers"]) == 1


def test_new_nested_contract_rejects_corrupt_root_rank():
    result = build_natal_evidence(source_case("ZP37-LIANG"))
    BaziEvidenceChain.model_validate(result)
    entry = next(
        e for entries in result["ten_gods"].values() for e in entries if e["roots"]
    )
    entry["roots"][0]["hidden_rank"] = "0"
    with pytest.raises(ValidationError):
        BaziEvidenceChain.model_validate(result)


@pytest.mark.parametrize(
    "topic",
    [
        "career",
        "wealth",
        "marriage",
        "romance",
        "education",
        "personality",
        "relatives",
        "children",
        "health",
    ],
)
def test_nine_recommended_first_views_keep_analysis_within_default_budget(topic):
    spec = SPECS["bazi_" + topic]
    response = asyncio.run(
        native(
            spec,
            inputs(spec),
            fields=suggested_fields(spec),
            strict_fields=True,
            include_snapshot_text=False,
            response_char_limit=8192,
        )
    )
    assert not response.is_error
    result = response.structured_content
    # A large installed file inventory may be deferred; the actual first-view
    # analysis must still be inline, without another calculation or call.
    if "result_delivery" in result:
        deferred = result["result_delivery"]["deferred_fields"]
        assert deferred and set(deferred) <= {
            "run_metadata.runtime",
            "run_metadata.provenance",
        }
        assert len(deferred) == len(set(deferred))
    analysis = result[topic + "_analysis"]
    assert analysis["evidence_chain"]["topic"]["first_view"]["timing"]


def test_same_core_evidence_is_published_by_comprehensive_and_birth_surfaces(
    rest, tmp_path, capsys
):
    for key, field in (
        ("analyze_destiny", "structure_profile.evidence_chain"),
        ("bazi_birth", "bazi_birth.structure_profile.evidence_chain"),
    ):
        spec = SPECS[key]
        request = inputs(spec)
        flags = {
            "fields": [field],
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        }
        protocol = asyncio.run(native(spec, request, **flags))
        code, output = call_cli(
            spec,
            request,
            tmp_path,
            capsys,
            [
                "--no-metadata",
                "--fields",
                field,
                "--strict-fields",
                "--no-include-snapshot-text",
                "--response-char-limit",
                "0",
            ],
        )
        assert code == 0 and not protocol.is_error
        assert business(protocol.structured_content) == output
        if spec.rest_path:
            http = rest.post(spec.rest_path, json=request, params=flags)
            assert http.status_code == 200 and business(http.json()) == output
            output = output["bazi_birth"]
        evidence = output["structure_profile"]["evidence_chain"]
        assert evidence["ten_gods"] and evidence["structure_checks"]
    # Use a common actual input, since catalog examples may use distinct people.
    from fatebridge.services.bazi import calculate_bazi_birth
    from fatebridge.services.calculation import calculate_destiny_analysis
    from fatebridge.utils.birth_input import create_person_info

    person = create_person_info(2000, 12, 10, 9, "虚构", "男", "北京")
    a = calculate_destiny_analysis(person)["structure_profile"]["evidence_chain"]
    b = calculate_bazi_birth(person, analysis_year=2027)["bazi_birth"][
        "structure_profile"
    ]["evidence_chain"]
    assert a == b


def test_large_depth_response_preserves_same_run_complete_conditions(store):
    spec = SPECS["bazi_career"]
    response = asyncio.run(
        native(
            spec, inputs(spec), include_snapshot_text=False, response_char_limit=4096
        )
    )
    assert not response.is_error
    result = response.structured_content
    reference = result["result_delivery"]
    restored = reconstruct(store, reference["result_id"])
    assert restored["run_metadata"]["run_id"] == result["run_metadata"]["run_id"]
    assert restored["career_analysis"]["evidence_chain"]["structure_checks"]
