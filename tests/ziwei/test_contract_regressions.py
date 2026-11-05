"""Related contract regressions with shared imports; original cases retained."""

import json
import shutil

import pytest

import scripts.ziwei.audit_ziwei as ziwei_audit
from fatebridge.application.examples import example_input
from fatebridge.application.execution import execute_tool
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_rules
from fatebridge.core.ziwei_tables import (
    ZIWEI_STAR_BRIGHTNESS,
    lookup_star_brightness,
    split_star_mutagen,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from scripts.ziwei.audit_ziwei import FIXTURES, audit_ming_anxing, synthetic_seed


def test_ming_anxing_source_corpus_retains_real_differences():
    result = audit_ming_anxing()
    assert result["independent_sihua_source_cells"] == 40
    assert result["sihua_position_joins_checked"] == 10
    assert result["ziwei_anchor_cells_checked"] == 10
    assert result["tianfu_reflection_cells_checked"] == 12
    assert result["manual_scan_reader_count"] == 1
    assert not result["mismatches"]
    assert not result["current_profiles_conform_to_ming_sihua"]
    assert not result["whole_book_acceptance_passed"]
    assert [
        len(result["edition_differences"][p])
        for p in ("iztro_2_5_8", "quanshu_v2_excerpt")
    ] == [3, 2]


def test_ming_anxing_reference_requires_frozen_image_bytes(tmp_path):
    shutil.copytree(FIXTURES / "naj_ming_anxing_v1", tmp_path / "naj_ming_anxing_v1")
    page = tmp_path / "naj_ming_anxing_v1/frame_0076.jpg"
    page.write_bytes(page.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Ming Anxing source checksum mismatch"):
        audit_ming_anxing(tmp_path)


def test_rewriting_production_table_cannot_rewrite_frozen_source_expectations(
    tmp_path, monkeypatch
):
    name = "src/fatebridge/data/classical/ziwei-naj-ming-sihua.json"
    production = json.loads((ziwei_audit.ROOT / name).read_text())
    row = next(row for row in production["rows"] if row["stem"] == "庚")
    row["assignments"]["化科"] = "太阴"
    row["assignments"]["化忌"] = "天同"
    target = tmp_path / name
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(production, ensure_ascii=False))
    monkeypatch.setattr(ziwei_audit, "ROOT", tmp_path)
    result = audit_ming_anxing(FIXTURES)
    assert result["status"] == "failed"
    assert "literal_sihua_table" in {row["case"] for row in result["mismatches"]}


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_geng_ming_print_comparison_does_not_overwrite_selected_mutagens(profile):
    chart = build_ziwei_chart(synthetic_seed(1990), "男", rule_profile=profile)
    comparison = chart["sihua_source_comparison"]
    assert comparison["source_reading"] == "庚日武同相為首"
    assert not comparison["source_agrees_on_this_stem"]
    assert not comparison["compared_assignments_applied"]
    assert chart["sihua"]["化科"] == "太阴"
    assert chart["sihua"]["化忌"] == "天同"
    diff = {row["transformation"]: row for row in comparison["differences"]}
    assert diff["化科"]["compared_star"] == "天同"
    assert diff["化科"]["compared_position"]["natal_mutagen"] == "化忌"
    assert diff["化忌"]["compared_star"] == "天相"
    assert diff["化忌"]["compared_position"]["natal_mutagen"] is None
    for row in diff.values():
        for side in ("selected", "compared"):
            position = row[f"{side}_position"]
            parts = position["calculation_path"].split(".")
            palace = chart["palaces"][int(parts[2])]
            actual = palace["stars_detail"][int(parts[4])]
            assert actual["name"] == row[f"{side}_star"]
            assert actual["mutagen"] == position["natal_mutagen"]
            assert palace["name"] == position["natal_palace_name"]
            assert palace["ganzhi"][1] == position["natal_branch"]


def test_ren_comparison_depends_on_selected_source_instead_of_claiming_all_differ():
    software = build_ziwei_chart(synthetic_seed(1992), "男")
    excerpt = build_ziwei_chart(
        synthetic_seed(1992), "男", rule_profile="quanshu_v2_excerpt"
    )
    comparison = software["sihua_source_comparison"]
    assert comparison["differences"][0]["selected_star"] == "左辅"
    assert comparison["differences"][0]["compared_star"] == "天府"
    assert excerpt["sihua_source_comparison"]["source_agrees_on_this_stem"]
    assert not excerpt["sihua_source_comparison"]["differences"]
    # Returned lists cannot mutate cached source rows or subsequent results.
    comparison["differences"].clear()
    assert build_ziwei_chart(synthetic_seed(1992), "男")["sihua_source_comparison"][
        "differences"
    ]


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_table_comparison_has_no_whole_book_or_dynamic_scope_claim(profile):
    comparison = build_ziwei_rules(rule_profile=profile)["rule_catalogue"][
        "sihua_source_comparison"
    ]
    assert comparison["scope"] == "natal_sihua_table_only"
    assert comparison["printed_volume"] == "三"
    assert not comparison["compared_assignments_applied"]
    assert not comparison["whole_book_conformance_claimed"]


def test_hypothetical_ming_tianxiang_ji_cannot_be_cited_as_actual_mutagen():
    spec = next(spec for spec in CATALOG if spec.key == "ziwei_birth")
    request = spec.request_model.model_validate(
        dict(
            birth_year=1990,
            birth_month=5,
            birth_day=15,
            birth_hour=12,
            gender="男",
            use_true_solar_time=False,
            rule_profile="quanshu_v2_excerpt",
        )
    )
    payload = execute_tool(spec, request)
    comparison = payload["ziwei_birth"]["sihua_source_comparison"]
    difference = next(
        d for d in comparison["differences"] if d["transformation"] == "化忌"
    )
    assert difference["compared_star"] == "天相"
    path = difference["compared_position"]["calculation_path"] + ".mutagen"
    receipt = payload["run_metadata"]

    def claim(value):
        return CalculationClaim(
            path=path,
            value=value,
            run_id=receipt["run_id"],
            business_output_sha256=receipt["business_output_sha256"],
        )

    assert (
        verify_calculation_claims(payload, [claim(None)])["status"]
        == "verified_structured_facts"
    )
    assert verify_calculation_claims(payload, [claim("化忌")])["status"] == "rejected"


def test_rules_starter_can_drive_a_real_request_without_inventing_missing_inputs():
    spec = next(spec for spec in CATALOG if spec.key == "ziwei_rules")
    params = example_input(spec)
    assert params == {"year_stem": "庚", "rule_profile": "quanshu_v2_excerpt"}
    payload = execute_tool(spec, spec.request_model.model_validate(params))
    assert payload["focused_rules"]["sihua"]["化忌"] == "天同"
    assert len(payload["rule_catalogue"]["sihua_source_comparison"]["differences"]) == 2


def test_table_shape_is_twelve_per_star():
    for star, row in ZIWEI_STAR_BRIGHTNESS.items():
        assert len(row) == 12, f"{star} must have 12 branch entries"


def test_lookup_known_iztro_software_cells():
    # 寅-indexed: 寅=0, 午=4, 丑=11 (ZIWEI_BRANCH_SEQUENCE order)
    assert lookup_star_brightness("紫微", "午") == "庙"  # ziweiMaj[4]=miao
    assert lookup_star_brightness("紫微", "寅") == "旺"  # ziweiMaj[0]=wang
    assert lookup_star_brightness("太阳", "戌") == "不"  # taiyangMaj[8]=bu
    assert lookup_star_brightness("天机", "未") == "陷"  # tianjiMaj[5]=xian


def test_lookup_unknown_or_empty_returns_none():
    assert lookup_star_brightness("天魁", "子") is None  # not in table
    assert lookup_star_brightness("擎羊", "寅") is None  # qingyangMin[0]=''
    assert lookup_star_brightness("陀罗", "卯") is None  # tuoluoMin[1]=''
    assert lookup_star_brightness("紫微", "辰X") is None  # bad branch


def test_split_star_mutagen():
    assert split_star_mutagen("紫微化科") == ("紫微", "化科")
    assert split_star_mutagen("太阴化忌") == ("太阴", "化忌")
    assert split_star_mutagen("天府") == ("天府", None)
    assert split_star_mutagen("") == ("", None)
