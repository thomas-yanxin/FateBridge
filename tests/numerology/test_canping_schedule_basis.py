"""Source quotations, profile differences and compact same-run policy facts."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import evidence_views
from fatebridge.application.projection import project_fields
from fatebridge.core import canping_schedule_basis as basis
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.output_canping_schedule import CanpingScheduleBasis
from fatebridge.core.output_chinese import CanpingTiming
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import NumerologySourceError

FIXTURE = Path(__file__).parents[1] / "fixtures/canping_schedule_basis_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())
READINGS = json.loads((FIXTURE / "verified-readings.json").read_text())
BASE = dict(
    date="2021-11-07",
    time="00:30",
    zone="America/Havana",
    birth_utc_offset="-05:00",
    gender="男",
    use_true_solar_time=False,
)
PROFILES = ["bazi_appendix_v1", "bazi_continuous_v1", "legacy_minggong_v1"]


@pytest.fixture(autouse=True)
def native_model(monkeypatch, tmp_path):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))


def test_primary_excerpts_keep_distinct_books_and_frozen_image_identities():
    assert REFERENCE["frozen_before_implementation"]
    assert (
        hashlib.sha256((FIXTURE / "verified-readings.json").read_bytes()).hexdigest()
        == REFERENCE["readings_sha256"]
    )
    for source in REFERENCE["source_files"]:
        assert (
            hashlib.sha256((FIXTURE / source["file"]).read_bytes()).hexdigest()
            == source["sha256"]
        )
    actual = basis.source_readings()
    actual.pop("_file_sha256")
    assert actual == READINGS
    assert (
        READINGS["sources"]["heluo_najda"]["pdf_sha256"]
        != READINGS["sources"]["sanming_nlc"]["pdf_sha256"]
    )
    excerpts = {c["id"]: c for c in READINGS["clauses"]}
    assert (
        excerpts["heluo_period_distinction"]["text"]
        == "河洛數內只以陽爻九年陰爻六年為大運不用子平之運"
    )
    assert excerpts["sanming_decade_anniversary"]["text"] == "從此算後十週年方換一運"
    assert excerpts["sanming_ten_year_step"]["pdf_page"] == 114
    assert READINGS["target_excerpt_ten_year_step_explicitly_collated"] is False


@pytest.mark.parametrize(
    "profile,applied",
    [
        ("bazi_appendix_v1", ["appendix_month_order", "appendix_integer_rounding"]),
        ("bazi_continuous_v1", ["appendix_month_order"]),
        ("legacy_minggong_v1", []),
    ],
)
def test_actual_profile_does_not_borrow_another_profiles_source_certification(
    profile, applied
):
    value = build_canping_result(**BASE, dayun_method=profile)
    timing = value["canping_timing"]
    b = timing["schedule_basis"]
    assert b["profile_id"] == timing["profile_id"] == profile
    assert b["applied_clause_ids"] == applied
    assert b["bridge_step_years"] == 10
    assert b["target_excerpt_ten_year_step_explicitly_collated"] is False
    assert b["datetime_mapping_is_original_source_formula"] is False
    assert (
        b["whole_book_alignment_established"]
        is b["real_world_efficacy_validated"]
        is False
    )
    for c in b["clauses"]:
        assert (c["role"] == "applied_rule") is (c["id"] in applied)
        if c["source_id"] == "sanming_nlc":
            assert c["role"] != "applied_rule"
    assert (
        next(
            r["facts"]
            for r in value["numerology_evidence"]["rule_trace"]
            if r["rule_id"] == basis.POLICY_ID
        )
        == b
    )
    CanpingTiming.model_validate(timing)
    if profile == "legacy_minggong_v1":
        assert b["has_actual_date_mapping"] is False
        assert b["actual_start_at"] is None and b["age_conversion_result"] is None
        assert timing["first_period"] is None
        assert all(c["role"] == "comparison_not_applied" for c in b["clauses"])
    else:
        assert b["calendar_mapping"]["calendar_policy"] == timing["calendar_policy"]
        assert b["calendar_mapping"]["dst_policy"] == timing["dst_policy"]
        assert b["age_conversion_result"] == timing["calendar_offset"]
        assert b["actual_start_at"] == timing["start_at"]
        assert timing["first_period"] == value["dayun"][0]
        assert len(value["dayun"]) == 12 and len(value["liunian_series"]["rows"]) == 120
        assert len(value["liunian_series"]["year_boundaries"]) == 121
    assert "[配运原典与日期映射]" in value["snapshot_text"]


@pytest.mark.parametrize("profile", PROFILES)
def test_compact_policy_view_is_complete_for_each_profile_without_reading_all_121_boundaries(
    profile,
):
    value = build_canping_result(**BASE, dayun_method=profile)
    spec = next(s for s in CATALOG if s.key == "canping")
    views = evidence_views(spec)
    assert views is not None
    projected = project_fields(
        value, views["timing_policy"]["fields"], strict_fields=True
    )
    spec.output_model.model_validate(projected)
    assert (
        projected["canping_timing"]["schedule_basis"]
        == value["canping_timing"]["schedule_basis"]
    )
    assert "solar_year_context" not in projected["canping_timing"]
    assert "liunian_series" not in projected
    full_periods = project_fields(value, views["periods"]["fields"], strict_fields=True)
    assert full_periods["dayun"] == value["dayun"]


def test_queried_segment_is_not_replaced_with_the_new_first_period_summary():
    value = build_canping_result(**BASE, analysis_datetime="2036-01-01T12:00:00Z")
    timing = value["canping_timing"]
    assert timing["first_period"] == value["dayun"][0]
    assert timing["first_period"]["pillar"] == "戊戌"
    assert timing["selected"]["dayun_index"] == 1
    assert timing["selected"]["dayun_pillar"] == "丁酉"
    timing["first_period"]["verses"]["textShun"] = "detached summary edit"
    assert value["dayun"][0]["verses"]["textShun"] != "detached summary edit"


def test_loaded_source_returns_detached_copies():
    value = basis.source_readings()
    value["clauses"][0]["text"] = "poison"
    assert basis.source_readings()["clauses"][0]["text"] == "雖非希夷著述"


@pytest.mark.parametrize("mutation", ["quote", "source", "role_source", "efficacy"])
def test_nonempty_source_rewriting_fails_before_any_field_projection(
    tmp_path, monkeypatch, mutation
):
    data = deepcopy(READINGS)
    if mutation == "quote":
        data["clauses"][3]["text"] = data["clauses"][3]["text"].replace("不用", "用")
    elif mutation == "source":
        data["clauses"][4]["source_id"] = "heluo_najda"
    elif mutation == "role_source":
        data["target_excerpt_ten_year_step_explicitly_collated"] = True
    else:
        data["real_world_efficacy_validated"] = True
    path = tmp_path / "source-fault.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    basis._collation.cache_clear()
    try:
        monkeypatch.setattr(basis, "COLLATION_PATH", path)
        with pytest.raises(NumerologySourceError):
            build_canping_result(**BASE)
    finally:
        basis._collation.cache_clear()


def test_layout_only_change_gets_its_own_loaded_file_digest(tmp_path, monkeypatch):
    raw = json.dumps(READINGS, ensure_ascii=False, separators=(",", ":")).encode()
    path = tmp_path / "layout-only.json"
    path.write_bytes(raw)
    basis._collation.cache_clear()
    try:
        monkeypatch.setattr(basis, "COLLATION_PATH", path)
        value = build_canping_result(**BASE)["canping_timing"]["schedule_basis"]
        assert value["source_file_sha256"] == hashlib.sha256(raw).hexdigest()
        assert value["source_content_sha256"] == basis.CONTENT_SHA256
    finally:
        basis._collation.cache_clear()


def test_partial_receipts_stay_valid_and_present_source_conflicts_fail():
    value = build_canping_result(**BASE)["canping_timing"]
    b = value["schedule_basis"]
    for k, v in b.items():
        CanpingScheduleBasis.model_validate({k: v})
    changes = [
        dict(profile_id="legacy_minggong_v1"),
        dict(whole_book_alignment_established=True),
        dict(real_world_efficacy_validated=0),
        dict(target_excerpt_ten_year_step_explicitly_collated=True),
    ]
    for change in changes:
        with pytest.raises(ValidationError):
            CanpingScheduleBasis.model_validate({**deepcopy(b), **change})
    bad = deepcopy(b)
    bad["clauses"][4]["source_id"] = "heluo_najda"
    with pytest.raises(ValidationError):
        CanpingScheduleBasis.model_validate(bad)
    for change in [
        dict(profile_id="legacy_minggong_v1"),
        dict(start_at="2021-11-07T00:30:00-04:00"),
        dict(dst_policy="silent_fold_zero"),
        dict(calendar_offset={"whole_years": 1}),
    ]:
        with pytest.raises(ValidationError):
            CanpingTiming.model_validate({**deepcopy(value), **change})


def test_projected_source_start_still_bounds_the_first_period_without_parent_start():
    timing = build_canping_result(**BASE)["canping_timing"]
    projected = {
        "schedule_basis": timing["schedule_basis"],
        "first_period": deepcopy(timing["first_period"]),
    }
    CanpingTiming.model_validate(projected)
    projected["first_period"]["start_at"] = "2021-11-07T00:30:00-04:00"
    with pytest.raises(ValidationError, match="首运摘要"):
        CanpingTiming.model_validate(projected)


def test_projected_legacy_basis_cannot_gain_a_date_summary_without_parent_profile():
    timing = build_canping_result(**BASE, dayun_method="legacy_minggong_v1")[
        "canping_timing"
    ]
    projected = {"schedule_basis": timing["schedule_basis"], "first_period": None}
    CanpingTiming.model_validate(projected)
    projected["first_period"] = {
        "pillar": "戊戌",
        "start_at": "2022-11-07T00:30:00-05:00",
    }
    with pytest.raises(ValidationError, match="旧命宫"):
        CanpingTiming.model_validate(projected)


def test_projected_false_date_mapping_blocks_a_fabricated_summary_without_any_profile():
    with pytest.raises(ValidationError, match="旧命宫"):
        CanpingTiming.model_validate(
            {
                "schedule_basis": {"has_actual_date_mapping": False},
                "first_period": {"start_at": "2022-11-07T00:30:00-05:00"},
            }
        )
