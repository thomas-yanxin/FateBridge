"""Keep fortnight numbering and source yuga arithmetic conditional."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core import sukuyo_fortnights as source
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_commentarial_clock import commentarial_boundary_reference
from fatebridge.core.sukuyo_sources import LoadedSource
from scripts.sukuyo.check_sukuyo_fortnights import verify_primary

FIXTURE = Path(__file__).parents[1] / "data/sukuyo-fortnight-before-production-v69.json"
BEFORE = json.loads(FIXTURE.read_bytes())


def reference():
    return commentarial_boundary_reference()["standalone_xuanying_reference"][
        "named_rizang_comparison"
    ]["fortnight_calendar_reference"]


@pytest.mark.parametrize("row", BEFORE["all68_declared_ordinal_cases"])
def test_every_before_production_ordinal_case_including_invalid_days(row):
    args = {k: row[k] for k in ("half", "day", "black_length", "white_length")}
    if row["valid"]:
        assert source.declared_fortnight_ordinal(**args) == row["ordinal"]
    else:
        with pytest.raises(ValueError):
            source.declared_fortnight_ordinal(**args)


@pytest.mark.parametrize(
    "changed",
    [
        {"day": True},
        {"day": 9.0},
        {"black_length": True},
        {"black_length": 13},
        {"black_length": 16},
        {"white_length": 14},
        {"white_length": 15.0},
        {"half": "first_half"},
    ],
)
def test_unsupported_numbering_or_halfday_is_not_silently_accepted(changed):
    args = {
        "half": "white",
        "day": 9,
        "black_length": 14,
        "white_length": 15,
        **changed,
    }
    with pytest.raises(ValueError):
        source.declared_fortnight_ordinal(**args)


def test_black_length_and_white_length_have_no_implicit_defaults():
    with pytest.raises(TypeError):
        source.declared_fortnight_ordinal("white", 9)


def test_yuga_derived_ledger_is_exact_but_has_no_month_placement_or_epoch():
    value = reference()
    ledger = value["derived_five_year_ledger"]
    assert ledger == BEFORE["before_production_five_year_ledger"]
    assert (
        ledger["all_months"],
        ledger["short_months"],
        ledger["full_months_derived"],
        ledger["derived_days"],
    ) == (62, 30, 32, 1830)
    assert ledger["derived_mean_month"] == {"numerator": 915, "denominator": 31}
    assert ledger["explicit_leap_year_positions"] == [3, 5]
    assert ledger["explicit_leap_month_positions"] is None
    assert ledger["actual_leap_month_lengths"] is None
    assert not value["interpretation_scope"][
        "five_year_cycle_adopted_as_current_calendar"
    ]


def test_all_quoted_season_schemes_keep_own_author_stance_and_mapping():
    rows = reference()["T1821_all_four_attributed_three_season_schemes"]
    assert [r["rain_second_white9_chinese_label"] for r in rows] == [
        [8, 9],
        [7, 9],
        [6, 9],
        [5, 9],
    ]
    assert [r["cold_fourth_white9_chinese_label"] for r in rows] == [
        [2, 9],
        [1, 9],
        [12, 9],
        [11, 9],
    ]
    assert [r["stance_in_selected_paragraph"] for r in rows] == ["criticized"] * 3 + [
        "author_own_explanation"
    ]


def test_four_quarter_groups_do_not_masquerade_as_twelve_daily_conversion_tables():
    value = reference()
    rows = value["T2087_four_quarters_original_groups_not12_literal_daily_intervals"]
    assert len(rows) == 4 and sum(len(r["names"]) for r in rows) == 12
    assert rows[-1]["start"] == [10, 16] and rows[-1]["end"] == [1, 15]
    assert not value["interpretation_scope"][
        "absolute_year_or_uniform_date_conversion_established"
    ]


def test_eleven_and_explicit_twelve_correction_remain_different_layers():
    value = reference()["T1644_T2251_explicit_correction_context"]["source_conflict"]
    assert value["T1644_selected_main_literal"] == "十一月九日"
    assert value["T2251_selected_quotation_literal"] == "十二月九日"
    assert value["T2251_small_type_note"] == "傍本作一誤也"
    assert not value["source_priority_or_emendation_accepted"]


def test_tampered_source_bundle_cannot_reuse_the_canonical_reference(
    tmp_path, monkeypatch
):
    path = tmp_path / "changed.json"
    path.write_text("{}")
    monkeypatch.setattr(source, "SOURCE", path)
    with pytest.raises(ValueError, match="来源包已改变"):
        source.fortnight_calendar_reference({"source_sha256": "anything"})


@pytest.mark.parametrize(
    "file,expected",
    [
        ("sukuyo_t1299_days.json", "T1299"),
        ("sukuyo_comparative_time_units.json", "西域记"),
    ],
)
def test_changed_bound_parent_edition_is_rejected(monkeypatch, file, expected):
    load = source.load_source

    def changed(path):
        value = load(path)
        if path.name != file:
            return value
        payload = value.data
        if file == "sukuyo_t1299_days.json":
            payload["source_sha256"] = "changed"
        else:
            for r in payload["witnesses"]:
                if r["id"] == "T51n2087":
                    r["source_sha256"] = "changed"
        return LoadedSource(payload, "changed")

    monkeypatch.setattr(source, "load_source", changed)
    with pytest.raises(ValueError, match=expected + "具名版本不一致"):
        source.fortnight_calendar_reference(
            {"source_sha256": BEFORE["actual_sources"]["T13n0397.xml"]["sha256"]}
        )


def test_wrong_rizang_edition_is_not_bound():
    with pytest.raises(ValueError, match="日藏具名版本不一致"):
        source.fortnight_calendar_reference({"source_sha256": "changed"})


def test_source_reference_copy_cannot_emend_later_runs():
    first = reference()
    first["T1644_T2251_explicit_correction_context"]["source_conflict"][
        "T1644_selected_main_literal"
    ] = "十二月九日"
    assert (
        reference()["T1644_T2251_explicit_correction_context"]["source_conflict"][
            "T1644_selected_main_literal"
        ]
        == "十一月九日"
    )


def test_declared_arithmetic_does_not_reassign_current_historical_date_or_half():
    calendar = calendar_mansion(
        "0806-07-23",
        "23:59:00",
        "+09:00",
        calendar_profile="hinoo_t1299_host27",
        calendar_basis="japanese_naoj_historical_utc09",
        calendar_day_part="first_half",
    )
    before = deepcopy(calendar)
    day = day_evidence(calendar)
    assert calendar == before and day["calendar"]["calendar_day_part"] == "first_half"
    assert not reference()["interpretation_scope"]["applied_to_current_calendar"]
    assert not reference()["interpretation_scope"][
        "hinoo_half_or_leap_precedence_established"
    ]


@pytest.mark.parametrize("name", list(BEFORE["actual_sources"]))
def test_actual_source_capture_substitution_rejected(tmp_path, name):
    path = tmp_path / "wrong"
    path.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="实际源文件字节指纹不一致"):
        verify_primary({name: path})


def test_offline_checker_does_not_claim_actual_source_reading():
    result = verify_primary()
    assert result["declared_ordinal_cases"] == 68
    assert result["actual_source_files_rechecked"] == []
    assert not result["actual_date_or_leap_precedence_admitted"]


def test_complete_runtime_numbering_summary_retains_denominator_and_rejection_meaning():
    value = reference()
    assert (
        value["all68_declared_ordinal_cases"] == BEFORE["all68_declared_ordinal_cases"]
    )
    summary = value["numbering_validation_scope"]
    assert (summary["declared_cases"], summary["valid"], summary["rejected"]) == (
        68,
        59,
        9,
    )
    assert summary["historical_observations"] == summary["real_samples"] == 0
    assert not summary["rejections_are_source_disagreements_or_prediction_failures"]
    assert not summary["valid_fraction_is_calendar_accuracy_or_prediction_probability"]
