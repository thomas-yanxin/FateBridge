"""Official printed minutes and original study controls, never rain outcomes."""

import ast
import copy
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fatebridge.validation import meihua_weather_solar_binding as binding
from fatebridge.validation.meihua_weather_calendar_binding import (
    calendar_bound_weather_label,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/meihua_weather_solar_binding_v1"
PROFILE = json.loads((FIXTURE / "profile.json").read_bytes())
CASES = json.loads((FIXTURE / "literal-phase-cases.json").read_bytes())
PROBE = json.loads((FIXTURE / "forged-month-before.json").read_bytes())
MINOR = [r for r in PROFILE["terms"] if r["kind"] == "minor_month_boundary"]


def first():
    return copy.deepcopy(PROBE["original"])


def test_original_reference_and_old_reader_probe_precede_new_validator_execution():
    freeze = json.loads((FIXTURE / "reference-freeze.json").read_bytes())
    assert not freeze["new_module_present"]
    assert not freeze["new_profile_present"]
    assert not freeze["production_solar_engine_executed_by_this_extractor"]
    inputs = json.loads((FIXTURE / "implementation-input-freeze.json").read_bytes())
    assert not inputs["new_validator_executed"]
    assert (
        hashlib.sha256((FIXTURE / "reference-freeze.json").read_bytes()).hexdigest()
        == inputs["reference_freeze_sha256"]
    )
    for name, digest in inputs["selected_files_sha256"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    assert (
        hashlib.sha256((FIXTURE / "forged-month-before.json").read_bytes()).hexdigest()
        == inputs["old_reader_probe_sha256"]
    )
    assert inputs["source_profile_sha256"] == binding.PROFILE_SHA256
    assert inputs["software_guard_is_not_published_accuracy"]
    assert inputs["new_real_world_observations"] == 0
    assert len(PROFILE["terms"]) == 144 and len(MINOR) == 72
    assert len(json.loads((FIXTURE / "pdf-xml-cross-check.json").read_bytes())) == 60


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["instant"])
def test_predeclared_literal_phase_and_guard_cases(case):
    actual = binding.published_solar_month_context(
        datetime.fromisoformat(case["instant"])
    )
    assert (actual["status"], actual["month_branch"], actual["research_season"]) == (
        case["status"],
        case["branch"],
        case["season"],
    )
    assert not actual["unrounded_instant_authenticated"]
    assert not actual["exact_astronomical_accuracy_established"]
    assert (
        not actual["binding_policy"][
            "no_unique_rounding_rule_or_unrounded_instant_inferred"
        ]
        is False
    )


@pytest.mark.parametrize("index", range(72))
@pytest.mark.parametrize("delta", [-2, -1, 0, 1])
def test_all_printed_minor_terms_keep_both_guard_sides_and_coverage_edges(index, delta):
    row = MINOR[index]
    point = datetime.fromisoformat(row["printed_datetime"]) + timedelta(minutes=delta)
    actual = binding.published_solar_month_context(point)
    if delta in {-1, 0}:
        assert actual["status"] == "boundary_resolution_insufficient"
        assert actual["month_branch"] is None and actual["research_season"] is None
        assert actual["overlapping_boundary_guards"] == [row]
    elif (delta == -2 and index == 0) or (delta == 1 and index == 71):
        assert actual["status"] == "outside_two_anchor_coverage"
        assert actual["start_term"] is actual["end_term"] is None
    else:
        expected = MINOR[index - 1] if delta == -2 else row
        assert actual["status"] == "published_minute_context_bound"
        assert actual["start_term"] == expected
        assert actual["month_branch"] == expected["declared_month_branch_after"]
        assert actual["end_term"]["kind"] == "minor_month_boundary"
        assert {s["file_name"] for s in actual["sources"]} == {
            actual["start_term"]["source_file"],
            actual["end_term"]["source_file"],
        }


@pytest.mark.parametrize(
    "row", PROFILE["terms"], ids=lambda c: f"{c['year']}:{c['term']}"
)
def test_reference_facts_remain_bound_to_original_xml_element_and_names(row):
    import xml.etree.ElementTree as ET

    raw = (FIXTURE / row["source_file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["source_sha256"]
    tree = ET.fromstring(raw)
    original = list(tree)[row["index_in_source"]]
    stamp = datetime.fromisoformat(row["printed_datetime"])
    assert (
        int(original.findtext("M")),
        int(original.findtext("D")),
        original.findtext("hm"),
    ) == (stamp.month, stamp.day, stamp.strftime("%H:%M"))
    assert row["source_element"] == f"/{tree.tag}/Data[{row['index_in_source']+1}]"
    assert row["printed_precision"] == "minute"
    assert (row["declared_month_branch_after"] is None) == (row["kind"] == "major")


def test_unchanged_old_reader_accepts_wrong_month_new_binding_rejects_it():
    assert PROBE["old_reader_result_unchanged"]
    assert (
        calendar_bound_weather_label(PROBE["forged"])
        == calendar_bound_weather_label(first())
        == PROBE["old_result"]
    )
    with pytest.raises(ValueError, match="computed_issue_month_branch"):
        binding.solar_calendar_bound_weather_label(PROBE["forged"])
    original = first()
    saved = copy.deepcopy(original)
    output = binding.solar_calendar_bound_weather_label(original)
    solar = output.pop("solar_context_verification")
    assert output == PROBE["old_result"]
    assert original == saved
    assert solar["published_solar_context_verified_under_declared_guard"]
    assert not solar["solar_term_month_or_season_authenticated"]
    assert solar["reference"]["month_branch"] == "子"


@pytest.mark.parametrize("season", [None, "summer", 1, True])
def test_primary_scenario_cannot_substitute_or_omit_published_context(season):
    row = first()
    row["input"]["weather_context"]["season"] = season
    with pytest.raises(ValueError, match="weather_context.season"):
        binding.verify_published_solar_issue_context(row)


def test_unsupplied_scenario_keeps_unknown_season_while_month_is_verified():
    row = first()
    row["scenario"] = "season_not_supplied"
    row["input"]["weather_context"] = None
    actual = binding.verify_published_solar_issue_context(row)
    assert actual["reference"]["research_season"] == "winter"
    assert actual["published_solar_context_verified_under_declared_guard"]
    row["input"]["weather_context"] = {"season": "winter"}
    with pytest.raises(ValueError, match="weather_context.season"):
        binding.verify_published_solar_issue_context(row)


def test_guard_case_stays_unverified_and_does_not_invent_a_month_or_suppress_row():
    row = first()
    row["input"].update(
        analysis_year=2026,
        analysis_month=2,
        analysis_day=4,
        analysis_hour=4,
        analysis_minute=2,
    )
    actual = binding.verify_published_solar_issue_context(row)
    assert not actual["published_solar_context_verified_under_declared_guard"]
    assert actual["reference"]["status"] == "boundary_resolution_insufficient"
    assert actual["reference"]["month_branch"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("analysis_year", 2025.0),
        ("analysis_minute", False),
        ("analysis_hour", "12"),
        ("analysis_timezone", "UTC+08:00"),
    ],
)
def test_original_hong_kong_clock_and_literal_types_are_not_silently_changed(
    field, value
):
    row = first()
    row["input"][field] = value
    with pytest.raises(ValueError):
        binding.verify_published_solar_issue_context(row)


@pytest.mark.parametrize(
    "field,value", [("many_min_count", 2), ("prior_condition", "prolonged_rain")]
)
def test_original_unconditional_context_protocol_is_retained(field, value):
    row = first()
    row["input"]["weather_context"][field] = value
    with pytest.raises(ValueError, match="original_protocol"):
        binding.verify_published_solar_issue_context(row)


def test_unknown_scenario_naive_time_and_unprinted_seconds_are_rejected():
    row = first()
    row["scenario"] = "winning_subset"
    with pytest.raises(ValueError, match="two original"):
        binding.verify_published_solar_issue_context(row)
    for value in [
        datetime(2026, 1, 1),
        datetime.fromisoformat("2026-01-01T12:00:01+08:00"),
    ]:
        with pytest.raises(ValueError):
            binding.published_solar_month_context(value)


def test_reference_is_an_isolated_copy_and_uses_minor_not_major_boundaries():
    point = datetime.fromisoformat("2026-04-21T12:00:00+08:00")
    a = binding.published_solar_month_context(point)
    assert a["month_branch"] == "辰"
    assert a["start_term"]["term"] == "清明" and a["end_term"]["term"] == "立夏"
    a["start_term"]["term"] = "穀雨"
    a["binding_policy"]["season_by_branch"]["辰"] = "summer"
    assert binding.published_solar_month_context(point)["start_term"]["term"] == "清明"


def test_validator_does_not_import_production_calendar_or_weather_calculators():
    tree = ast.parse(Path(binding.__file__).read_text())
    modules = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert not any("core" in name or name.endswith("services") for name in modules)
    assert "meihua_weather_calendar_binding" in modules


def test_reference_hash_drift_is_not_accepted_as_better_agreement(
    monkeypatch, tmp_path
):
    target = tmp_path / "meihua"
    target.mkdir()
    (target / "weather-solar-minutes-hko-v1.json").write_bytes(
        (FIXTURE / "profile.json").read_bytes() + b" "
    )
    binding._profile.cache_clear()
    with monkeypatch.context() as context:
        context.setattr(binding, "files", lambda _: tmp_path)
        with pytest.raises(ValueError, match="content changed"):
            binding.published_solar_month_context(
                datetime.fromisoformat("2026-01-01T12:00:00+08:00")
            )
    binding._profile.cache_clear()
