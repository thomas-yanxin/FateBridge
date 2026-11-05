"""Pinned whole-source checks and unambiguous scope/naming regressions."""

import json
import shutil
from copy import deepcopy

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_horoscope
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from scripts.ziwei.audit_ziwei import (
    FIXTURES,
    audit_depth_classical,
    audit_ming_scan,
    synthetic_seed,
)
from scripts.ziwei.audit_ziwei_phase import audit_phase_days, new_moons
from scripts.ziwei.ziwei_conditional_inputs import synthetic_birth_clock


def test_nasa_new_moons_cover_335_pre_hko_days_without_claiming_month_numbering():
    result = audit_phase_days()
    assert result["lunar_day_cells_checked"] == 335
    assert result["new_moon_boundaries_in_range"] == 12
    assert result["minimum_minutes_to_local_midnight"] == 70
    assert result["checked_field"] == "lunar_day_only"
    assert result["limits"] and not result["mismatches"]


def test_phase_parser_does_not_take_full_moon_when_new_moon_column_is_empty():
    source = (FIXTURES / "nasa-phases1901.html").read_text(encoding="utf-8")
    moments = new_moons(source)
    first = moments[0]
    assert first.strftime("%Y-%m-%d %H:%M") == "1901-01-20 14:36"


def test_selected_ming_scan_collation_retains_edition_differences_and_unknowns():
    result = audit_ming_scan()
    assert result["scan_frames_frozen"] == 6
    assert result["noble_placement_checks"] == 40
    assert result["independent_noble_source_cells"] == 20
    assert result["void_pairs_checked"] == 60
    assert result["element_records_checked"] == 16
    assert result["printed_volume"] == "三" and result["transcription_volume"] == "二"
    assert result["manual_scan_reader_count"] == 1
    assert result["pinned_transcription_differences"]
    assert result["body_master_unresolved"]["source_reading"] == "子午人火鈴星"
    assert not result["mismatches"]
    assert not result["whole_book_acceptance_passed"]


def test_ming_scan_bytes_are_required_not_just_a_citation_url(tmp_path):
    shutil.copytree(FIXTURES / "naj_ming", tmp_path / "naj_ming")
    page = tmp_path / "naj_ming/frame_0075.jpg"
    page.write_bytes(page.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Ming scan source checksum mismatch"):
        audit_ming_scan(tmp_path)


def test_whole_pinned_source_and_independent_depth_vectors():
    result = audit_depth_classical()
    assert result["source_revision"] == 1963110
    assert result["void_pairs_checked"] == 60
    assert result["annual_placements_checked"] == 72
    assert result["annual_sha_sets_checked"] == 12
    assert result["symbolic_source_records_checked"] == 16
    assert result["symbolic_calculation_joins_checked"] == 960
    assert not result["mismatches"]
    assert result["unresolved"]
    assert not result["whole_book_acceptance_passed"]


def test_full_source_checksum_rejects_drift_without_replacing_expectations(tmp_path):
    manifest = json.loads((FIXTURES / "depth_manifest.json").read_text())
    shutil.copy2(FIXTURES / "depth_manifest.json", tmp_path)
    for item in manifest["files"]:
        shutil.copy2(FIXTURES / item["path"], tmp_path)
    source = tmp_path / "quanshu_v2_revision_1963110.json"
    source.write_bytes(source.read_bytes() + b" ")
    with pytest.raises(ValueError, match="source checksum mismatch"):
        audit_depth_classical(tmp_path)


@pytest.mark.parametrize("year,primary", [(1984, "戌"), (1985, "亥")])
def test_pinned_text_keeps_both_xun_voids_without_changing_software_profile(
    year, primary
):
    software = build_ziwei_chart(synthetic_seed(year), "男")
    classic = build_ziwei_chart(
        synthetic_seed(year), "男", rule_profile="quanshu_v2_excerpt"
    )
    assert software["void_systems"]["xun"]["displayed_star_branches"] == [primary]
    assert classic["void_systems"]["xun"]["displayed_star_branches"] == ["戌", "亥"]
    positions = [
        p["ganzhi"][1]
        for p in classic["palaces"]
        if any(s["name"] == "旬空" for s in p["stars_detail"])
    ]
    assert set(positions) == {"戌", "亥"}
    assert classic["reading_view"]["star_occurrence_count"] == 67
    assert classic["reading_view"]["distinct_star_count"] == 66
    assert software["reading_view"]["star_occurrence_count"] == 66


def test_annual_virtues_and_flying_stars_are_not_natal_or_boshi_stars():
    chart = build_ziwei_chart(
        synthetic_seed(1992), "男", rule_profile="quanshu_v2_excerpt"
    )
    before = deepcopy(chart)
    result = build_ziwei_horoscope(
        birth_seed=synthetic_birth_clock(int((chart)["lunar_date"]["year"])),
        chart=chart,
        gender="男",
        target_seed=synthetic_seed(2027, 6, 15),
    )
    annual = next(s for s in result["scopes"] if s["scope"] == "流年")
    target = {s["star"]: s for s in annual["flowing_stars"]}
    assert target["月德"]["branch"] == "未"
    assert target["天德"]["branch"] == "辰"
    assert target["丧门"]["branch"] == "酉"
    assert target["吊客"]["branch"] == "巳"
    assert target["白虎"]["branch"] == "卯"
    assert target["官府"]["branch"] == "亥"
    assert target["官府"]["system_id"] == "annual_four_flying_stars"
    assert all(
        s["scope"] == "流年" and not s["natal_stars_relocated"] for s in target.values()
    )
    assert chart == before
    natal_yuede = next(
        p["ganzhi"][1]
        for p in chart["palaces"]
        if any(s["name"] == "月德" for s in p["stars_detail"])
    )
    assert natal_yuede == "丑" and natal_yuede != target["月德"]["branch"]
    for record in target.values():
        palace = next(
            p for p in annual["palace_map"] if p["branch"] == record["branch"]
        )
        assert record["natal_palace_name"] == palace["natal_palace_name"]
        assert record["scope_palace_name"] == palace["scope_palace_name"]


def test_three_sha_returns_only_the_group_the_text_explicitly_supplies():
    chart = build_ziwei_chart(
        synthetic_seed(1984), "男", rule_profile="quanshu_v2_excerpt"
    )
    result = build_ziwei_horoscope(
        birth_seed=synthetic_birth_clock(int((chart)["lunar_date"]["year"])),
        chart=chart,
        gender="男",
        target_seed=synthetic_seed(2027),
    )
    annual = next(s for s in result["scopes"] if s["scope"] == "流年")
    sha = annual["annual_three_sha"]
    assert sha["branches"] == ["申", "子", "辰"]
    assert sha["names_as_written"] == ["奏书", "将军", "直符"]
    assert sha["individual_name_positions"] is None
    assert sha["distinct_from_boshi_cycle"]
    assert not {"奏书", "将军", "直符"}.intersection(
        s["star"] for s in annual["flowing_stars"]
    )


def test_textual_symbolism_is_not_a_new_sihua_assignment():
    chart = build_ziwei_chart(
        synthetic_seed(1984), "男", rule_profile="quanshu_v2_excerpt"
    )
    evidence = chart["symbolic_properties"]
    rows = {r["star"]: r for r in evidence["records"]}
    assert not evidence["textual_hua_terms_are_sihua"]
    assert rows["武曲"]["natal_mutagen"] == "化科"
    assert "化财" in rows["武曲"]["source_quote"]
    assert "遇帝为权" in rows["七杀"]["source_quote"]
    assert rows["七杀"]["natal_mutagen"] is None
    assert rows["天同"]["elements_as_written"] == ["水", "金"]
    assert rows["七杀"]["elements_as_written"] == ["火", "金"]
    assert rows["贪狼"]["elements_as_written"] == ["水", "木"]
    assert rows["廉贞"]["source_name"] == "廉真"
    assert chart["void_systems"]["source_name_mapping"]["天空地劫诀中的天空"] == "地空"


def test_actual_receipt_does_not_accept_textual_huacai_as_natal_huake():
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    request = spec.request_model.model_validate(
        dict(
            birth_year=1984,
            birth_month=3,
            birth_day=15,
            birth_hour=12,
            gender="男",
            use_true_solar_time=False,
            rule_profile="quanshu_v2_excerpt",
        )
    )
    payload = execute_tool(spec, request)
    rows = payload["ziwei_birth"]["symbolic_properties"]["records"]
    i = next(i for i, r in enumerate(rows) if r["star"] == "武曲")
    receipt = payload["run_metadata"]

    def claim(value):
        return CalculationClaim(
            path=f"ziwei_birth.symbolic_properties.records.{i}.natal_mutagen",
            value=value,
            run_id=receipt["run_id"],
            business_output_sha256=receipt["business_output_sha256"],
        )

    assert rows[i]["natal_mutagen"] == "化科"
    assert (
        verify_calculation_claims(payload, [claim("化科")])["status"]
        == "verified_structured_facts"
    )
    assert verify_calculation_claims(payload, [claim("化财")])["status"] == "rejected"
