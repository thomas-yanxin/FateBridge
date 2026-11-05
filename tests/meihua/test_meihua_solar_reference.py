"""Official day labels remain distinct from calculated event instants."""

import asyncio
import copy
import gzip
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from fatebridge.services.divination import calculate_meihua_analysis
from tests.support.transports import SPECS, business, rest, surface_calls

FIXTURE = Path(__file__).parents[1] / "fixtures/meihua_solar_reference_v1"
READING = json.loads((FIXTURE / "source-reading.json").read_text())
CASES = json.loads((FIXTURE / "cases.json").read_text())["cases"]
PATH = "meihua.calendar_policy.solar_term_date_reference"


def compare(term):
    from fatebridge.core.meihua_solar_reference import compare_solar_term_date

    return compare_solar_term_date(
        term, fact_path="calendar_context.current_solar_term"
    )


def layer(context):
    from fatebridge.core.meihua_solar_reference import solar_term_date_reference

    return solar_term_date_reference(context)


def test_reference_precedes_implementation_and_keeps_all_source_bytes():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    assert manifest["implementation_not_present"]
    assert not manifest["expected_published_dates_from_production_calculator"]
    assert manifest["independent_real_observations"] == 0
    for name, expected in manifest["files"].items():
        if str(name).endswith((".py", ".py.txt")):
            continue
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected
    assert manifest["source_date_labels"] == 4800
    assert manifest["publisher_named_solar_events"] == 4


def test_production_transcription_and_all4800_day_comparisons_follow_raw_sources():
    from importlib.resources import files

    raw = files("fatebridge.data").joinpath("meihua/solar-dates-hko-v1.json")
    assert json.loads(raw.read_text()) == READING
    # The supplied noon is synthetic and only tests civil-day correspondence.
    total = 0
    normalizer = str.maketrans(
        {"驚": "惊", "蟄": "蛰", "穀": "谷", "滿": "满", "種": "种", "處": "处"}
    )
    for source in json.loads((FIXTURE / "extraction.json").read_text()):
        p = FIXTURE / source["fixture_file"]
        content = (
            gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes()
        )
        assert hashlib.sha256(content).hexdigest() == source["raw_content_sha256"]
        lines = content.decode("utf-8-sig").splitlines()
        for row in source["rows"]:
            fields = lines[row["source_line"] - 1].split()
            assert fields[-1].translate(normalizer) == row["term"]
            y, m, d = (
                fields[0].replace("年", "-").replace("月", "-").rstrip("日").split("-")
            )
            expected = date(int(y), int(m), int(d)).isoformat()
            assert expected == row["published_date"]
            event = compare(
                {
                    "name": row["term"],
                    "datetime_with_offset": expected + "T12:00:00+08:00",
                }
            )
            assert event["published_date"] == event["computed_date"] == expected
            assert event["comparison_status"] == "published_date_match"
            assert event["source"]["raw_sha256"] == source["raw_content_sha256"]
            total += 1
    assert total == 4800


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_supplied_instant_is_compared_in_fixed8_with_all_disagreements_retained(case):
    original = copy.deepcopy(case["term"])
    event = compare(case["term"])
    assert case["term"] == original
    assert event["computed_date"] == case["expected_computed_date"]
    assert event["published_date"] == case["expected_published_date"]
    assert event["comparison_status"] == case["expected_status"]
    assert event["publisher_named_near_midnight"] is case["publisher_named_event"]
    assert event["actual_datetime_with_offset"] == original["datetime_with_offset"]
    assert (
        event["date_difference_days"]
        == (
            date.fromisoformat(event["computed_date"])
            - date.fromisoformat(event["published_date"])
        ).days
    )
    assert event["fact_path"] == "calendar_context.current_solar_term"
    assert event["actual_ephemeris_model"] == original["ephemeris_model"]


@pytest.mark.parametrize(
    "term",
    [
        None,
        {},
        {"name": "立春"},
        {
            "name": "立春",
            "datetime": "2026-02-04 04:02:00",
            "timezone": "Asia/Shanghai",
        },
        {"name": "立春", "datetime_with_offset": "2026-02-04T04:02:00"},
        {"name": "立春", "datetime_with_offset": "bad"},
        {"name": "立春", "datetime_with_offset": 1},
        {"name": "立春", "date_key": "20260204"},
    ],
)
def test_unknown_or_naive_instants_do_not_get_a_guessed_offset_or_day_agreement(term):
    event = compare(term)
    assert event["comparison_status"] == "actual_instant_unavailable"
    assert event["published_date"] is None
    assert event["date_difference_days"] is None
    assert event["publisher_named_near_midnight"] is None


@pytest.mark.parametrize("year", [1899, 1900, 2101])
def test_outside_table_year_is_not_negative_calendar_or_exactness_evidence(year):
    event = compare(
        {"name": "小寒", "datetime_with_offset": f"{year}-01-06T12:00:00+08:00"}
    )
    assert event["comparison_status"] == "outside_published_year_range"
    assert event["published_date"] is event["source"] is None


def test_unknown_term_name_is_not_inferred_from_its_day():
    event = compare(
        {"name": "unknown", "datetime_with_offset": "2026-02-04T04:02:00+08:00"}
    )
    assert event["comparison_status"] == "term_not_in_reference"
    assert event["published_date"] is None


def test_partial_comparison_and_day_agreement_do_not_certify_exactness():
    known = CASES[7]["term"]
    result = layer({"current_solar_term": known})
    assert result["status"] == "partially_compared"
    assert result["compared_record_count"] == 1
    assert not result["all_selected_records_compared"]
    assert not result["published_date_match_certifies_exactness"]
    assert not result["exact_astronomical_accuracy_established"]
    assert not result["predictive_efficacy_established"]
    assert result["source_uncertainty_interval_seconds"] is None
    assert result["original_solar_instants_retained"]
    assert result["original_month_branch_retained"]
    assert result["original_lunar_seed_retained"]
    assert not result["alternate_event_time_inferred"]
    assert layer({})["status"] == "not_compared"


def test_metadata_is_independent_of_input_mutation_and_later_calls():
    context = {
        "current_solar_term": CASES[0]["term"],
        "next_solar_term": CASES[7]["term"],
    }
    original = copy.deepcopy(context)
    a = layer(context)
    assert context == original
    a["events"][0]["source"]["url"] = "poison"
    a["caveat_source"]["url"] = "poison"
    b = layer(context)
    assert b["events"][0]["source"]["url"].startswith("https://www.hko.gov.hk/")
    assert b["caveat_source"]["url"].startswith("https://www.hko.gov.hk/")
    assert b["status"] == "published_date_disagreement"


@pytest.mark.parametrize("topic", ["general", "weather"])
def test_actual_service_explains_disagreement_without_replacing_instant_or_cast(topic):
    out = calculate_meihua_analysis(
        analysis_year=1912,
        analysis_month=11,
        analysis_day=22,
        analysis_hour=12,
        analysis_timezone="UTC+08:00",
        interpretation_topic=topic,
    )
    assert "error" not in out
    ref = out["meihua"]["calendar_policy"]["solar_term_date_reference"]
    assert ref["status"] == "published_date_disagreement"
    event = next(e for e in ref["events"] if e["event_name"] == "小雪")
    assert event["published_date"] == "1912-11-23"
    assert event["computed_date"] == "1912-11-22"
    assert (
        out["calendar_context"]["next_solar_term"]["datetime_with_offset"]
        == event["actual_datetime_with_offset"]
    )
    assert "1912-11-23" in out["summary"] and "1912-11-22" in out["summary"]
    assert out["summary"] == out["interpretation"]["comprehensive_judgement"]
    assert (
        out["interpretation"]["evidence_scope"]["solar_term_date_reference_path"]
        == PATH
    )
    if topic == "weather":
        assert out["interpretation"]["weather"]["single_forecast"] is None


@pytest.mark.parametrize("topic", ["general", "weather"])
def test_new_layer_projects_identically_on_rest_native_mcp_cli(topic, surface_calls):
    payload = {
        "analysis_year": 1912,
        "analysis_month": 11,
        "analysis_day": 22,
        "analysis_hour": 12,
        "analysis_timezone": "UTC+08:00",
        "interpretation_topic": topic,
    }
    fields = [
        PATH,
        "interpretation.evidence_scope",
        "interpretation.solar_term_date_reference_notice",
        "summary",
    ]
    spec = SPECS["meihua_analysis"]
    response, protocol, code, cli = surface_calls(
        spec,
        payload,
        projection={
            **{"fields": fields, "strict_fields": True},
            "response_char_limit": 0,
        },
        cli_first=False,
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(protocol.structured_content)
        == business(cli)
    )


def test_edited_date_cannot_masquerade_as_better_agreement_in_same_version(
    monkeypatch, tmp_path
):
    import fatebridge.core.meihua_solar_reference as module

    edited = copy.deepcopy(READING)
    edited["years"]["1912"]["terms"]["小雪"] = "1912-11-22"
    p = tmp_path / "meihua/solar-dates-hko-v1.json"
    p.parent.mkdir()
    p.write_text(json.dumps(edited, ensure_ascii=False, indent=2) + "\n")
    monkeypatch.setattr(module, "files", lambda _: tmp_path)
    module._profile.cache_clear()
    try:
        with pytest.raises(ValueError, match="profile content changed"):
            compare(CASES[0]["term"])
    finally:
        module._profile.cache_clear()


def test_named_note_stays_visible_even_when_actual_and_published_dates_match():
    published = date.fromisoformat(READING["years"]["2021"]["terms"]["冬至"])
    day = published + timedelta(days=1)
    result = calculate_meihua_analysis(
        analysis_year=day.year,
        analysis_month=day.month,
        analysis_day=day.day,
        analysis_hour=12,
        analysis_timezone="UTC+08:00",
    )
    ref = result["meihua"]["calendar_policy"]["solar_term_date_reference"]
    event = next(x for x in ref["events"] if x["event_name"] == "冬至")
    assert event["comparison_status"] == "published_date_match"
    assert event["publisher_named_near_midnight"] is True
    assert "2021年冬至" in result["summary"]
    assert not ref["published_date_match_certifies_exactness"]


def test_ordinary_ny_local_previous_day_is_not_a_reference_mismatch_notice():
    result = calculate_meihua_analysis(
        analysis_year=2026,
        analysis_month=2,
        analysis_day=3,
        analysis_hour=15,
        analysis_minute=2,
        analysis_timezone="America/New_York",
    )
    ref = result["meihua"]["calendar_policy"]["solar_term_date_reference"]
    assert ref["status"] == "published_dates_match"
    assert "solar_term_date_reference_notice" not in result["interpretation"]


def test_frozen_data_and_supplied_clock_audit_cannot_certify_real_events():
    from fatebridge.validation.meihua_solar_reference import audit_solar_date_reference

    report = audit_solar_date_reference(FIXTURE)
    assert report["selected_checks_passed"]
    assert report["published_date_labels_checked"] == 4800
    assert len(report["case_results"]) == 15
    assert (
        sum(
            c["kind"] == "reused_numerical_fixture_not_observation"
            for c in report["case_results"]
        )
        == 7
    )
    assert report["synthetic_noon_instants_are_not_actual_event_times"]
    assert report["actual_independent_astronomical_event_observations"] == 0
    assert report["new_prospective_real_outcomes"] == 0
    assert not report["physical_calendar_accuracy_established"]
    assert not report["authority_certified"]


def test_changed_raw_reference_is_rejected_before_comparing_dates(tmp_path):
    import shutil

    from fatebridge.validation.meihua_solar_reference import audit_solar_date_reference

    target = tmp_path / "references"
    shutil.copytree(FIXTURE, target)
    p = target / "cases.json"
    p.write_text(p.read_text() + " ")
    with pytest.raises(ValueError, match="Frozen solar-date reference changed"):
        audit_solar_date_reference(target)


@pytest.mark.parametrize("limit", [4096, 8192])
def test_default_bounded_mcp_preserves_new_evidence_in_same_result(limit):
    import hashlib

    from fastmcp import Client

    import fatebridge.mcp_server as mcp

    async def run():
        async with Client(mcp.app) as client:
            reply = await client.call_tool(
                "meihua_analysis",
                {
                    "analysis_year": 1912,
                    "analysis_month": 11,
                    "analysis_day": 22,
                    "analysis_hour": 12,
                    "analysis_timezone": "UTC+08:00",
                    "include_snapshot_text": False,
                    "fields": ["meihua", "interpretation", "summary"],
                    "strict_fields": True,
                    "response_char_limit": limit,
                },
                raise_on_error=False,
            )
            assert not reply.is_error
            receipt = reply.structured_content
            ref = receipt["result_delivery"]
            manifest = json.loads(
                (await client.read_resource(ref["manifest_uri"]))[0].text
            )
            assert (
                manifest["run_metadata"]["run_id"] == receipt["run_metadata"]["run_id"]
            )
            uri = f"fatebridge://results/{ref['result_id']}/fields/{PATH}/0"
            pages = []
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                assert page["result_id"] == ref["result_id"] and page["path"] == PATH
                pages.append(page)
                uri = page["next_uri"]
            raw = "".join(p["text"] for p in pages)
            assert hashlib.sha256(raw.encode()).hexdigest() == pages[-1]["sha256"]
            value = json.loads(raw)
            assert value["status"] == "published_date_disagreement"
            assert (
                next(e for e in value["events"] if e["event_name"] == "小雪")[
                    "published_date"
                ]
                == "1912-11-23"
            )
            assert not value["exact_astronomical_accuracy_established"]

    asyncio.run(run())


def test_actual_month_anchor_is_compared_after_it_leaves_the_adjacent_term_pair():
    out = calculate_meihua_analysis(
        analysis_year=1917,
        analysis_month=12,
        analysis_day=23,
        analysis_hour=12,
        analysis_timezone="UTC+08:00",
    )
    ref = out["meihua"]["calendar_policy"]["solar_term_date_reference"]
    assert len(ref["events"]) == len(ref["selected_record_paths"]) == 4
    assert ref["all_selected_records_compared"]
    assert all(
        e["comparison_status"] == "published_date_match" for e in ref["events"][:2]
    )
    anchor = next(
        e
        for e in ref["events"]
        if e["fact_path"] == "calendar_context.bazi_month_boundary.start_term"
    )
    assert anchor["event_name"] == "大雪"
    assert anchor["comparison_status"] == "published_date_disagreement"
    assert ref["date_disagreement_count"] == 1
    assert "大雪" in out["summary"]


def test_repeated_records_of_one_event_do_not_inflate_disagreement_counts():
    term = copy.deepcopy(CASES[0]["term"])
    context = {
        "current_solar_term": term,
        "next_solar_term": term,
        "bazi_month_boundary": {"start_term": term, "next_term": term},
    }
    ref = layer(context)
    assert ref["compared_record_count"] == 4
    assert ref["compared_reference_event_count"] == 1
    assert ref["date_disagreement_count"] == 1
    assert not ref["same_reference_event_has_multiple_instants"]


def test_different_returned_instants_for_same_event_are_not_silently_resolved():
    from fatebridge.core.meihua_solar_reference import solar_reference_notice

    term = copy.deepcopy(CASES[7]["term"])
    different = {**term, "datetime_with_offset": "2026-02-04T04:03:00+08:00"}
    context = {
        "current_solar_term": term,
        "next_solar_term": term,
        "bazi_month_boundary": {"start_term": different, "next_term": term},
    }
    before = copy.deepcopy(context)
    ref = layer(context)
    assert context == before
    assert ref["same_reference_event_has_multiple_instants"]
    assert ref["status"] == "inconsistent_returned_instants"
    assert not ref["alternate_event_time_inferred"]
    assert "不同交节时刻" in solar_reference_notice(ref)
