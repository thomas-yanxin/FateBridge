"""Frozen official labels, common-mode mutations and immutable-study controls."""

import ast
import copy
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from validation import meihua_weather_calendar_binding as binding
from validation.meihua_weather_trace_binding import bound_weather_label

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/meihua_weather_calendar_binding_v1"
PROFILE = json.loads((FIXTURE / "calendar-profile.json").read_bytes())
ANCHORS = json.loads((FIXTURE / "literal-anchors.json").read_bytes())
OLD = ROOT / "tests/fixtures/meihua_weather_binding_v1/reference.json"


def first():
    return copy.deepcopy(json.loads(OLD.read_bytes())["samples"]["first"])


def test_preimplementation_freeze_and_all_raw_official_references_are_retained() -> (
    None
):
    freeze = json.loads((FIXTURE / "reference-freeze.json").read_bytes())
    assert not freeze["new_module_present"]
    assert not freeze["new_packaged_profile_present"]
    assert not freeze["production_calendar_or_lunar_library_imported"]
    assert freeze["all_printed_date_rows_cross_checked_between_languages"] == 1826
    assert freeze["profile_sha256"] == binding.PROFILE_SHA256
    assert (
        hashlib.sha256((FIXTURE / "calendar-profile.json").read_bytes()).hexdigest()
        == binding.PROFILE_SHA256
    )
    for name, expected in freeze["source_files_sha256"].items():
        assert (
            hashlib.sha256((FIXTURE / "hko" / name).read_bytes()).hexdigest()
            == expected
        )
    assert freeze["original_study_records"] == 2008
    assert freeze["unique_issue_dates"] == freeze["unique_target_dates"] == 1004
    assert freeze["preimplementation_original_study_lunar_label_mismatches"] == []
    assert not freeze["independent_astronomical_accuracy_established"]


def test_each_frozen_reference_date_retains_labels_and_exact_row_provenance() -> None:
    for day in list(PROFILE["dates"]):
        _assert_frozen_reference_date(day)


def _assert_frozen_reference_date(day):
    actual = binding.published_lunar_date_reference(date.fromisoformat(day))
    expected = PROFILE["dates"][day]
    for key, value in expected.items():
        assert actual[key] == value
    for source in actual["sources"]:
        assert (
            hashlib.sha256(
                (FIXTURE / "hko" / source["file_name"]).read_bytes()
            ).hexdigest()
            == source["raw_sha256"]
        )
    expected_source_files = {
        actual[name][language + "_file"]
        for name in ["source_row", "month_anchor"]
        for language in ["english", "chinese"]
    }
    assert {s["file_name"] for s in actual["sources"]} == expected_source_files
    for name in ["source_row", "month_anchor"]:
        row = actual[name]
        for language in ["english", "chinese"]:
            line = (
                (FIXTURE / "hko" / row[language + "_file"])
                .read_text(encoding="utf-8-sig")
                .splitlines()[row[language + "_line"] - 1]
            )
            at = date.fromisoformat(row.get("date", day))
            if language == "english":
                assert line.split()[0] == f"{at.year}/{at.month}/{at.day}"
            else:
                assert line.startswith(f"{at.year}年{at.month}月{at.day}日")
    actual["source_row"]["english_line"] = -1
    assert (
        binding.published_lunar_date_reference(date.fromisoformat(day))["source_row"]
        == expected["source_row"]
    )


def test_literal_new_year_leap_month_and_year_end_anchors() -> None:
    for day, expected in list(ANCHORS.items()):
        row = binding.published_lunar_date_reference(date.fromisoformat(day))
        assert [row[k] for k in ["year", "month", "day", "is_leap_month"]] == expected


def test_unanchored_bootstrap_and_outside_dates_stay_unavailable() -> None:
    for day in ("2022-01-01", "2022-01-02", "2021-12-31", "2027-01-01"):
        with pytest.raises(ValueError, match="outside"):
            binding.published_lunar_date_reference(date.fromisoformat(day))


def test_self_consistent_twelve_year_substitution_preserves_old_result_but_fails_new_binding() -> (
    None
):
    original = first()
    changed = copy.deepcopy(original)
    for key in ["calendar_actual", "calendar_expected"]:
        changed[key]["year"] += 12
    changed["calendar_policy"]["lunar_year"] += 12
    assert bound_weather_label(changed) == bound_weather_label(original)
    with pytest.raises(ValueError, match="calendar_actual"):
        binding.calendar_bound_weather_label(changed)


@pytest.mark.parametrize(
    "field,key,value",
    [
        ("calendar_actual", "year", 2025.0),
        ("calendar_expected", "year", 2037),
        ("calendar_actual", "month", 12),
        ("calendar_expected", "day", 13),
        ("calendar_actual", "is_leap_month", 0),
        ("calendar_policy", "lunar_year", 2037),
        ("calendar_policy", "is_leap_month", True),
        ("calendar_policy", "year_boundary", "lichun"),
        ("calendar_policy", "day_boundary", "zi_start"),
        ("calendar_policy", "timezone", "UTC+08:00"),
        ("calendar_policy", "leap_month_rule", "increment_month_number"),
        ("input", "analysis_year", True),
        ("input", "analysis_timezone", "Asia/Shanghai"),
    ],
)
def test_published_fields_and_declared_date_policy_cannot_be_substituted(
    field: str, key: str, value: bool | float | int | str
) -> None:
    record = first()
    record[field][key] = value
    with pytest.raises(ValueError):
        binding.calendar_bound_weather_label(record)


def test_common_mode_false_leap_flag_is_not_authenticated_by_internal_agreement() -> (
    None
):
    record = first()
    record["calendar_actual"]["is_leap_month"] = record["calendar_expected"][
        "is_leap_month"
    ] = True
    record["calendar_policy"]["is_leap_month"] = True
    assert bound_weather_label(record)["verification"]["mechanical_binding_verified"]
    with pytest.raises(ValueError, match="calendar_actual"):
        binding.calendar_bound_weather_label(record)


def test_original_decision_and_record_are_unchanged_and_full_calendar_gates_stay_false() -> (
    None
):
    record = first()
    saved = copy.deepcopy(record)
    old = bound_weather_label(record)
    result = binding.calendar_bound_weather_label(record)
    assert record == saved
    assert {key: result[key] for key in old} == old
    assert not result["verification"]["calendar_labels_independently_authenticated"]
    scope = result["calendar_verification"]
    assert scope["published_lunar_date_labels_verified"]
    for key in [
        "civil_instant_authenticated",
        "solar_term_month_or_season_authenticated",
        "historical_reference_release_time_authenticated",
        "independent_astronomical_accuracy_established",
        "predictive_efficacy_established",
    ]:
        assert scope[key] is False


def test_reference_integrity_rejects_content_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "validation/data/meihua"
    target.mkdir(parents=True)
    (target / "weather-calendar-hko-v1.json").write_bytes(
        (FIXTURE / "calendar-profile.json").read_bytes() + b" "
    )
    monkeypatch.setattr(binding, "REPO_ROOT", tmp_path)
    binding._profile.cache_clear()
    try:
        with pytest.raises(ValueError, match="content changed"):
            binding.published_lunar_date_reference(date(2025, 12, 31))
    finally:
        binding._profile.cache_clear()


def test_new_reader_imports_no_production_calendar_engine_or_weather_outcome_reader() -> (
    None
):
    source = Path(binding.__file__).read_text()
    tree = ast.parse(source)
    imports = [
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    ]
    assert not any(
        any(
            key in name
            for key in [
                "almanac",
                "bazi_calendar",
                "lunardate",
                "services",
                "predictions",
            ]
        )
        for name in imports
    )
    assert "meihua_weather_trace_binding" in imports
