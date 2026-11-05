"""The immutable all-host audit retains convergent, divergent and missing cases."""

import copy
import json

import pytest

from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from scripts.sukuyo import check_sukuyo_month_transitions as audit


@pytest.fixture(scope="module")
def oracle():
    return audit.source_expectations()


def row_for(oracle, civil):
    return next(
        row
        for row in oracle[0]
        if row["date"] == civil and row["basis"] == "japanese_naoj_historical_utc09"
    )


def calculate(row, half="None"):
    return calendar_mansion(
        row["date"],
        zone="+09:00",
        calendar_basis=row["basis"],
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part=None if half == "None" else half,
    )


def test_source_only_oracle_keeps_all_hosts_and_declared_conditions(oracle):
    rows, protocol = oracle
    assert len(rows) == 27581
    assert {key: value["conditions"] for key, value in protocol["counts"].items()} == {
        "chinese_hko_utc08": 7383,
        "japanese_hutime_1002_1_utc09": 5898,
        "japanese_naoj_historical_utc09": 69462,
    }
    assert all(
        set(row["expectations"]) == {"None", "first_half", "second_half"}
        for row in rows
    )
    # Missing previous context is retained, rather than dropped from acceptance.
    first = next(row for row in rows if row["basis"] == "japanese_hutime_1002_1_utc09")
    assert first["date"] == "1872-02-09"
    assert first["expectations"]["None"]["status"] == "partial"
    assert not first["expectations"]["first_half"][
        "candidate_set_complete_under_declared_reconstructions"
    ]
    assert first["expectations"]["second_half"]["status"] == "computed"


@pytest.mark.parametrize(
    "civil",
    [
        "0801-02-21",
        "0806-07-23",
        "0814-08-23",
        "0817-05-24",
        "0801-03-22",
        "0803-12-22",
        "0814-09-21",
    ],
)
@pytest.mark.parametrize("half", ["None", "first_half", "second_half"])
def test_all_four_length_patterns_and_following_months_match(oracle, civil, half):
    row = row_for(oracle, civil)
    assert not audit.compare_calendar(row, half, calculate(row, half))["differences"]


def test_equal_mansion_cannot_hide_a_wrong_lunar_year(oracle):
    row = row_for(oracle, "0801-02-21")
    result = calculate(row)
    assert result["natal_su27"] == "室"
    changed = copy.deepcopy(result)
    changed["profile_calculation"]["short_month_assignment"]["previous_lunar"][
        "before_regular_month"
    ]["lunar_year"] = 801
    differences = audit.compare_calendar(row, "None", changed)["differences"]
    assert set(differences) == {"before_regular_month"}
    assert differences["before_regular_month"]["expected"][0] == 800


def test_declared_second_half_cannot_hide_a_deleted_first_half_branch(oracle):
    row = row_for(oracle, "0814-08-23")
    result = calculate(row, "second_half")
    assert result["natal_su27"] == "张"
    result["profile_calculation"]["short_month_assignment"]["slots"][0][
        "candidate_mansions"
    ] = ["张"]
    assert (
        "first_half_branches"
        in audit.compare_calendar(row, "second_half", result)["differences"]
    )


@pytest.mark.parametrize("mutation", ["shorten_domain", "change_expected", "omit_host"])
def test_fixed_protocol_cannot_be_replaced_by_a_narrower_passing_subset(
    tmp_path, monkeypatch, mutation
):
    protocol = json.loads(audit.PROTOCOL.read_bytes())
    if mutation == "shorten_domain":
        protocol["counts"]["chinese_hko_utc08"]["month_starts"] -= 1
    elif mutation == "change_expected":
        protocol["oracle_sha256"] = "0" * 64
    else:
        protocol["counts"].pop("japanese_naoj_historical_utc09")
    path = tmp_path / "altered.json"
    path.write_text(json.dumps(protocol))
    monkeypatch.setattr(audit, "PROTOCOL", path)
    with pytest.raises(ValueError, match="Fixed month-transition protocol changed"):
        audit.source_expectations()


@pytest.mark.parametrize(
    "civil,year,month,leap,missing,ordinary",
    [
        ("0801-03-22", 801, 1, True, "奎", "奎"),
        ("0814-09-21", 814, 7, True, "轸", "角"),
        ("2024-08-04", 2024, 6, False, "星", "张"),
    ],
)
def test_actual_missing_month_and_current_baseline_both_explained(
    civil, year, month, leap, missing, ordinary
):
    kwargs = (
        {"calendar_basis": "japanese_naoj_historical_utc09", "zone": "+09:00"}
        if civil < "1900"
        else {}
    )
    r = calendar_mansion(
        civil,
        calendar_profile="hinoo_t1299_host27",
        calendar_day_part="first_half",
        **kwargs,
    )
    t = day_evidence(r)["reading_text"]
    assert f'相邻前月末为农历{year}年{"闰" if leap else ""}{month}月29日' in t
    assert f"前半使用该月缺失三十日，按{month}月30日查得{missing}" in t
    assert f'本月常规初一另按{r["lunar_month"]}月1日查得{ordinary}' in t
