"""Historical edge facts are sourced, not modern-calendar extrapolations."""

import base64
import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from fatebridge.validation.sukuyo_historical_sources import (
    REFORM_MONTH,
    MonthStart,
    _sequence_errors,
    gregorian_ordinal,
    parse_hutime,
    parse_naoj,
)

PRIMARY = json.loads(
    (Path(__file__).parent / "data/sukuyo-historical-edge-probes.json").read_bytes()
)


def naoj(year):
    row = next(row for row in PRIMARY["naoj"] if row["lunar_year"] == year)
    raw = base64.b64decode(row["raw_csv_base64"])
    assert hashlib.sha256(raw).hexdigest() == row["response_sha256"]
    return parse_naoj(raw, year)


def test_astronomical_year_zero_is_retained_as_context_for_gregorian_year_one():
    rows = naoj(0)
    november = next(row for row in rows if (row.year, row.month) == (0, 11))
    assert november.ordinal == -18
    assert november.fields(date(1, 1, 1).toordinal()) == [0, 11, 20, False]
    assert naoj(0)[0].ordinal == gregorian_ordinal(0, 1, 23)


@pytest.mark.parametrize(
    "civil",
    [
        date(1, 1, 1),
        date(400, 2, 29),
        date(806, 1, 28),
        date(1582, 10, 15),
        date(1872, 12, 31),
    ],
)
def test_gregorian_index_matches_standard_library_without_a_1582_cutover(civil):
    assert gregorian_ordinal(civil.year, civil.month, civil.day) == civil.toordinal()


@pytest.mark.parametrize(
    "fields", [(0, 2, 30), (100, 2, 29), (1, 0, 1), (1, 13, 1), (1, 1, True)]
)
def test_invalid_gregorian_dates_are_rejected(fields):
    with pytest.raises(ValueError):
        gregorian_ordinal(*fields)


def test_two_publishers_agree_on_806_new_year_under_explicit_gregorian_input():
    first = naoj(806)[0]
    assert (first.ordinal, first.year, first.month, first.leap) == (
        date(806, 1, 28).toordinal(),
        806,
        1,
        False,
    )
    raw = base64.b64decode(PRIMARY["hutime"]["raw_response_base64"])
    assert hashlib.sha256(raw).hexdigest() == PRIMARY["hutime"]["response_sha256"]
    month, length = parse_hutime(json.loads(raw)[2], date(806, 2, 1))
    assert month == first and length == 29


def test_meiji_reform_month_is_two_days_not_a_missing_28_or_29_day_record():
    final = naoj(1872)[-1]
    assert final == MonthStart(REFORM_MONTH, 1872, 12, False)
    raw = base64.b64decode(PRIMARY["hutime"]["raw_response_base64"])
    month, length = parse_hutime(json.loads(raw)[6], date(1872, 12, 31))
    assert month == final and length == 2
    assert not _sequence_errors([final], date(1873, 1, 1).toordinal())
    assert final.fields(date(1872, 12, 31).toordinal()) == [1872, 12, 2, False]
    invalid = MonthStart(date(1871, 12, 30).toordinal(), 1871, 12, False)
    assert _sequence_errors([invalid], invalid.ordinal + 2)


def test_wrong_naoj_year_and_hutime_flag_or_resource_are_rejected():
    raw = base64.b64decode(PRIMARY["naoj"][0]["raw_csv_base64"])
    with pytest.raises(ValueError):
        parse_naoj(raw, 1)
    row = json.loads(base64.b64decode(PRIMARY["hutime"]["raw_response_base64"]))[6]
    with pytest.raises(ValueError):
        parse_hutime({**row, "isLeap": "True"}, date(1872, 12, 31))
    with pytest.raises(ValueError):
        parse_hutime(
            {**row, "uri": row["uri"].replace("1001.1", "1002.1")}, date(1872, 12, 31)
        )
