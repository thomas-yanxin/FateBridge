"""Source-year semantics, independent printed arithmetic, and CLI compatibility."""

import hashlib
import json
import runpy
import sys
from datetime import date
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core.guolao_year_labels import DATA, shoushi_year_context

ROOT = Path(__file__).parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "guolao-year-labels-v1"
REFERENCE = json.loads((FIXTURES / "reference.json").read_text())
BASELINE = json.loads((FIXTURES / "elapsed-cli-before.json").read_text())
SCRIPTS = ("audit_guolao_solar.py", "audit_guolao_purple.py")


@pytest.mark.parametrize("example", REFERENCE["worked_examples"])
def test_named_year_and_preceding_winter_reproduce_the_selected_source(example):
    book = shoushi_year_context(source_year=example["source_year"])
    winter = shoushi_year_context(winter_year=example["winter_year"])
    assert book["input_kind"] == "source_calendar_nominal_year_label"
    assert winter["input_kind"] == "preceding_winter_nominal_year_label"
    assert {k: v for k, v in book.items() if k != "input_kind"} == {
        k: v for k, v in winter.items() if k != "input_kind"
    }
    assert book["elapsed_years"] == example["elapsed_years"]
    assert book["inclusive_count_from_reference"] == example["inclusive_count"]
    assert F(book["effective_year_days_exact"]) == F(example["year_days"])
    assert F(book["zhongji_days_exact"]) == F(example["zhongji_days"])
    assert F(book["winter_cycle_days_exact"]) == F(example["winter_cycle_days"])
    assert book["winter_sexagenary_day"] == example["winter_sexagenary_day"]
    assert F(book["winter_fraction_of_day_exact"]) == F(
        example["winter_fraction_of_day"]
    )


def test_same_number_different_year_kind_cannot_silently_mean_the_same_winter():
    book = shoushi_year_context(source_year=1599)
    winter = shoushi_year_context(winter_year=1599)
    assert book["elapsed_years"] == 318
    assert winter["elapsed_years"] == 319
    assert winter["source_year_label_ce"] == 1600
    assert book["winter_cycle_days_exact"] != winter["winter_cycle_days_exact"]
    assert book["source_year_sexagenary_label"] == "己亥"
    assert book["preceding_winter_year_sexagenary_label"] == "戊戌"
    assert (
        shoushi_year_context(source_year=1281)["source_year_sexagenary_label"] == "辛巳"
    )
    assert (
        shoushi_year_context(winter_year=1280)["preceding_winter_year_sexagenary_label"]
        == "庚辰"
    )


def test_computed_source_winter_is_not_replaced_with_observed_value_to_fit():
    book = shoushi_year_context(source_year=1608)
    assert F(book["winter_cycle_days_exact"]) == F("29.2594")
    assert F(book["winter_cycle_days_exact"]) != F(
        REFERENCE["observed_winter_cycle_days"]
    )
    assert not REFERENCE["observed_value_used_to_fit_constants"]
    assert REFERENCE["computed_and_observed_not_merged"]


@pytest.mark.parametrize("kind", ["source_year", "winter_year"])
@pytest.mark.parametrize("bad", [True, 1608.0, F(1608), "1608", date(1608, 1, 1)])
def test_year_kind_requires_integer_labels_not_birth_dates_or_implicit_casts(kind, bad):
    with pytest.raises(TypeError, match="整数"):
        shoushi_year_context(**{kind: bad})


@pytest.mark.parametrize("kwargs", [{}, {"source_year": 1281, "winter_year": 1280}])
def test_exactly_one_explicit_year_kind_is_required(kwargs):
    with pytest.raises(ValueError, match="只能"):
        shoushi_year_context(**kwargs)


@pytest.mark.parametrize("kwargs", [{"source_year": 1280}, {"winter_year": 1279}])
def test_upward_reckoning_is_not_inferred_from_negative_elapsed_years(kwargs):
    with pytest.raises(ValueError, match="上考"):
        shoushi_year_context(**kwargs)


def test_year_labels_do_not_assign_modern_dates_or_resolve_other_header_variants():
    value = shoushi_year_context(source_year=1608)
    for flag in [
        "modern_calendar_date_assigned",
        "modern_epoch_calibrated",
        "gujin58_header_variants_resolved",
        "used_in_native_birth_chart",
    ]:
        assert value[flag] is False
    assert value["physical_julian_day"] is None
    assert value["timezone"] is None
    assert value["year_boundary_policy"] == (
        "named_book_year_label_only_no_modern_calendar_boundary"
    )


def _command(monkeypatch, capsys, script, args):
    path = ROOT / "scripts" / script
    monkeypatch.setattr(sys, "argv", [str(path), *args])
    assert runpy.run_path(str(path))["main"]() == 0
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("elapsed", [0, 99, 100, 199, 200, 318, 319, 327])
def test_existing_complete_cli_payloads_match_before_snapshot(
    monkeypatch, capsys, script, elapsed
):
    actual = _command(monkeypatch, capsys, script, ["--elapsed-years", str(elapsed)])
    assert actual == BASELINE[f"{script}:{elapsed}"]
    assert "source_year_context" not in actual


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize(
    "selector,year", [("--source-year", 1608), ("--winter-year", 1607)]
)
def test_actual_cli_new_selectors_use_same_calculation_as_declared_distance(
    monkeypatch, capsys, script, selector, year
):
    result = _command(monkeypatch, capsys, script, [selector, str(year)])
    context = result.pop("source_year_context")
    assert context["elapsed_years"] == 327
    assert context["inclusive_count_from_reference"] == 328
    assert context["source_year_sexagenary_label"] == "戊申"
    assert context["preceding_winter_year_sexagenary_label"] == "丁未"
    baseline = BASELINE[f"{script}:327"]
    if script == "audit_guolao_purple.py":
        assert result["input_kind"] == context["input_kind"]
        # Only the input declaration changes, not the numerical chain.
        result["input_kind"] = baseline["input_kind"]
    assert result == baseline


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--source-year", "1608", "--elapsed-years", "327"],
        ["--source-year", "1608", "--winter-year", "1607"],
        ["--winter-year", "1279"],
        ["--source-year", "1608.0"],
    ],
)
def test_cli_rejects_ambiguous_or_unimplemented_inputs(
    monkeypatch, capsys, script, args
):
    path = ROOT / "scripts" / script
    monkeypatch.setattr(sys, "argv", [str(path), *args])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(str(path))["main"]()
    assert error.value.code == 2
    assert not capsys.readouterr().out


def test_frozen_scans_and_metadata_support_runtime_provenance():
    source = json.loads(DATA.read_bytes())
    assert (
        hashlib.sha256(DATA.read_bytes()).hexdigest()
        == shoushi_year_context(source_year=1608)["source_data_sha256"]
    )
    for artifact in REFERENCE["artifacts"]:
        assert hashlib.sha256(
            (FIXTURES / artifact["path"]).read_bytes()
        ).hexdigest() == (artifact["sha256"])
    for runtime, evidence in zip(source["sources"], REFERENCE["sources"]):
        for key in ["source_id", "original_sha256", "artifact_sha256"]:
            assert runtime[key] == evidence[key]
    identity = REFERENCE["page_identity"]
    assert identity["wikisource_text_page"] == 81
    assert identity["matching_current_djvu_physical_page"] == 83
    assert not identity["universal_offset_rule_inferred"]
    assert not REFERENCE["independent_second_collator"]


@pytest.mark.parametrize(
    "key", ["reference_nominal_year_ce", "reference_winter_year_ce"]
)
def test_changed_epoch_metadata_fails_instead_of_fitting_an_example(
    tmp_path, monkeypatch, key
):
    from fatebridge.core import guolao_year_labels

    source = json.loads(DATA.read_bytes())
    source[key] += 1
    changed = tmp_path / "wrong-epoch.json"
    changed.write_text(json.dumps(source))
    monkeypatch.setattr(guolao_year_labels, "DATA", changed)
    with pytest.raises(ValueError, match="不能改元"):
        shoushi_year_context(source_year=1608)
