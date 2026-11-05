"""Independent printed clauses/cell labels, with no claim of civil date accuracy."""

import hashlib
import json
from datetime import date
from fractions import Fraction
from pathlib import Path

import pytest

from fatebridge.core.guolao_grid import load_grid
from fatebridge.core.guolao_limits import limit_scale
from fatebridge.core.guolao_ruler_calendar import (
    DATA,
    METHOD_ID,
    NominalSourceDate,
    load_ruler_calendar,
    ruler_calendar_audit,
    ruler_calendar_scale,
)

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests/fixtures/guolao-ruler-calendar-v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_text())


@pytest.mark.parametrize("asset", REFERENCE["assets"])
def test_original_and_read_views_preserve_source_bytes_and_credits(asset):
    raw = (FIXTURE / asset["path"]).read_bytes()
    assert len(raw) == asset["bytes"]
    assert hashlib.sha256(raw).hexdigest() == asset["sha256"]
    assert "中國國家圖書館" in REFERENCE["source"]["credit"]
    assert "保留可見水印" in REFERENCE["source"]["credit"]


@pytest.mark.parametrize(
    "palace,days,annual",
    [
        ("相貌", 120, "3"),
        ("官禄", 180, "2"),
        ("福德", 132, "27207/10000"),
        ("迁移", 96, "15/4"),
        ("疾厄", 84, "857/200"),
        ("奴仆", 54, "33003/5000"),
        ("兄弟", 60, "6"),
    ],
)
def test_page35_printed_month_day_clauses_and_base100_annual_units(
    palace, days, annual
):
    scale = ruler_calendar_scale(palace)
    assert scale.nominal_days_per_degree == days
    assert scale.printed_annual_rate == Fraction(annual)
    reading = next(x for x in REFERENCE["page35"]["clauses"] if palace in x["palaces"])
    assert reading["annual_text"] == scale.printed_annual_rate_text
    assert reading["month_day_text"] == scale.printed_month_day_text


@pytest.mark.parametrize("reading", REFERENCE["page36"]["selected_first_cell_readings"])
def test_six_independently_read_printed_first_cells_match_inclusive_labels(reading):
    interval = ruler_calendar_scale(reading["palace"]).cell_interval(reading["cell"])
    for key, field in [
        ("start_nominal_source_date", "start"),
        ("last_included_nominal_day", "last_included_day"),
    ]:
        result = interval[key]
        assert [result["ordinal_year"], result["month"], result["day"]] == reading[
            field
        ]
    assert not REFERENCE["page36"]["disease_first_cell_numeric_reading_accepted"]


def test_unreconciled_annual_rates_have_exact_visible_residuals():
    audit = ruler_calendar_audit()
    assert audit["contradictory_rate_groups"] == 3
    scales = {row["palaces"][0]: row for row in audit["scales"]}
    assert scales["福德"]["printed_annual_full_limit_minus_30_exact"] == "-723/10000"
    assert scales["疾厄"]["printed_annual_full_limit_minus_30_exact"] == "-1/200"
    assert scales["奴仆"]["printed_annual_full_limit_minus_30_exact"] == "-2973/10000"
    assert all(
        s["month_day_full_limit_minus_source_duration_days_exact"] == "0"
        for s in scales.values()
    )
    # This NLC witness says 秒. It cannot silently repair the old Lu Wei 分 reading.
    assert limit_scale("疾厄").printed_rate is None
    assert limit_scale("疾厄").printed_rate_text.endswith("五十分")
    assert "秒" in scales["疾厄"]["printed_annual_rate_text"]


def test_one_based_source_origin_and_inclusive_end_do_not_add_a_year_or_day():
    scale = ruler_calendar_scale("福德")
    assert (
        scale.position(NominalSourceDate(1, 1, 1))["limit_scale_degrees_exact"] == "0"
    )
    assert scale.position(NominalSourceDate(1, 5, 12))["cell"] == 1
    last_instant = NominalSourceDate(1, 5, 12, 1 - Fraction(1, 10**80))
    assert scale.position(last_instant)["cell"] == 1
    assert scale.position(NominalSourceDate(1, 5, 13))["cell"] == 2
    assert (
        scale.position(NominalSourceDate(1, 5, 13))["limit_scale_degrees_exact"] == "1"
    )
    result = scale.at_degrees(Fraction(1, 2))
    assert result["nominal_source_date"]["month"] == 3
    assert result["nominal_source_date"]["day"] == 7
    assert result["elapsed_nominal_days_exact"] == "66"
    for key in ("calendar_date", "birth_age", "mansion", "next_palace"):
        assert result[key] is None


@pytest.mark.parametrize("scale", load_ruler_calendar(), ids=lambda s: s.palaces[0])
def test_exact_subday_inverse_local_completion_and_no_wrap(scale):
    epsilon = Fraction(1, 10**80)
    for degree in (Fraction(0), epsilon, Fraction(1), Fraction(7, 3), Fraction(30)):
        days = scale.days_from_degrees(degree)
        assert scale.degrees_from_days(days) == degree
        assert NominalSourceDate.from_elapsed_days(days).elapsed_days == days
    end = scale.at_degrees(Fraction(30))
    assert end["status"] == "local_limit_complete"
    assert end["cell"] is None
    assert end["next_palace"] is None
    assert scale.at_degrees(30 - epsilon)["cell"] == 30
    with pytest.raises(ValueError):
        scale.at_degrees(30 + epsilon)
    with pytest.raises(ValueError):
        scale.position(NominalSourceDate(2027, 1, 1))


@pytest.mark.parametrize(
    "parts",
    [
        (0, 1, 1),
        (1, 0, 1),
        (1, 13, 1),
        (1, 1, 0),
        (1, 1, 31),
        (True, 1, 1),
        (1.0, 1, 1),
        (1, "1", 1),
        (1, 1, None),
        (1, 1, 1, Fraction(1)),
        (1, 1, 1, Fraction(-1)),
        (1, 1, 1, 0.5),
    ],
)
def test_nominal_date_rejects_wrong_types_and_invalid_labels(parts):
    with pytest.raises((ValueError, TypeError)):
        NominalSourceDate(*parts)


@pytest.mark.parametrize("value", [1, 1.0, True, "1", None])
def test_fraction_units_cannot_be_implicit(value):
    scale = ruler_calendar_scale("官禄")
    with pytest.raises(TypeError):
        scale.at_degrees(value)
    with pytest.raises(TypeError):
        scale.degrees_from_days(value)
    with pytest.raises(TypeError):
        NominalSourceDate.from_elapsed_days(value)


@pytest.mark.parametrize("cell", [0, 31, -1, True, "1", 1.0])
def test_invalid_cell_is_never_clamped(cell):
    with pytest.raises((ValueError, TypeError)):
        ruler_calendar_scale("官禄").cell_interval(cell)


def test_other_palaces_and_civil_dates_are_not_guessed():
    for name in ("命", "", "ASC", "官祿"):
        with pytest.raises(ValueError):
            ruler_calendar_scale(name)
    with pytest.raises(TypeError):
        ruler_calendar_scale("官禄").position(date(2027, 1, 1))
    assert not ruler_calendar_audit()["modern_calendar_mapping_accepted"]
    assert not ruler_calendar_audit()["full_210_printed_cells_collated"]
    assert not ruler_calendar_audit()["full_birth_limit_schedule_accepted"]
    assert not ruler_calendar_audit()["real_world_efficacy_tested"]
    assert (
        json.loads(DATA.read_bytes())["source"]["pdf_sha256"]
        == REFERENCE["download"]["sha256"]
    )


def test_footer_palace_limit_labels_do_not_become_celestial_fraction_tails():
    audit = load_grid().audit()
    assert (
        audit["lower_section_role"]
        == "separate_palace_limit_rows_numeric_semantics_unadjudicated"
    )
    assert not audit["fractional_tail_label_is_established_interpretation"]
    assert not audit["lower_section_numeric_cells_collated"]
    assert not audit["life_degree_accepted"]
    assert REFERENCE["page37"]["lower_section_visible_labels"][:3] == [
        "相貌限",
        "福德限",
        "官祿限",
    ]
