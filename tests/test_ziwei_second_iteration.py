"""Whole-chart software comparison and separately attributed classical rules."""

import hashlib
import json
from copy import deepcopy

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_horoscope
from fatebridge.core.ziwei_tables import lookup_star_brightness
from fatebridge.services.metaphysics import _build_analysis_seed
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from scripts.audit_ziwei import (
    FIXTURES,
    ROOT,
    audit_additional_classical,
    report,
    synthetic_seed,
)
from scripts.audit_ziwei_natal import audit_natal

pytestmark = [
    pytest.mark.filterwarnings("ignore:fromSolarDate is deprecated:DeprecationWarning"),
    pytest.mark.filterwarnings("ignore:toSolarDate is deprecated:DeprecationWarning"),
    pytest.mark.filterwarnings("ignore:use is_leap_month:DeprecationWarning"),
]


def test_complete_natal_corpus_preserves_all_cases_and_fields():
    result = audit_natal()
    assert result["case_count"] == 1080
    assert result["star_records_checked"] == 71280
    assert result["cycle_cells_checked"] == 25920
    assert result["year_stem_coverage"] == 10
    assert result["year_branch_coverage"] == result["hour_branch_coverage"] == 12
    assert not result["differences"]
    assert not result["whole_input_space_certified"]


def test_selected_classical_table_has_240_actual_source_cells_without_full_book_claim():
    result = audit_additional_classical()
    assert result["brightness_cells_checked"] == 240
    assert not result["differences"]
    assert result["unresolved"]
    assert result["status"] == "partial"
    assert not result["whole_book_acceptance_passed"]


@pytest.mark.parametrize(
    "star,software,table",
    [("太阳", "陷", "平"), ("太阴", "不", "旺"), ("七杀", "庙", "旺")],
)
def test_software_and_classical_brightness_are_explicit_source_choices(
    star, software, table
):
    assert lookup_star_brightness(star, "酉") == software
    assert (
        lookup_star_brightness(star, "酉", rule_profile="quanshu_v2_excerpt") == table
    )


def test_table_vs_prose_conflict_is_not_silently_adjudicated():
    # The selected table calls 太阴寅 旺; prose in the same volume says 庙.
    assert (
        lookup_star_brightness("太阴", "寅", rule_profile="quanshu_v2_excerpt") == "旺"
    )
    source = json.loads((FIXTURES / "quanshu_additional_excerpts.json").read_text())
    assert any("太阴寅" in text for text in source["unresolved"])
    assert lookup_star_brightness("禄存", "子") is None
    assert (
        lookup_star_brightness("禄存", "子", rule_profile="quanshu_v2_excerpt") == "庙"
    )
    assert (
        lookup_star_brightness("天刑", "子", rule_profile="quanshu_v2_excerpt") is None
    )


def test_changsheng_and_boshi_directions_are_independent_rules():
    seed = synthetic_seed(1985)  # 乙丑, male: software reverse; text 长生 forward.
    software = build_ziwei_chart(seed, "男")
    classic = build_ziwei_chart(seed, "男", rule_profile="quanshu_v2_excerpt")
    assert software["calendar_cycles"]["changsheng_direction"] == "逆行"
    assert classic["calendar_cycles"]["changsheng_direction"] == "顺行"
    assert classic["calendar_cycles"]["boshi_direction"] == "逆行"
    assert classic["wuxing_ju"]["element"] == "土"
    by_branch = {p["ganzhi"][1]: p for p in classic["palaces"]}
    assert by_branch["申"]["changsheng12"] == "长生"
    assert by_branch["酉"]["changsheng12"] == "沐浴"
    assert by_branch["未"]["changsheng12"] == "养"
    assert by_branch["卯"]["boshi12"] == "博士"
    assert by_branch["寅"]["boshi12"] == "力士"


def test_missing_gender_keeps_only_direction_invariants_and_defined_masters():
    chart = build_ziwei_chart(synthetic_seed(1984), "未知")
    assert chart["calendar_cycles"]["status"] == "partial_missing_gender"
    assert chart["chart_masters"]["life"]["star"] == "禄存"
    assert chart["chart_masters"]["body"]["star"] == "火星"
    for key, labels in (
        ("changsheng12", {"长生", "病"}),
        ("boshi12", {"博士", "飞廉"}),
    ):
        assert {p[key] for p in chart["palaces"] if p[key] is not None} == labels
        assert sum(p[key] is None for p in chart["palaces"]) == 10
    classic = build_ziwei_chart(
        synthetic_seed(1984), "男", rule_profile="quanshu_v2_excerpt"
    )
    assert (
        classic["chart_masters"]["body"]["source_status"]
        == "software_fallback_ambiguous_fire_ling_text"
    )


def test_three_distinct_void_systems_are_not_merged_by_name():
    chart = build_ziwei_chart(synthetic_seed(1992), "男")
    stars = {
        s["name"]: p["ganzhi"][1] for p in chart["palaces"] for s in p["stars_detail"]
    }
    assert stars["天空"] == "酉"
    assert stars["截路"] == "寅" and stars["空亡"] == "卯"
    assert stars["旬空"] == "戌"
    assert stars["地空"] == "亥" and stars["地劫"] == "亥"
    assert len(stars) == 66


def test_annual_lucun_yang_tuo_follow_target_stem_without_moving_natal_stars():
    chart = build_ziwei_chart(synthetic_seed(1984), "男")
    before = deepcopy(chart)
    target = _build_analysis_seed(
        analysis_year=2029, analysis_month=6, analysis_day=15, analysis_hour=12
    )
    result = build_ziwei_horoscope(
        nominal_age_basis="legacy_mixed_clock",
        chart=chart,
        gender="男",
        target_seed=target,
    )
    annual = next(s for s in result["scopes"] if s["scope"] == "流年")
    assert annual["stem"] == "己"
    assert {s["star"]: s["branch"] for s in annual["flowing_stars"]} == {
        "禄存": "午",
        "擎羊": "未",
        "陀罗": "巳",
    }
    assert all(
        not s["natal_stars_relocated"] and s["scope"] == "流年"
        for s in annual["flowing_stars"]
    )
    assert chart == before
    assert all(
        "flowing_stars" not in s for s in result["scopes"] if s["scope"] != "流年"
    )


def test_natal_reference_is_frozen_independently_of_current_engine():
    manifest = json.loads((FIXTURES / "natal_manifest.json").read_text())
    for source in manifest["files"]:
        assert (
            hashlib.sha256((FIXTURES / source["path"]).read_bytes()).hexdigest()
            == source["sha256"]
        )
    assert manifest["npm_integrity"].startswith("sha512-")
    assert manifest["source"].endswith("/2.5.8")


def test_audit_rejects_source_drift_during_audit_without_editing_real_files(
    monkeypatch,
):
    source = ROOT / "src/fatebridge/core/ziwei_rulesets.py"
    original = type(source).read_bytes
    reads = 0

    def changed_after_first_read(path):
        nonlocal reads
        data = original(path)
        if path == source:
            reads += 1
            if reads > 1:
                return data + b"\n"
        return data

    monkeypatch.setattr(type(source), "read_bytes", changed_after_first_read)
    with pytest.raises(RuntimeError, match="Source changed during"):
        report()


def test_real_calculation_receipt_rejects_natal_scope_confusion_and_changed_source():
    spec = next(s for s in CATALOG if s.key == "ziwei_horoscope")
    request = spec.request_model.model_validate(
        dict(
            birth_year=1992,
            birth_month=8,
            birth_day=15,
            birth_hour=14,
            gender="男",
            use_true_solar_time=False,
            target_year=2027,
            target_month=6,
            target_day=15,
            target_hour=12,
        )
    )
    payload = execute_tool(spec, request)
    scope_index = next(
        i
        for i, s in enumerate(payload["ziwei_horoscope"]["scopes"])
        if s["scope"] == "流年"
    )
    links = payload["ziwei_horoscope"]["scopes"][scope_index]["mutagen_natal_links"]
    link_index = next(i for i, link in enumerate(links) if link["star"] == "天机")
    path = f"ziwei_horoscope.scopes.{scope_index}.mutagen_natal_links.{link_index}.scope_palace_name"
    receipt = payload["run_metadata"]

    def claim(value):
        return CalculationClaim(
            path=path,
            value=value,
            run_id=receipt["run_id"],
            business_output_sha256=receipt["business_output_sha256"],
        )

    assert links[link_index]["natal_palace_name"] == "官禄宫"
    assert (
        verify_calculation_claims(payload, [claim("夫妻宫")])["status"]
        == "verified_structured_facts"
    )
    assert verify_calculation_claims(payload, [claim("官禄宫")])["status"] == "rejected"
    changed = deepcopy(payload)
    changed["ziwei_horoscope"]["ruleset"]["brightness_rule"] = "invented_perfect_table"
    assert verify_calculation_claims(changed, [claim("夫妻宫")])["status"] == "rejected"
