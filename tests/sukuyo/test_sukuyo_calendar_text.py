"""Third-round primary-source and context-omission counterexamples."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.execution_context import ExecutionOptions
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_calendar_text import (
    calendar_day_evidence,
    month_table_variant,
    source_bundle,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from fatebridge.validation.sukuyo import (
    required_quote_paths,
    verify_sukuyo_context_claims,
)

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "data/sukuyo-t1299-calendar-primary.json").read_text()
)
ALIASES = str.maketrans("虛婁畢參張軫", "虚娄毕参张轸")


def test_every_printed_month_table_cell_matches_its_literal_source_row():
    assert source_bundle()["source_sha256"] == FIXTURE["source_sha256"]
    count = 0
    for day, row in enumerate(FIXTURE["printed_month_table"], 1):
        expected = row["text"].split("日", 1)[1].strip()
        assert len(expected) == 12
        for month, name in enumerate(expected, 1):
            r = month_table_variant(month, day, "室")
            assert r["literal_mansion"] == name
            assert r["table_mansion_28"] == name.translate(ALIASES)
            assert r["locator"] == row["locator"]
            assert not r["applied_to_sanjiu"]
            count += 1
    assert count == 360


def test_source_table_counterexamples_do_not_overwrite_the_selected_27_system():
    # Printed 2/5=胃 disagrees with T1299's own 2/5=畢 example.
    # Printed 12/5=牛 cannot be silently removed or assigned by longitude.
    for case in FIXTURE["literal_examples"]:
        r = month_table_variant(case["month"], case["day"], case["selected_27"])
        assert r["table_mansion_28"] == case["printed_mansion"]
        assert r["reference_month_day_mansion_27"] == case["selected_27"]
        assert r["differs_from_selected_27"] and not r["applied_to_sanjiu"]
    c = calendar_mansion("2025-03-04")
    assert c["natal_su27"] == "毕"
    assert c["source_table_variant"]["table_mansion_28"] == "胃"
    c = calendar_mansion("2025-07-25")
    assert c["natal_su27"] is None
    assert not c["source_table_variant"]["reference_is_primary_result"]


def test_all_30_day_names_and_both_volume_name_variants():
    upper = "建名 得财 威力 猛武 圆满 求名 友朋 大战 凶猛 善法 慈猛 名闻 最胜 勇猛 吉祥".split()
    lower = "建名 得财 威力 猛武 圆满 求名 朋友 力战 凶猛 善法 慈猛 名闻 最胜 勇猛 吉相".split()
    for day in range(1, 31):
        r = calendar_day_evidence(day)
        assert r["upper_name"] == upper[(day - 1) % 15]
        assert r["lower_name"] == lower[(day - 1) % 15]
        assert r["half_day"] == (day - 1) % 15 + 1
        assert r["lunar_half"] == ("白" if day <= 15 else "黑")
        assert r["name_variant"] == (r["upper_name"] != r["lower_name"])
        assert r["clock_evaluation_status"] == "not_computed"


def test_verse_abbreviation_uses_explicit_inline_gloss_without_rewriting_literal():
    texts = "\n".join(c["text"] for c in FIXTURE["clauses"])
    assert "十一日夜" in texts and "一夜十五晝" in texts
    for day in (1, 11):
        r = calendar_day_evidence(day)
        assert r["prose_verse_time_variant"]
        assert not r["prose_verse_time_semantic_conflict"]
        note = r["verse_abbreviation_resolution"]
        assert note["locator"] == "T21n1299_p0393c26"
        assert "所謂一夜者，十一夜也" in note["source_excerpt"]
        assert note["applies_to_current_lunar_day"] is (day == 11)
        witnesses = {v["witness"] for v in r["time_restrictions"]}
        assert witnesses == (
            set()
            if day == 1
            else {
                "upper_prose",
                "lower_prose",
                "upper_verse",
                "lower_verse",
                "lower_named_day",
            }
        )
        if day == 11:
            assert {v["release_after"] for v in r["time_restrictions"]} == {"midnight"}
            verses = [
                v for v in r["time_restrictions"] if v["witness"].endswith("verse")
            ]
            assert all(
                v["literal_lunar_day"] == 1 and v["interpreted_lunar_day"] == 11
                for v in verses
            )
            assert all("一夜十五晝" in v["source_excerpt"] for v in verses)
    r = calendar_day_evidence(8)
    assert not r["prose_verse_time_variant"]
    assert len(r["time_restrictions"]) == 5
    assert {v["release_after"] for v in r["time_restrictions"]} == {"midday"}


def test_conditional_day_lists_retain_source_differences():
    # 14 appears only in lower prose's conditional list; 29 in upper's.
    for day, expected in [
        (14, ["unlisted", "conditional"]),
        (29, ["conditional", "unlisted"]),
        (19, ["unlisted", "conditional"]),
    ]:
        r = calendar_day_evidence(day)
        assert r["classification_variant"]
        assert [v["assessment"] for v in r["classifications"]] == expected


def test_named_day_activity_layer_is_independent_of_the_mansion():
    c = {
        "natal_su27": "参",
        "calendar_date": "2025-03-04",
        "calendar_timezone": "UTC+08:00",
        "lunar_day": 7,
    }
    r = day_evidence(c, activity="travel", activity_details=["long_distance_journey"])
    layer = next(
        v for v in r["activity_assessment"]["layers"] if v["layer"] == "named_day"
    )
    assert layer["status"] == "caution"
    rules = [
        v
        for v in r["activity_assessment"]["matched_rules"]
        if v["layer"] == "named_day"
    ]
    assert len(rules) == 1 and rules[0]["locator"] == "T21n1299_p0393b11-13"
    c["lunar_day"] = 2
    r = day_evidence(c, activity="commerce")
    assert r["calendar_day"]["upper_name"] == "得财"
    assert (
        next(
            v for v in r["activity_assessment"]["layers"] if v["layer"] == "named_day"
        )["status"]
        == "uncovered"
    )
    c["natal_su27"] = "奎"
    assert all(
        "结交" not in s for s in day_evidence(c)["traditional_activity_examples"]
    )


def test_native_reading_retains_each_matched_clause_and_time_caveat():
    r = day_evidence(calendar_mansion("2025-03-04"), "奎", "marriage")
    text = r["reading_text"]
    assert "历日27宿为毕" in text and "28宿表此格为胃" in text
    assert r["weekday"]["basis"] == "modern_utc_plus08_civil_midnight"
    assert not r["weekday"]["classical_daybreak_boundary_acceptance"]
    assert "原典平明日界尚未核定" in text
    assert "宜忌冲突" in text and "尚未换算成民用钟时" in text
    for rule in r["activity_assessment"]["matched_rules"]:
        assert rule["rule_id"] in text and rule["locator"] in text
    c = calendar_mansion("2025-07-25")
    text = day_evidence(c)["reading_text"]
    assert "农历2025年闰6月1日" in text and "候选鬼未作为确定宿应用" in text
    assert "白一夜／白十一夜" in text and "None" not in text


def test_snapshot_uses_resolved_coordinates_including_zero_gps_override():
    from fatebridge.services.divination import calculate_suzhan_analysis

    r = calculate_suzhan_analysis(
        date="2025-03-04",
        time="12:00:00",
        lat="31n13",
        lon="121e28",
        gps_lat=0.0,
        gps_lon=0.0,
    )
    assert r["params"]["birthLongitude"] == r["params"]["birthLatitude"] == 0.0
    assert "经纬度：0.0 0.0" in r["snapshot_text"]
    assert "经纬度：121e28 31n13" not in r["snapshot_text"]


@pytest.mark.parametrize("value", [0, 31, 1.5, True])
def test_invalid_day_cannot_be_coerced_or_wrapped(value):
    with pytest.raises(ValueError):
        calendar_day_evidence(value)


def payload(tool="suzhan", **changes):
    spec = next(s for s in CATALOG if s.key == tool)
    params = (
        {
            "date": "2025-03-04",
            "time": "12:00:00",
            "zone": "+08:00",
            "natal_mansion": "奎",
            "activity": "marriage",
        }
        if tool == "suzhan"
        else {"person1_date": "1990-06-15", "person2_date": "1992-03-20"}
    )
    return execute_tool(
        spec,
        spec.request_model.model_validate({**params, **changes}),
        options=ExecutionOptions(as_of="2026-10-22T12:00:00+08:00"),
    )


def quotes(result, focus):
    receipt = result["run_metadata"]
    out = []
    for path in required_quote_paths(focus):
        value = result
        for key in path.split("."):
            value = value[key]
        out.append(
            CalculationClaim(
                path=path,
                value=value,
                run_id=receipt["run_id"],
            )
        )
    return out


def test_context_checker_rejects_cherry_picked_true_marriage_clause():
    result = payload()
    claims = quotes(result, "activity")
    assert (
        verify_sukuyo_context_claims(result, claims, focus="activity")["status"]
        == "verified_context_complete_quotes"
    )
    receipt = result["run_metadata"]
    good = next(
        (i, r)
        for i, r in enumerate(result["sukuyo"]["activity_assessment"]["matched_rules"])
        if r["assessment"] == "favorable"
    )
    partial = CalculationClaim(
        path=f"sukuyo.activity_assessment.matched_rules.{good[0]}",
        value=good[1],
        run_id=receipt["run_id"],
    )
    assert (
        verify_calculation_claims(result, [partial])["status"]
        == "verified_structured_facts"
    )
    # A genuinely true isolated quotation does not preserve interpretation context.
    report = verify_sukuyo_context_claims(result, [partial], focus="activity")
    assert report["status"] == "rejected" and report["semantic_review_required"]
    assert any(e.get("path") == "sukuyo.activity_assessment" for e in report["errors"])
    changed = deepcopy(claims)
    next(c for c in changed if c.path == "sukuyo.activity_assessment").value[
        "evidence_status"
    ] = "favorable"
    assert (
        verify_sukuyo_context_claims(result, changed, focus="activity")["status"]
        == "rejected"
    )


def test_context_checker_requires_both_directions_and_original_unprojected_run():
    result = payload("sukuyo_compatibility")
    claims = quotes(result, "compatibility")
    assert (
        verify_sukuyo_context_claims(result, claims, focus="compatibility")["status"]
        == "verified_context_complete_quotes"
    )
    assert (
        verify_sukuyo_context_claims(
            result,
            [c for c in claims if c.path != "person2_to_person1"],
            focus="compatibility",
        )["status"]
        == "rejected"
    )
    assert (
        verify_sukuyo_context_claims(
            {k: v for k, v in result.items() if k != "snapshot_text"},
            claims,
            focus="compatibility",
        )["status"]
        == "rejected"
    )
    assert (
        verify_sukuyo_context_claims(
            result, claims + claims[:1], focus="compatibility"
        )["status"]
        == "rejected"
    )
    claims[0].run_id = "another-run"
    assert (
        verify_sukuyo_context_claims(result, claims, focus="compatibility")["status"]
        == "rejected"
    )


def test_partial_leap_context_is_quotable_without_certifying_a_mansion():
    result = payload("sukuyo_compatibility", person1_date="2025-07-25")
    assert result["status"] == "partial" and result["person1_to_person2"] is None
    report = verify_sukuyo_context_claims(
        result, quotes(result, "compatibility"), focus="compatibility"
    )
    assert report["status"] == "verified_context_complete_quotes"
    assert report["semantic_review_required"] and not report["authority_certified"]


def test_lower_conditional_and_doctrinal_context_cannot_be_omitted_or_promoted():
    result = payload(activity="commerce")
    claims = quotes(result, "activity")
    assert (
        verify_sukuyo_context_claims(result, claims, focus="activity")["status"]
        == "verified_context_complete_quotes"
    )
    for omitted in (
        "sukuyo.lower_mansion_day",
        "sukuyo.conjunction_doctrine",
        "sukuyo.palace_reference",
    ):
        assert (
            verify_sukuyo_context_claims(
                result, [c for c in claims if c.path != omitted], focus="activity"
            )["status"]
            == "rejected"
        )
    changed = deepcopy(claims)
    value = next(c for c in changed if c.path == "sukuyo.activity_assessment").value
    value["conditional_rules"][0]["applied_to_aggregate"] = True
    assert (
        verify_sukuyo_context_claims(result, changed, focus="activity")["status"]
        == "rejected"
    )


def test_hinoo_candidates_cannot_be_omitted_or_promoted_by_quotation():
    result = payload(
        "sukuyo_compatibility",
        person1_date="2024-08-04",
        person2_date="2024-08-04",
        calendar_profile="hinoo_t1299_host27",
        person2_calendar_day_part="second_half",
    )
    assert result["pair"] is None and result["status"] == "partial"
    claims = quotes(result, "compatibility")
    assert (
        verify_sukuyo_context_claims(result, claims, focus="compatibility")["status"]
        == "verified_context_complete_quotes"
    )
    assert (
        verify_sukuyo_context_claims(
            result,
            [c for c in claims if c.path != "candidate_relation_analysis"],
            focus="compatibility",
        )["status"]
        == "rejected"
    )
    changed = deepcopy(claims)
    next(c for c in changed if c.path == "pair").value = "栄親"
    assert (
        verify_sukuyo_context_claims(result, changed, focus="compatibility")["status"]
        == "rejected"
    )
    changed = deepcopy(claims)
    next(c for c in changed if c.path == "candidate_relation_analysis").value["rows"][
        0
    ]["applied_to_primary"] = True
    assert (
        verify_sukuyo_context_claims(result, changed, focus="compatibility")["status"]
        == "rejected"
    )


@pytest.mark.asyncio
async def test_default_mcp_budget_preserves_the_full_original_context_without_recalculation(
    monkeypatch, tmp_path
):
    from fastmcp import Client

    from fatebridge.application import result_delivery as delivery
    from fatebridge.mcp_server import create_mcp_app
    from fatebridge.services import divination

    monkeypatch.setattr(
        delivery, "RESULT_STORE", delivery.ResultStore(tmp_path / "private")
    )
    async with Client(create_mcp_app()) as client:
        result = await client.call_tool(
            "suzhan",
            {
                "date": "2025-03-04",
                "time": "12:00:00",
                "zone": "+08:00",
                "natal_mansion": "奎",
                "activity": "marriage",
                "fields": None,
                "include_snapshot_text": True,
                "as_of": "2026-10-22T12:00:00+08:00",
            },
        )
        assert not result.is_error
        shaped = result.structured_content
        ref = shaped["result_delivery"]

        def must_not_recalculate(**kwargs):
            pytest.fail("resource reads must reuse the same calculation")

        monkeypatch.setattr(divination, "build_suzhan_result", must_not_recalculate)
        manifest = json.loads((await client.read_resource(ref["manifest_uri"]))[0].text)
        assert manifest["run_metadata"]["run_id"] == shaped["run_metadata"]["run_id"]

        async def read_json_pages(base_uri):
            parts = []
            offset = 0
            while True:
                page = json.loads(
                    (await client.read_resource(f"{base_uri}/{offset}"))[0].text
                )
                parts.append(page["text"])
                offset = page["next_offset"]
                if offset is None:
                    break
            text = "".join(parts)
            assert hashlib.sha256(text.encode()).hexdigest() == page["sha256"]
            return json.loads(text)

        original = await read_json_pages(
            f"fatebridge://results/{ref['result_id']}/pages"
        )
        assert original["run_metadata"] == manifest["run_metadata"]
        inline_metadata = deepcopy(shaped["run_metadata"])
        runtime = inline_metadata["runtime"]
        if "delivery_path" in runtime:
            assert runtime["delivery_path"] == "run_metadata.runtime"
            assert runtime["delivery_path"] in ref["deferred_fields"]
            restored = await read_json_pages(
                f"fatebridge://results/{ref['result_id']}/fields/{runtime['delivery_path']}"
            )
            assert restored == original["run_metadata"]["runtime"]
            assert (
                len(restored["ephemeris"]["files"]) == runtime["ephemeris_files_count"]
            )
            assert (
                restored["ephemeris"]["sha256"] == runtime["ephemeris_inventory_sha256"]
            )
            assert restored["environment_sha256"] == runtime["environment_sha256"]
            inline_metadata["runtime"] = restored
        evidence = inline_metadata.get("calculation_evidence")
        if evidence and "delivery_path" in evidence:
            path = evidence["delivery_path"]
            assert path == "run_metadata.calculation_evidence"
            assert path in ref["deferred_fields"]
            inline_metadata["calculation_evidence"] = await read_json_pages(
                f"fatebridge://results/{ref['result_id']}/fields/{path}"
            )
        assert original["run_metadata"] == inline_metadata
        assert (
            original["sukuyo"]["calendar_day"]["clock_evaluation_status"]
            == "not_computed"
        )
        assert (
            original["sukuyo"]["activity_assessment"]["evidence_status"] == "conflicted"
        )
        assert (
            verify_sukuyo_context_claims(
                original, quotes(original, "activity"), focus="activity"
            )["status"]
            == "verified_context_complete_quotes"
        )


def test_context_checker_requires_six_palace_transit_and_joint_reading_limits():
    result = payload(natal_mansion="娄")
    complete = quotes(result, "activity")
    assert (
        verify_sukuyo_context_claims(result, complete, focus="activity")["status"]
        == "verified_context_complete_quotes"
    )
    incomplete = [
        claim for claim in complete if claim.path != "sukuyo.six_palace_reference"
    ]
    report = verify_sukuyo_context_claims(result, incomplete, focus="activity")
    assert report["status"] == "rejected"
    assert {
        "code": "missing_interpretation_context",
        "path": "sukuyo.six_palace_reference",
    } in report["errors"]
    assert report["semantic_review_required"]


def test_context_checker_requires_taibai_missing_row_and_nonphysical_limits():
    result = payload(date="2025-02-07")
    reference = result["sukuyo"]["taibai_direction_reference"]
    assert reference["lunar_day"] == 10
    assert reference["witnesses"][1]["status"] == "row_deleted_in_apparatus"
    complete = quotes(result, "activity")
    assert (
        verify_sukuyo_context_claims(result, complete, focus="activity")["status"]
        == "verified_context_complete_quotes"
    )
    report = verify_sukuyo_context_claims(
        result,
        [
            claim
            for claim in complete
            if claim.path != "sukuyo.taibai_direction_reference"
        ],
        focus="activity",
    )
    assert report["status"] == "rejected"
    assert {
        "code": "missing_interpretation_context",
        "path": "sukuyo.taibai_direction_reference",
    } in report["errors"]
    assert report["semantic_review_required"]
