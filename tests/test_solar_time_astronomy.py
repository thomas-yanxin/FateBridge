"""Independent NOAA cached values and physical-instant solar normalization."""

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from fatebridge.core import ephemeris_runtime
from fatebridge.utils.birth_input import create_person_info
from fatebridge.utils.solar_time import (
    EQUATION_OF_TIME_METHOD,
    SOLAR_TIME_STRATEGY_LONGITUDE_ONLY,
    calculate_equation_of_time_minutes,
    calculate_solar_time_adjustment,
    normalize_birth_time,
)

ROOT = Path(__file__).parent / "fixtures/noaa_solar_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text(encoding="utf-8"))
CASES = REFERENCE["cases"]


def test_expected_values_are_the_original_noaa_cache_not_engine_output():
    raw = (ROOT / REFERENCE["source_file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REFERENCE["source_sha256"]
    assert len(CASES) == 366
    table = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
    office = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    with ZipFile(ROOT / REFERENCE["source_file"]) as archive:
        rows = ET.fromstring(archive.read("content.xml")).findall(
            f".//{{{table}}}table-row"
        )
    for case in CASES:
        cells = []
        for cell in rows[case["source_row"] - 1]:
            if cell.tag not in (
                f"{{{table}}}table-cell",
                f"{{{table}}}covered-table-cell",
            ):
                continue
            repeat = int(cell.get(f"{{{table}}}number-columns-repeated", "1"))
            cells.extend([cell] * min(repeat, 40 - len(cells)))
            if len(cells) == 40:
                break
        assert (
            float(cells[21].get(f"{{{office}}}value"))
            == case["equation_of_time_minutes"]
        )
        assert float(cells[5].get(f"{{{office}}}value")) == case["julian_day"]
        # The source spreadsheet's local noon at UTC-7 is 19:00 UTC.
        assert (
            case["at_utc"]
            == cells[3].get(f"{{{office}}}date-value") + "T19:00:00+00:00"
        )


@pytest.mark.parametrize("case", CASES, ids=lambda row: row["at_utc"][:10])
def test_equation_of_time_agrees_with_all_published_cached_rows(case):
    actual = calculate_equation_of_time_minutes(datetime.fromisoformat(case["at_utc"]))
    assert (
        abs(actual - case["equation_of_time_minutes"]) * 60
        <= REFERENCE["tolerance_seconds"]
    )


def test_one_physical_instant_has_one_eot_across_date_line_and_dst_offsets():
    utc = datetime(2024, 2, 29, 23, 30, tzinfo=timezone.utc)
    expected = calculate_equation_of_time_minutes(utc)
    for offset in [-12, -5, 0, 8, 14]:
        local = utc.astimezone(timezone(timedelta(hours=offset)))
        assert calculate_equation_of_time_minutes(local) == expected
        assert (
            calculate_solar_time_adjustment(local, f"{offset:+03d}:00", 120)[
                "equation_of_time_minutes"
            ]
            == expected
        )


def test_apparent_correction_rejects_ambiguous_instants_or_missing_engine(monkeypatch):
    with pytest.raises(ValueError, match="时区"):
        calculate_equation_of_time_minutes(datetime(2024, 1, 1))
    monkeypatch.setattr(ephemeris_runtime, "swe", None)
    with pytest.raises(ImportError, match="Swiss"):
        calculate_solar_time_adjustment(datetime(2024, 1, 1), "UTC", 0)
    # A longitude-only rule has no astronomical EOT dependency.
    result = calculate_solar_time_adjustment(
        datetime(2024, 1, 1),
        "UTC",
        15,
        strategy=SOLAR_TIME_STRATEGY_LONGITUDE_ONLY,
    )
    assert result["total_correction_minutes"] == 60


def test_corrected_hour_boundary_and_method_are_not_hidden():
    person = create_person_info(
        2024,
        12,
        6,
        0,
        birth_minute=52,
        birth_longitude=0,
        birth_timezone="UTC",
        use_true_solar_time=True,
    )
    result = normalize_birth_time(person)
    # The old 364-day sinusoid yields about 00:59; the astronomical equation
    # puts this explicitly documented counterexample after 01:00.
    assert result.corrected_datetime.hour == 1
    assert result.as_dict()["equation_of_time_method"] == EQUATION_OF_TIME_METHOD
    b = 2 * math.pi * (result.input_datetime.timetuple().tm_yday - 81) / 364
    old_minutes = 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)
    assert (result.input_datetime + timedelta(minutes=old_minutes)).hour == 0
