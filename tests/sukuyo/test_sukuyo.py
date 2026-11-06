"""Primary-text examples, calendar boundaries and directed 宿曜 regressions."""

import hashlib
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import (
    MONTH_STARTS,
    RELATION_TEMPLATE,
    SU27_ORDER,
    calendar_mansion,
    day_evidence,
    lunar_mansion,
    relation_between_su27,
    su28_to_su27,
    sukuyo_relation,
)
from fatebridge.services.divination import (
    calculate_sukuyo_compatibility,
    calculate_suzhan_analysis,
)

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = json.loads((ROOT / "tests/data/sukuyo-t1299-reference.json").read_text())


def test_month_starts_against_naoj_and_t1299_birth_example():
    assert MONTH_STARTS == REFERENCE["naoj_month_starts"]
    assert (
        lunar_mansion(2, 5) == "毕"
    )  # T21n1299_p0391b11, not the conflicting 28 table.
    for month, start in enumerate(REFERENCE["naoj_month_starts"], 1):
        assert lunar_mansion(month, 1) == start
        assert lunar_mansion(month, 28) == start


def test_all_27_relations_against_independent_primary_text_example():
    for other, expected in REFERENCE["bi_example"]:
        r = relation_between_su27("毕", other)
        assert r["relation"] == expected
        assert r["rule_trace"][0]["locator"] == "T21n1299_p0391b06-18"
        assert r["distance"] is None


def test_all_729_directed_relations_and_reverse_pairs():
    assert len(SU27_ORDER) == 27 and "牛" not in SU27_ORDER
    for a in SU27_ORDER:
        for b in SU27_ORDER:
            forward, reverse = relation_between_su27(a, b), relation_between_su27(b, a)
            assert forward["pair"] == reverse["pair"]
            assert (forward["offset"] + reverse["offset"]) % 27 == 0
            assert forward["relation"] in RELATION_TEMPLATE
            assert forward["distance"] is None
            assert forward["sequence_group"] == forward["offset"] // 9 + 1


@pytest.mark.parametrize("longitude", [None, 104, 114, float("nan")])
def test_niu_cannot_be_assigned_by_an_invented_longitude_rule(longitude):
    with pytest.raises(ValueError, match="农历月日"):
        su28_to_su27("牛", longitude)


def test_shared_names_and_traditional_aliases():
    assert su28_to_su27("胃") == "胃"
    assert su28_to_su27("畢") == "毕"
    assert sukuyo_relation("斗", "胃")["relation"] == "親"
    with pytest.raises(ValueError):
        relation_between_su27("牛", "胃")


def test_compatibility_uses_lunar_dates_without_a_chart_or_guessed_birth_time(
    monkeypatch,
):
    import fatebridge.services.divination as service

    monkeypatch.setattr(
        service,
        "build_suzhan_result",
        lambda **kw: pytest.fail("Must not derive calendar 宿 from a chart"),
    )
    r = calculate_sukuyo_compatibility(
        person1_date="1990-06-15", person2_date="1992-03-20"
    )
    assert r["su27_basis"] == "t1299_lower_fullmoon27_v1"
    assert r["person1"]["natal_su27"] == "娄"
    assert r["person2"]["natal_su27"] == "氐"
    assert {"natal_su28", "moon_longitude"}.isdisjoint(r["person1"])
    assert {"coordinates", "deprecated_fields"}.isdisjoint(r["interpretation_contract"])
    assert r["person1"]["calendar"]["birth_time_known"] is False
    assert r["person1_to_person2"]["relation"] == "壊"
    assert r["person2_to_person1"]["relation"] == "安"
    assert r["pair"] == "安壊"
    assert not r["validation"]["authority_certified"]
    assert r["validation"]["real_world_prediction"] == "not_established"


def test_same_mansion_does_not_turn_into_a_personality_or_success_claim():
    r = calculate_sukuyo_compatibility(
        person1_date="1990-06-15", person2_date="1990-06-15"
    )
    assert r["pair"] == "命"
    assert r["person1_to_person2"]["traditional_assessment"] == "caution"
    assert "性格相同" not in r["summary"] and "概率" not in r["summary"]


def test_timezone_conversion_changes_chinese_calendar_day_at_exact_boundary():
    before = calendar_mansion("2025-01-28", "15:59:59", "UTC")
    after = calendar_mansion("2025-01-28", "16:00:00", "UTC")
    assert [before["lunar_month"], before["lunar_day"]] == [12, 29]
    assert [after["lunar_month"], after["lunar_day"]] == [1, 1]
    assert after["calendar_date"] == "2025-01-29"
    assert after["natal_su27"] == "室"
    assert (
        calendar_mansion("2025-01-29", "00:00:00", "+08:00")["natal_su27"]
        == after["natal_su27"]
    )


@pytest.mark.parametrize(
    "d,t,z",
    [
        ("2024-03-10", "02:30:00", "America/New_York"),
        ("2024-11-03", "01:30:00", "America/New_York"),
    ],
)
def test_ambiguous_unknown_or_nonexistent_time_cannot_select_a_calendar_day(d, t, z):
    with pytest.raises(ValueError):
        calendar_mansion(d, t, z)


def test_leap_month_is_partial_until_an_explicit_convention_is_selected():
    params = dict(person1_date="2025-07-25", person2_date="2025-03-04")
    partial = calculate_sukuyo_compatibility(**params)
    assert partial["status"] == "partial" and partial["pair"] is None
    assert partial["person1"]["natal_su27"] is None
    assert partial["person1"]["calendar"]["candidate_su27"] == "鬼"
    assert partial["person2"]["natal_su27"] == "毕"
    assert partial["person1_to_person2"] is None
    explicit = calculate_sukuyo_compatibility(
        **params, leap_month_policy="repeat_month"
    )
    assert explicit["status"] == "computed"
    assert explicit["person1"]["natal_su27"] == "鬼"
    assert explicit["person1"]["calendar"]["limitations"]


@pytest.mark.parametrize("d", ["1900-12-31", "2100-01-01", "2025-02-30"])
def test_outside_declared_calendar_scope_or_invalid_date_fails(d):
    with pytest.raises(ValueError):
        calendar_mansion(d)


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_every_published_hko_day_in_1901_2099_and_chinese_supplement():
    spec = importlib.util.spec_from_file_location(
        "sukuyo_reference_builder", ROOT / "scripts/sukuyo/fetch_sukuyo_reference.py"
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    sources = builder.read_sources()
    manifest = json.loads((ROOT / "tests/data/sukuyo_hko_v1/manifest.json").read_text())
    for source in manifest["sources"]:
        assert hashlib.sha256(sources[source["file"]]).hexdigest() == source["sha256"]
    expected = builder.published_rows(sources)
    assert len(expected) == 72684 == manifest["reference_days"]
    for civil, year, month, day, leap in expected:
        actual = calendar_mansion(civil)
        assert [
            actual["lunar_year"],
            actual["lunar_month"],
            actual["lunar_day"],
            actual["is_leap_month"],
        ] == [year, month, day, leap], civil
    assert calendar_mansion("2069-12-30")["lunar_day"] == 17


@pytest.mark.parametrize(
    "civil,expected",
    [
        ("1933-07-22", [5, 30, True]),
        ("1954-11-25", [11, 1, False]),
        ("1978-09-02", [7, 30, False]),
    ],
)
def test_published_calendar_corrections_change_the_mansion_input(civil, expected):
    r = calendar_mansion(civil)
    assert [r["lunar_month"], r["lunar_day"], r["is_leap_month"]] == expected
    assert r["calendar_correction"] == "sukuyo_hko_corrections_v1"


def test_suzhan_exposes_calendar_evidence_and_default_equatorial_research_model():
    r = calculate_suzhan_analysis(date="2025-03-04", time="12:00:00", zone="+08:00")
    assert r["sukuyo"]["day_mansion"] == "毕"
    assert r["sukuyo"]["nature"] == "安重"
    assert r["sukuyo"]["weekday"]["luminary"] == "火"
    assert r["sukuyo"]["lunar_half"] == "白" and r["sukuyo"]["half_day"] == 5
    assert r["params"]["su28Method"] == "modern_equatorial_research_anchors_v1"
    assert "当日视赤经、不等宽宿界" in r["snapshot_text"]
    assert len(r["rulesets"]["unresolved"]) >= 3


def test_seven_nature_groups_and_special_days_match_upper_volume():
    for group, mansions in REFERENCE["upper_natures"].items():
        for mansion in mansions:
            r = day_evidence(
                {
                    "natal_su27": mansion,
                    "calendar_date": "2025-03-02",
                    "calendar_timezone": "UTC+08:00",
                    "lunar_day": 3,
                }
            )
            assert r["nature"] == group
    for label, sequence in REFERENCE["upper_special_days"].items():
        for i, mansion in enumerate(sequence):
            day = date(2025, 3, 2 + i).isoformat()
            r = day_evidence(
                {
                    "natal_su27": mansion,
                    "calendar_date": day,
                    "calendar_timezone": "UTC+08:00",
                    "lunar_day": 3 + i,
                }
            )
            assert label in r["special_day_labels"]


def test_personal_sanjiu_day_preserves_upper_lower_ye_conflict():
    context = calendar_mansion("2025-03-04")  # 毕, nine steps after 女.
    r = day_evidence(context, natal_mansion="女")
    assert r["personal_day"]["relation"]["relation"] == "業"
    assert r["personal_day"]["textual_conflict"] is True
    assert "皆吉祥" in r["personal_day"]["upper_volume"]["meaning"]
    assert "不成就" in r["personal_day"]["lower_volume_variant"]["meaning"]
    r = calculate_suzhan_analysis(
        date="2025-03-04", time="12:00:00", natal_mansion="女"
    )
    assert r["sukuyo"]["personal_day"]["textual_conflict"] is True


def test_same_run_claim_checker_rejects_invented_mansion_and_reversed_relation():
    from fatebridge.application.execution import execute_tool
    from fatebridge.core.execution_context import ExecutionOptions
    from fatebridge.services.tool_catalog import CATALOG
    from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims

    spec = next(s for s in CATALOG if s.key == "sukuyo_compatibility")
    result = execute_tool(
        spec,
        spec.request_model.model_validate(
            {"person1_date": "1990-06-15", "person2_date": "1992-03-20"}
        ),
        options=ExecutionOptions(as_of="2026-10-22T12:00:00+08:00"),
    )
    receipt = result["run_metadata"]

    def claim(path, value):
        return CalculationClaim(
            path=path,
            value=value,
            run_id=receipt["run_id"],
        )

    valid = [
        claim("person1.natal_su27", "娄"),
        claim("person1_to_person2.relation", "壊"),
    ]
    assert (
        verify_calculation_claims(result, valid)["status"]
        == "verified_structured_facts"
    )
    wrong = [
        claim("person1.natal_su27", "斗"),
        claim("person1_to_person2.relation", "安"),
    ]
    assert verify_calculation_claims(result, wrong)["status"] == "rejected"
    assert len(verify_calculation_claims(result, wrong)["errors"]) == 2


def test_suzhan_guolao_mode_loads_bundled_stars_with_operator_ephemeris_env(
    monkeypatch, tmp_path
):
    import os

    from fatebridge.core import ephemeris_runtime

    monkeypatch.setattr(
        ephemeris_runtime, "_configured_path", ephemeris_runtime._configured_path
    )
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    ephemeris_runtime.configure_ephemeris_path(str(tmp_path))
    result = calculate_suzhan_analysis(
        date="2025-03-04", time="12:00:00", zone="+08:00", szchart=1
    )
    assert "error" not in result, result
    assert result["chart"]["ok"] is True
    assert result["sukuyo"]["day_mansion"] == "毕"
    assert os.environ["SE_EPHE_PATH"] == str(tmp_path)
