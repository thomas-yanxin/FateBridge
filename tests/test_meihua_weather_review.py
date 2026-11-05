"""Frozen original scores, independent source tokens and synthetic clock controls."""

import ast
import copy
import gzip
import hashlib
import json
import shutil
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from fatebridge.validation import meihua_weather_reference_study as strict
from fatebridge.validation.meihua_weather_references import (
    climatology_reference,
    monthly_climatology_profile,
)
from fatebridge.validation.meihua_weather_study import (
    RainObservation,
    _aware,
    parse_hko_rainfall,
)

FOLDER = Path(__file__).parent / "fixtures/meihua_weather_review_v1"
STUDY = FOLDER / "study"
for name, expected in [
    (
        "original-manifest.json",
        "70431f3c5bc52755fe52dfe577434988d1ebddb36e21ac0f2c82d90ac9600b4f",
    ),
    (
        "independent-manifest.json",
        "31ed804a9a36922a2126db206f7899255b1ad4b32c9123cf6f37414d6a1b15c0",
    ),
]:
    raw = (FOLDER / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    for relative, digest in json.loads(raw)["files"].items():
        if not str(relative).endswith(".py"):
            assert (
                hashlib.sha256((FOLDER / relative).read_bytes()).hexdigest() == digest
            )
assert (
    hashlib.sha256((FOLDER / "climate-input-profile.json").read_bytes()).hexdigest()
    == "0777119f724c70bdf53b575dcf476befd08b26014a572691ed94b6c0fba0bd3d"
)
LEGACY = Path(__file__).parent / "fixtures/meihua_temporal_gates_v1"
assert (
    hashlib.sha256((LEGACY / "manifest.json").read_bytes()).hexdigest()
    == "065cb780830bd1922965ee2c714cbcf771450bbe8563b539302bb975c989b0cf"
)
for n, digest in json.loads((LEGACY / "manifest.json").read_bytes())["files"].items():
    assert hashlib.sha256((LEGACY / n).read_bytes()).hexdigest() == digest
CLOCKS = json.loads((LEGACY / "cases324.json").read_bytes())
CLIMATE = json.loads((FOLDER / "independent-climate-clock81.json").read_bytes())
ALL_CLOCKS = [*CLOCKS, *CLIMATE]
assert len(ALL_CLOCKS) == 405


@pytest.mark.parametrize("case", ALL_CLOCKS, ids=lambda r: r["id"])
def test_legacy_study_clock_uses_the_independent_integer_instant(case):
    expected = datetime(*case["expected_utc_components"], tzinfo=timezone.utc)
    assert _aware(case["label"]).astimezone(timezone.utc) == expected


@pytest.fixture(scope="module")
def synthetic_training():
    observations, publications = {}, {}
    day = date(1991, 1, 1)
    while day < date(2021, 1, 1):
        observations[day] = RainObservation(
            day, "0", "C", "complete_numeric", Decimal(0)
        )
        publications[day] = datetime.combine(
            day + timedelta(days=1), time(), timezone(timedelta(hours=8))
        )
        day += timedelta(days=1)
    assert len(observations) == 10958
    return observations, publications


@pytest.mark.parametrize("case", CLIMATE, ids=lambda r: r["id"])
def test_publication_maximum_and_availability_preserve_true_instants(
    case, synthetic_training
):
    issue = datetime(2021, 2, 28, 12, tzinfo=timezone.utc)
    expected = datetime(*case["expected_utc_components"], tzinfo=timezone.utc)
    first = datetime(
        *case["wall_components"],
        tzinfo=timezone(timedelta(microseconds=case["offset_microseconds"])),
    )
    assert first.astimezone(timezone.utc) == expected
    observations, original_times = synthetic_training
    times = dict(original_times)
    times[date(1991, 3, 1)], times[date(1992, 3, 1)] = first, issue
    profile = monthly_climatology_profile(observations, publication_times=times)
    maximum = profile["months"][2]["latest_declared_publication"]
    # Decode by the two input identities, not by the implementation under test.
    actual_maximum = (
        expected
        if maximum == first.isoformat()
        else issue if maximum == issue.isoformat() else None
    )
    assert actual_maximum == max(expected, issue)
    result = climatology_reference(date(2021, 3, 1), issue, profile)
    assert (result["label_under_declared_availability"] == "dry") == case[
        "expected_publication_available_at_issue"
    ]
    direct = json.loads((FOLDER / "climate-input-profile.json").read_bytes())
    direct["months"][2]["latest_declared_publication"] = case["label"]
    result = climatology_reference(date(2021, 3, 1), issue, direct)
    assert (result["label_under_declared_availability"] == "dry") == case[
        "expected_publication_available_at_issue"
    ]
    assert not result["source_provenance_authenticated"]
    assert not result["classical_rule_or_engine_forecast"]


def test_all13057_source_tokens_flags_and_rainfall_events_match_independent_reference():
    expected = json.loads(
        gzip.decompress((FOLDER / "independent-source-rows13057.json.gz").read_bytes())
    )
    values = parse_hko_rainfall(
        (STUDY / "sources/daily_HKO_RF_ALL.csv").read_bytes(),
        start=date(1991, 1, 1),
        end=date(2026, 10, 1),
    )
    actual = [
        {
            "date": day.isoformat(),
            "source_value": v.raw_value,
            "source_completeness": v.completeness,
            "expected_rain_ge0_1_mm": v.occurred(Decimal("0.1")),
        }
        for day, v in sorted(values.items())
    ]
    assert len(actual) == 13057
    assert actual == expected


@pytest.mark.parametrize(
    "path,expected",
    [
        ("first;;second", ["first", "second"]),
        ("first::", ["first", "/"]),
        ("a;" * 21 + "last", ["a"] * 19 + ["a;a;last"]),
    ],
)
def test_reviewed_search_path_changes_have_explicit_retained_examples(
    path, expected, monkeypatch
):
    from fatebridge.core import ephemeris_paths

    monkeypatch.setattr(ephemeris_paths.os, "pathsep", ":")
    monkeypatch.setattr(ephemeris_paths.os, "sep", "/")
    assert [
        str(root) for root in ephemeris_paths.ephemeris_search_directories(path)
    ] == expected


def csv_control(first, tail):
    return (
        first
        + "\nDaily Total Rainfall (mm) at the Hong Kong Observatory\n年/Year,月/Month,日/Day,數值/Value,數據完整性/data Completeness\n"
        + tail
    ).encode()


def test_trace_legend_in_metadata_does_not_adjudicate_trace_values():
    raw = csv_control(
        "metadata: Trace means rainfall less than 0.05 mm", "2025,1,1,Trace,C\n"
    )
    row = parse_hko_rainfall(raw, start=date(2025, 1, 1), end=date(2025, 1, 2))[
        date(2025, 1, 1)
    ]
    assert row.occurred(Decimal("0.1")) is None


def test_conflicting_trace_footer_is_unknown_instead_of_guessed_dry():
    raw = csv_control(
        "metadata",
        "2025,1,1,Trace,C\nTrace means rainfall less than 0.05 mm\nTrace means rainfall less than 0.10 mm\n",
    )
    row = parse_hko_rainfall(raw, start=date(2025, 1, 1), end=date(2025, 1, 2))[
        date(2025, 1, 1)
    ]
    assert row.occurred(Decimal("0.1")) is None


def test_data_after_a_footer_is_not_silently_merged_into_source_rows():
    raw = csv_control(
        "metadata",
        "2025,1,1,Trace,C\nTrace means rainfall less than 0.05 mm\n2025,1,2,0,C\n",
    )
    with pytest.raises(ValueError, match="cannot follow the source footer"):
        parse_hko_rainfall(raw, start=date(2025, 1, 1), end=date(2025, 1, 3))
