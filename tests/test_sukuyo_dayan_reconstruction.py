"""Exact conformance to all 1212 reference months fixed before production."""

import gzip
import json
from datetime import date
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_dayan_reconstruction as model
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_historical_calendar import date_reference

FIXTURE = Path(__file__).parent / "data/sukuyo-dayan-model-all-months-v1.json.gz"


def project(value):
    return {
        "jdn_at_civil_midnight_coordinate": value["nominal_midnight_JDN_coordinate"],
        "cycle_index": value["cycle_index"],
        "remainder": value["remainder_units"],
    }


def test_complete1212_months_both_models_equal_before_code_reference_exactly():
    reference = json.loads(gzip.decompress(FIXTURE.read_bytes()))
    assert reference["reference_commit"] == "26751a8cce76b989680586e4b8ab15abb0ef3ad8"
    rows = reference["all_month_rows"]
    assert len(rows) == 1212
    for expected in rows:
        result = model.reconstruct_new_moon(
            expected["host_ordinal"], expected["host_month_key"][0]
        )
        assert result["mean_nominal_julian_day"] == expected["mean_jd"]
        assert (
            result["solar_step"]["correction_units"]
            == expected["solar_correction_units"]
        )
        for name in ["A", "D"]:
            actual = result["models"][name]
            assert (
                actual["lunar_correction_units"]
                == expected[f"lunar_correction_{name}_units"]
            )
            assert project(actual["pre_advance_cycle"]) == expected[name]
        assert (
            project(
                result["models"][result["source_policy_selected_model"]][
                    "pre_advance_cycle"
                ]
            )
            == expected["selected"]
        )
        assert not result["advance_direction_determined"]
        assert not result["host_calendar_or_month_labels_independently_verified"]


def test_all327_printed_rows_recomputed_without_replacing_decision_or_conflicts():
    source = json.loads(
        (model.SOURCE.parent / "sukuyo_dayan_advance_2022.json").read_bytes()
    )
    reference = json.loads(gzip.decompress(FIXTURE.read_bytes()))
    keys = {tuple(row["host_month_key"]): row for row in reference["all_month_rows"]}
    for printed in source["rows"]:
        key = (
            printed["lunar_year"],
            printed["lunar_month"],
            printed["is_leap_month"],
        )
        selected = keys[key]
        result = date_reference(date.fromordinal(selected["host_ordinal"]))
        calculation = result["dayan_nominal_new_moon_model"]
        actual = calculation["models"][calculation["source_policy_selected_model"]][
            "pre_advance_cycle"
        ]
        assert actual["cycle_index"] == printed["computed_new_moon_day_cycle_index"]
        assert actual["remainder_units"] == {
            "numerator": printed["computed_new_moon_remainder"],
            "denominator": 1,
        }
        previous = result["dayan_advance_research_comparison"]
        assert previous["selected_row"] == printed
        assert not previous["physical_new_moon_recomputed"]
        if printed["row_number"] == 263:
            assert previous["author_proposed_day_shift_from_literal"] is None
            assert actual["remainder_units"]["numerator"] == 23


def test_all1212_months_are_exposed_even_when_not_in_the327_row_table():
    reference = json.loads(gzip.decompress(FIXTURE.read_bytes()))
    for row in reference["all_month_rows"]:
        reference_date = date.fromordinal(row["host_ordinal"])
        actual = date_reference(reference_date)["dayan_nominal_new_moon_model"]
        assert (
            actual["host_month_start_ordinal_used_as_selector"] == row["host_ordinal"]
        )
        assert (
            actual["declared_lunar_year_used_for_source_policy"]
            == row["host_month_key"][0]
        )
    assert date_reference(date(763, 6, 1))["dayan_nominal_new_moon_model"] is None
    assert date_reference(date(863, 6, 1))["dayan_nominal_new_moon_model"] is None


@pytest.mark.parametrize("change", ["drop_solar", "drop_lunar", "epoch", "rounding"])
def test_source_coefficients_and_policy_changes_require_revalidation(
    monkeypatch, tmp_path, change
):
    data = json.loads(model.SOURCE.read_bytes())
    if change == "drop_solar":
        data["solar_rows"].pop()
    elif change == "drop_lunar":
        data["lunar_rows"].pop()
    elif change == "epoch":
        data["constants"]["epoch_julian_day"]["numerator"] += 1
    else:
        data["policy"]["rounding"] = "round to improve printed agreement"
    path = tmp_path / "modified.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    monkeypatch.setattr(model, "SOURCE", path)
    with pytest.raises(ValueError, match="重新核验"):
        model.reconstruct_new_moon(date(768, 7, 23).toordinal(), 768)


@pytest.mark.parametrize("ordinal,year", [(True, 768), (280000, False), (1.5, 768)])
def test_selector_requires_explicit_integer_inputs(ordinal, year):
    with pytest.raises(ValueError, match="整数"):
        model.reconstruct_new_moon(ordinal, year)


def test_midmonth_is_not_silently_reinterpreted_as_a_different_month_start():
    with pytest.raises(ValueError, match="三日"):
        model.reconstruct_new_moon(date(768, 8, 5).toordinal(), 768)


def test_source_policy_values_are_not_a_physical_clock_or_a_calendar_override():
    calendar = calendar_mansion(
        "0806-07-23",
        "05:45:00",
        "+09:00",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
    )
    assert calendar["candidate_su27s"] == ["星", "鬼"]
    result = calendar["calendar_reference"]["dayan_nominal_new_moon_model"]
    assert result["source_policy_selected_model"] == "D"
    assert not result["current_calendar_or_mansion_changed"]
    assert not result["physical_new_moon_or_UTC_TT_recomputed"]
    text = day_evidence(calendar)["reading_text"]
    for required in [
        "A模型",
        "D模型",
        "793—819",
        "本月取D",
        "三日界",
        "月份",
        "置闰",
        "UTC／TT",
        "52项分歧",
        "1项未知",
        "Takashi SUGA",
    ]:
        assert required in text
    result["solar_step"]["coefficient_row"]["solar_term"] = "changed"
    fresh = date_reference(date(806, 7, 23))["dayan_nominal_new_moon_model"]
    assert fresh["solar_step"]["coefficient_row"]["solar_term"] != "changed"


@pytest.mark.parametrize(
    "civil,basis,applied",
    [
        ("0793-01-21", "japanese_naoj_historical_utc09", True),
        ("2026-02-17", "chinese_hko_utc08", False),
        ("0763-01-23", "japanese_naoj_historical_utc09", False),
        ("1050-11-01", "japanese_naoj_historical_utc09", False),
    ],
)
def test_scope_and_current_input_applicability_are_both_explained(
    civil, basis, applied
):
    calendar = calendar_mansion(civil, "00:15:00", calendar_basis=basis)
    day = day_evidence(calendar)
    reference = day["calendar_day"]["clock_doctrine"][
        "dayan_reconstruction_scope_reference"
    ]
    scope = reference["reference_scope"]
    assert scope["reference_corpus_months"] == 1212
    assert scope["printed_2022_selected_rows"] == 327
    author = reference["computational_reference"]
    assert author["author_literal"] == "Takashi SUGA"
    assert "s.authors" in author["author_attribution_gemspec_literal"]
    assert author["author_attribution_git_blob_sha1"] == (
        "6872a172d911e75fb1c96a4b9c5540431464a177"
    )
    text = day["reading_text"]
    assert "1212是数值实现对照的月份数，327是具名研究表行数" in text
    if applied:
        assert "本次按声明的农历792年另列大衍A／D模型" in text
    else:
        assert "本次输入没有应用该大衍名义模型" in text
        assert "该模型的1212月实现对照不能移作本次所选历日或现实效力的验收" in text
