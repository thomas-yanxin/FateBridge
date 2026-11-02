"""Printed-source sunrise arithmetic, units, differences and remaining gaps."""

import copy
import csv
import hashlib
import json
from fractions import Fraction as F
from pathlib import Path

import pytest

from fatebridge.core import guolao_sunrise as subject
from fatebridge.core.guolao_lunar_phases import assign_source_phase_day
from fatebridge.validation.guolao_sunrise import (
    audit_sunrise_tables,
    chinese_integer,
    parse_cell,
    parse_digital_table,
)

FIXTURE = Path(__file__).parent / "fixtures/guolao-sunrise-v1"


def test_raw_facsimiles_table_glyphs_and_prearithmetic_transcription_are_pinned():
    ref = json.loads((FIXTURE / "reference.json").read_text())
    for r in ref["artifacts"]:
        raw = (FIXTURE / r["path"]).read_bytes()
        assert len(raw) == r["bytes"]
        assert hashlib.sha256(raw).hexdigest() == r["sha256"]
    assert hashlib.sha256(subject.DATA.read_bytes()).hexdigest() == ref["data_sha256"]
    assert ref["single_unblinded_collator"]
    assert ref["digital_readings_known_during_Siku_collation"]


def test_all_required_siku_cells_equal_the_original_unrescaled_transcription():
    rows = list(csv.DictReader((FIXTURE / "siku-five-fields-transcription.csv").open()))
    data = json.loads(subject.DATA.read_bytes())["profiles"]["gujin37_siku"]["rows"]
    assert len(rows) == len(data) == 93
    assert sum(r[k] is not None for r in data for k in subject.FIELDS) == 555
    for expected, actual in zip(rows, data, strict=True):
        for k in subject.FIELDS:
            assert (expected[k] or None) == actual[k]
    assert data[-1]["declination_du"] is None
    assert data[-1]["argument_du"] == "91.3125"


def test_complete_digital_edition_parse_keeps_critical_marks_and_separate_profile():
    parsed = parse_digital_table(
        (FIXTURE / "yuanshi055-table-with-critical-marks.html").read_text()
    )
    data = json.loads(subject.DATA.read_bytes())["profiles"]["yuanshi55_digital"][
        "rows"
    ]
    assert parsed["rows"] == data
    assert parsed["polar_distance_columns_not_semantically_parsed"]
    assert not parsed["source_raw_glyphs_overwritten"]
    assert F(data[9]["declination_du"]) == F("23.6342")
    assert F(data[10]["summer_half_night_fen"]) == F("1917.40")


@pytest.mark.parametrize(
    "value,kind",
    [
        ("<p></p>", "angle"),
        ("<p>一百一十五一三{{*|四五}}</p>", "angle"),
        ("<p>三千{{*|九二}}</p>", "night"),
        ("<p>{{*|三}}</p>", "rate"),
    ],
)
def test_blank_unmarked_or_truncated_precision_is_not_guessed(value, kind):
    with pytest.raises(ValueError):
        parse_cell(value, kind)


def test_missing_source_row_or_cell_not_filled_by_adjacent_values():
    raw = (FIXTURE / "yuanshi055-table-with-critical-marks.html").read_text()
    with pytest.raises(ValueError):
        parse_digital_table(raw.replace("<p>初</p>", "<p>空</p>", 1))
    with pytest.raises(ValueError):
        parse_digital_table(
            raw.replace("<p>二十三{{*|九０}}<br /> 　　　{{*|三０}}</p>", "<p></p>", 1)
        )


@pytest.mark.parametrize("profile", ["gujin37_siku", "yuanshi55_digital"])
def test_origin_clock_matches_independently_printed_complete_day_night_constants(
    profile,
):
    t = subject.load_table(profile)
    outside = t.sunrise(F(), solar_side="outside", basis="dadu_source_table")
    inside = t.sunrise(F(), solar_side="inside", basis="dadu_source_table")
    assert F(outside["source_clock"]["source_night_ke_exact"]) == F("61.8408")
    assert F(outside["source_clock"]["source_day_ke_exact"]) == F("38.1592")
    assert F(outside["source_clock"]["usable_source_sunrise_fraction_exact"]) == F(
        ".309204"
    )
    assert F(inside["source_clock"]["usable_source_sunrise_fraction_exact"]) == F(
        ".190796"
    )
    assert F(outside["declination_ancient_du_exact"]) == F("23.9030")
    assert F(outside["source_clock"]["source_dawn_fraction_exact"]) == F(".284204")
    assert not outside["source_clock"]["physical_sunrise_validated"]
    assert not outside["midnight_solar_argument_or_fold_derived"]


def test_literal_five_witness_differences_are_not_replaced_by_neighbor_differences():
    result = audit_sunrise_tables()
    assert [(r["index"], r["field"]) for r in result["witness_differences"]] == [
        (7, "day_night_difference_fen"),
        (39, "day_night_difference_fen"),
        (91, "declination_drop_fen"),
        (91, "day_night_difference_fen"),
        (92, "argument_du"),
    ]
    for p in result["profiles"].values():
        assert p["rows"] == 93 and p["required_numeric_cells"] == 555
        assert p["printed_empty_cells"] == 3
        assert not p["rates_replaced_by_anchor_differences"]
        assert not p["terminal_segment_rescaled_to_force_closure"]
    assert not result["source_row_count_is_accuracy_score"]
    assert result["modern_astronomical_truth_comparison"] is None


def test_exact_source_rate_is_used_even_when_adjacent_anchor_closure_is_imperfect():
    t = subject.load_table("gujin37_siku")
    q = t.sunrise(F("7.5"), solar_side="inside", basis="dadu_source_table")
    # The printed1.41 differs from the1.42 adjacent-anchor difference.
    assert F(q["source_clock"]["source_half_night_fen_exact"]) == F("1913.285")
    assert F(
        t.segment_residual(7)["summer_half_night_anchor_residual_fen_exact"]
    ) == -F(".01")
    assert F(t.segment_residual(39)["summer_half_night_anchor_residual_fen_exact"]) == 0


def test_short_terminal_segment_is_not_stretched_and_empty_declination_is_not_zero():
    t = subject.load_table("gujin37_siku")
    assert F(t.segment_residual(91)["width_du_exact"]) == F(".3125")
    assert F(
        t.segment_residual(91)["winter_half_night_anchor_residual_fen_exact"]
    ) == -F(".006875")
    mid = t.sunrise(F("91.15625"), solar_side="outside", basis="dadu_source_table")
    assert F(mid["source_clock"]["source_half_night_fen_exact"]) == F("2501.3915625")
    end = t.sunrise(F("91.3125"), solar_side="outside", basis="dadu_source_table")
    assert end["declination_ancient_du_exact"] is None
    assert not end["declination_usable_for_local_formula"]
    assert F(end["source_clock"]["usable_source_sunrise_fraction_exact"]) == F(1, 4)
    with pytest.raises(ValueError):
        t.sunrise(F("91.314375"), solar_side="outside", basis="dadu_source_table")


def test_digital_terminal_rate_discontinuity_is_kept_and_not_a_fitted_pass():
    t = subject.load_table("yuanshi55_digital")
    r = t.segment_residual(91)
    assert F(r["winter_half_night_anchor_residual_fen_exact"]) == F("1.9251")
    assert F(t.audit()["uncovered_tail_to_theoretical_quadrant_du_exact"]) == F(
        ".004375"
    )
    assert r["declination_anchor_residual_du_exact"] is None


def test_slight_negative_printed_declination_near_last_anchor_is_not_clamped():
    q = subject.load_table("gujin37_siku").sunrise(
        F("91.31249"), solar_side="inside", basis="dadu_source_table"
    )
    assert F(q["declination_ancient_du_exact"]) == -F(".000014855")
    assert not q["declination_usable_for_local_formula"]
    assert q["source_clock"]["source_clock_within_day_range"]


@pytest.mark.parametrize("value", [0, 0.5, False, "0"])
def test_source_angles_need_fraction_and_explicit_dadu_basis(value):
    t = subject.load_table("gujin37_siku")
    with pytest.raises(TypeError):
        t.sunrise(value, solar_side="inside", basis="dadu_source_table")


def test_unknown_profile_wrong_city_or_out_of_table_angle_not_defaulted():
    with pytest.raises(ValueError):
        subject.load_table("best_fit")
    t = subject.load_table("gujin37_siku")
    for degree, side, basis in [
        (F(), "inside", "birthplace"),
        (F(-1), "inside", "dadu_source_table"),
        (F(), "winter", "dadu_source_table"),
    ]:
        with pytest.raises(ValueError):
            t.sunrise(degree, solar_side=side, basis=basis)


@pytest.mark.parametrize("solstice,night", [("winter", F(62)), ("summer", F(38))])
def test_nine_regions_requires_explicit_observation_and_uses_239_normalizer(
    solstice, night
):
    kwargs = dict(
        solar_side="outside",
        measured_solstice=solstice,
        measured_night_ke=night,
        observation_reference="synthetic arithmetic scenario; no actual observation",
    )
    q = subject.local_solstice_sunrise(F("23.9"), **kwargs)
    assert F(q["night_ke_exact"]) == 62
    assert F(q["source_clock"]["usable_source_sunrise_fraction_exact"]) == F(".31")
    assert not q["observation_independently_authenticated"]
    assert not q["modern_latitude_or_birthplace_inferred"]
    with pytest.raises(ValueError):
        subject.local_solstice_sunrise(
            F("23.9"), **{**kwargs, "observation_reference": ""}
        )


@pytest.mark.parametrize("solstice,night", [("winter", F(49)), ("summer", F(51))])
def test_local_observation_direction_does_not_silently_apply_northern_rule_to_south(
    solstice, night
):
    with pytest.raises(ValueError):
        subject.local_solstice_sunrise(
            F(10),
            solar_side="outside",
            measured_solstice=solstice,
            measured_night_ke=night,
            observation_reference="synthetic",
        )


def test_source_local_formula_outside_physical_range_is_not_clamped_into_a_sunrise():
    q = subject.local_solstice_sunrise(
        F("23.9030"),
        solar_side="outside",
        measured_solstice="winter",
        measured_night_ke=F(100),
        observation_reference="synthetic boundary test",
    )
    assert F(q["night_ke_exact"]) > 100
    assert q["source_clock"]["usable_source_sunrise_fraction_exact"] is None
    assert not q["source_clock"]["source_clock_within_day_range"]


def test_original_phase_day_boundary_receives_exact_table_fraction_not_rounded_clock():
    q = subject.load_table("gujin37_siku").sunrise(
        F(), solar_side="outside", basis="dadu_source_table"
    )
    sunrise = F(q["source_clock"]["usable_source_sunrise_fraction_exact"])
    # Arithmetic boundary fixture, not a claimed date or verified solar argument.
    for d, expected in [(-F(1, 10**9), 59), (F(), 59), (F(1, 10**9), 60)]:
        result = assign_source_phase_day(
            F(60) + sunrise + d, "full_moon", source_sunrise_fraction=sunrise
        )
        assert result["assigned_source_phase_day_integer"] == expected
        new = assign_source_phase_day(
            F(60) + sunrise + d, "new_moon", source_sunrise_fraction=sunrise
        )
        assert new["assigned_source_phase_day_integer"] == 60


def test_loader_rejects_unit_metadata_or_boolean_literal_instead_of_reinterpreting(
    monkeypatch, tmp_path
):
    data = json.loads(subject.DATA.read_bytes())
    path = tmp_path / "data.json"
    monkeypatch.setattr(subject, "DATA", path)
    bad = copy.deepcopy(data)
    bad["day_cycle_fen"] = "100"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        subject.load_table("gujin37_siku")
    bad = copy.deepcopy(data)
    bad["profiles"]["gujin37_siku"]["rows"][0]["argument_du"] = False
    path.write_text(json.dumps(bad))
    with pytest.raises(TypeError):
        subject.load_table("gujin37_siku")


def test_cli_requires_explicit_table_basis_and_does_not_wrap_uncovered_angles(
    monkeypatch,
):
    import importlib.util
    import sys

    path = Path(__file__).parents[1] / "scripts/audit_guolao_sunrise.py"
    spec = importlib.util.spec_from_file_location("sunrise_cli_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for degree, extra in [
        ("91.314375", []),
        ("91.314375", ["--basis", "dadu_source_table"]),
        ("1/0", ["--basis", "dadu_source_table"]),
    ]:
        monkeypatch.setattr(
            sys,
            "argv",
            [
                str(path),
                "table",
                "--profile",
                "gujin37_siku",
                "--local-degree",
                degree,
                "--solar-side",
                "outside",
                *extra,
            ],
        )
        with pytest.raises(SystemExit) as error:
            module.main()
        assert error.value.code == 2
