"""The selected source's inline gloss must not become a fabricated conflict."""

import json
from pathlib import Path

from fatebridge.core.sukuyo import calendar_mansion, day_evidence, rulesets
from fatebridge.core.sukuyo_calendar_text import calendar_day_evidence, source_bundle
from fatebridge.services.tool_catalog import CATALOG

PRIMARY = json.loads(
    (Path(__file__).parents[1] / "data/sukuyo-time-gloss-primary.json").read_text()
)


def test_all_four_time_witnesses_and_release_references_have_primary_windows():
    bundle = source_bundle()
    assert bundle["source_sha256"] == PRIMARY["source_sha256"]
    refs = {r["witness"]: r for r in PRIMARY["passages"]}
    assert len(bundle["timing_witnesses"]) == len(refs) == 4
    for w in bundle["timing_witnesses"]:
        ref = refs[w["witness"]]
        assert w["locator"] == ref["locator"]
        assert w["source_excerpt"] in ref["text"]
        assert w["release_locator"] == ref["release_locator"]
        assert w["release_excerpt"] == ref["release_text"]
        assert len(w["entries"]) == 8
    note = bundle["verse_abbreviation_resolution"]
    assert note["source_excerpt"] == PRIMARY["inline_note"]["text"]
    assert note["locator"] == PRIMARY["inline_note"]["locator"]
    assert PRIMARY["inline_note"]["xml_fragment"].startswith('<note place="inline">')


def test_all_30_effective_day_sets_agree_with_explicit_prose_and_source_note():
    expected_nights = set(PRIMARY["expected_effective_night_days"])
    expected_days = set(PRIMARY["expected_effective_daylight_days"])
    actual_nights = set()
    actual_days = set()
    for day in range(1, 31):
        r = calendar_day_evidence(day)
        if r["time_restrictions"]:
            phases = {x["phase"] for x in r["time_restrictions"]}
            assert len(phases) == 1
            (actual_nights if phases == {"night"} else actual_days).add(day)
            assert {x["witness"] for x in r["time_restrictions"]} >= {
                "upper_prose",
                "upper_verse",
                "lower_prose",
                "lower_verse",
            }
        assert not r["prose_verse_time_semantic_conflict"]
        assert r["clock_evaluation_status"] == "not_computed"
    assert actual_nights == expected_nights == {4, 11, 18, 25}
    assert actual_days == expected_days == {8, 15, 22, 29}
    assert [
        d for d in range(1, 31) if calendar_day_evidence(d)["prose_verse_time_variant"]
    ] == PRIMARY["literal_variant_days"]


def test_direct_lower_gloss_and_upper_parallel_reading_are_distinguished():
    rows = {r["witness"]: r for r in calendar_day_evidence(11)["time_restrictions"]}
    assert rows["lower_verse"]["interpretation_status"] == "direct_lower_inline_gloss"
    assert (
        rows["upper_verse"]["interpretation_status"]
        == "parallel_prose_and_lower_inline_gloss"
    )
    assert rows["upper_verse"]["release_locator"] == "T21n1299_p0393a15-16"
    assert rows["lower_verse"]["release_locator"] == "T21n1299_p0393c27-28"


def test_first_night_native_reading_has_no_fabricated_verse_restriction():
    first = day_evidence(calendar_mansion("2025-01-29"))
    eleventh = day_evidence(calendar_mansion("2025-02-08"))
    assert first["calendar_day"]["lunar_day"] == 1
    assert eleventh["calendar_day"]["lunar_day"] == 11
    assert first["calendar_day"]["time_restrictions"] == []
    assert "未据省文另加初一夜限制" in first["reading_text"]
    assert "上卷偈文另列此日夜的限制" not in first["reading_text"]
    assert "下卷偈文另列此日夜的限制" not in first["reading_text"]
    assert "上卷偈文另列此日夜的限制" in eleventh["reading_text"]
    assert "下卷偈文另列此日夜的限制" in eleventh["reading_text"]


def test_resolved_gloss_remains_published_but_not_listed_as_unresolved_conflict():
    result = rulesets()
    assert (
        result["calendar_day"]["id"]
        == source_bundle()["id"]
        == "t1299_calendar_day_evidence_v5"
    )
    assert not any("白月夜限" in text for text in result["unresolved"])
    assert result["textual_resolutions"][0]["locator"] == "T21n1299_p0393c26"
    assert result["textual_resolutions"][0]["literal_expression"] == "一夜"


def test_mutating_returned_gloss_or_witness_does_not_change_later_results():
    first = calendar_day_evidence(11)
    first["verse_abbreviation_resolution"]["interpreted_lunar_day"] = 1
    first["time_restrictions"][0]["literal_lunar_day"] = 99
    assert (
        calendar_day_evidence(11)["verse_abbreviation_resolution"][
            "interpreted_lunar_day"
        ]
        == 11
    )
    assert calendar_day_evidence(11)["time_restrictions"][0]["literal_lunar_day"] == 11
    root = rulesets()
    root["textual_resolutions"][0]["source_excerpt"] = "tampered"
    assert (
        rulesets()["textual_resolutions"][0]["source_excerpt"]
        == PRIMARY["inline_note"]["text"]
    )


def test_live_schema_exposes_abbreviation_literal_interpretation_and_status():
    spec = next(s for s in CATALOG if s.key == "suzhan")
    defs = spec.output_model.model_json_schema()["$defs"]
    assert "verse_abbreviation_resolution" in defs["SukuyoCalendarDay"]["properties"]
    assert (
        "prose_verse_time_semantic_conflict" in defs["SukuyoCalendarDay"]["properties"]
    )
    assert "literal_lunar_day" in defs["SukuyoTimeRestriction"]["properties"]
    assert "interpreted_lunar_day" in defs["SukuyoTimeRestriction"]["properties"]
