"""Complete printed-date conformance does not certify all birth clocks."""

import gzip
import json
from datetime import date
from hashlib import sha256
from pathlib import Path

import pytest

from fatebridge.core import almanac
from scripts.ziwei.audit_ziwei import hko_rows
from tests.support.transports import SPECS, business
from tests.support.transports import rest as _shared_rest
from tests.support.transports import surface_calls

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/data/bazi_pmo_calendar_v1"
REFERENCE = json.loads(
    gzip.decompress((FIXTURE / "expected-calendar.json.gz").read_bytes())
)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def frozen(name):
    path = FIXTURE / name
    assert digest(path) == path.with_suffix(".sha256").read_text().strip()
    return json.loads(path.read_text())


@pytest.mark.filterwarnings(
    "ignore:(from|to)SolarDate is deprecated.*:DeprecationWarning"
)
@pytest.mark.filterwarnings("ignore:use is_leap_month:DeprecationWarning")
def test_hko_missing_month_cells_remain_partial_source_observations():
    source = ROOT / "tests/data/ziwei_independent/hko/T1901c.txt"
    rows = hko_rows(source.read_text(encoding="utf-8-sig"), 1901)
    partial = [row for row in rows if row["month"] is None]
    assert len(partial) == 19
    assert all(row["day"] is not None for row in partial)


def test_current_shared_date_components_match_every_frozen_literal_not_only_first_run():
    differences = []
    for row in REFERENCE["rows"]:
        solar = date.fromisoformat(row["solar"])
        actual = almanac._lunar_date_from_solar(solar)
        got = (actual.year, actual.month, actual.day, actual.isLeapMonth)
        expected = (row["year"], row["month"], row["day"], row["is_leap_month"])
        ganzhi = almanac.get_day_ganzhi(solar.year, solar.month, solar.day)
        if got != expected or ganzhi != row["day_ganzhi"]:
            differences.append((row["solar"], got, expected, ganzhi, row["day_ganzhi"]))
    assert differences == []


@pytest.mark.parametrize(
    "case", frozen("edge-clock-regressions.json")["cases"], ids=lambda c: c["id"]
)
def test_accepted_birth_edges_do_not_fake_lunar_fields_outside_corrected_date_range(
    case, surface_calls
):
    spec = SPECS["bazi_birth"]
    payload = {
        k: v
        for k, v in case.items()
        if k.startswith("birth_") or k == "use_true_solar_time"
    }
    payload.update(
        gender="男",
        analysis_year=case["birth_year"],
        analysis_month=case["birth_month"],
        analysis_day=case["birth_day"],
    )
    fields = ["bazi_birth.calendar_context"]
    options = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    http, protocol, code, cli = surface_calls(
        spec, payload, projection=options, cli_first=False
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for result in (http.json(), protocol.structured_content, cli):
        context = result["bazi_birth"]["calendar_context"]
        assert context["solar_datetime"][:10] == case["expected_corrected_solar_date"]
        assert context["lunar_calendar"] is None
        assert context["lunar_calendar_support"]["supported"] is False
        assert context["lunar_calendar_support"]["supported_range"] == {
            "start": "1900-01-01",
            "end": "2100-12-31",
        }
        assert (
            context["bazi_month_boundary"]["comparison_datetime"][:10]
            == f"{case['birth_year']:04}-{case['birth_month']:02}-{case['birth_day']:02}"
        )
