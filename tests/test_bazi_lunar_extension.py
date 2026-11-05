"""Normative calendar fidelity, legacy preservation and actual public transports.

HKO data is used in production for this extension. Tests against that same
table verify faithful conversion, not independent astronomical accuracy.
"""

import asyncio
import json
from datetime import date, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from fatebridge.core.almanac import _lunar_date_from_solar, get_lunar_context
from fatebridge.core.lunar_supplement import convert, source_for
from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native
from tests.test_agentic_nested_outputs import rest as _shared_rest

rest = _shared_rest

ROOT = Path(__file__).resolve().parents[1]
RESULT = json.loads((ROOT / "tests/data/bazi/hko-normative-cells.json").read_text())
TOPICS = [
    "birth",
    "career",
    "wealth",
    "health",
    "children",
    "education",
    "personality",
    "relatives",
    "marriage",
    "romance",
]


@pytest.mark.parametrize(
    "case", RESULT["target_extension"]["cases"], ids=lambda c: c["date"]
)
def test_each_of_326_normative_hko_dates_is_converted_faithfully(case):
    value = _lunar_date_from_solar(date.fromisoformat(case["date"]))
    assert {k: getattr(value, k) for k in case["expected"]} == case["expected"]


@pytest.mark.parametrize("day", [date(2057, 9, 28), date(2057, 10, 27)])
def test_other_candidate_disagreements_do_not_replace_existing_calendar(day):
    source = next(
        r for r in RESULT["all_diagnostic_mismatches"] if r["date"] == day.isoformat()
    )
    actual = _lunar_date_from_solar(day)
    assert {k: getattr(actual, k) for k in source["expected"]} == source["expected"]
    assert source_for(day) is None


def test_supplement_never_extrapolates_or_mutates_source_metadata():
    for day in [date(1900, 1, 1), date(2100, 2, 8), date(2101, 1, 1)]:
        assert convert(day) is None
        assert source_for(day) is None
    original = source_for(date(2100, 12, 31))
    original["method_id"] = "changed by caller"
    assert source_for(date(2100, 12, 31))["method_id"] == "hko_2100_month_starts_v1"
    # The HKO supplement still never extrapolates backwards; the newly
    # supported prefix is provided by a separate, identified PMO table.
    prefix = get_lunar_context(datetime(1900, 1, 1, 12))
    assert prefix is not None
    assert prefix["conversion_source"]["method_id"] == "pmo_1900_january_prefix_v1"
    assert get_lunar_context(datetime(1899, 12, 31, 12)) is None
    assert get_lunar_context(datetime(2101, 1, 1, 12)) is None


@pytest.mark.parametrize("topic", TOPICS)
def test_extension_date_is_consistent_on_all_ten_bazi_transports(
    topic, rest, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    args = {
        "birth_year": 2100,
        "birth_month": 12,
        "birth_day": 31,
        "birth_hour": 12,
        "birth_timezone": "Asia/Shanghai",
        "gender": "男",
        "use_true_solar_time": False,
        "analysis_year": 2100,
        "analysis_month": 12,
        "analysis_day": 31,
    }
    response = rest.post(spec.rest_path, json=args)
    protocol = asyncio.run(native(spec, args))
    code, local = call_cli(
        spec, args, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
    if topic == "birth":
        lunar = outputs[0]["bazi_birth"]["calendar_context"]["lunar_calendar"]
        assert (lunar["year"], lunar["month"], lunar["day"]) == (2100, 12, 1)
        assert lunar["conversion_source"]["method_id"] == "hko_2100_month_starts_v1"


@pytest.mark.parametrize(
    "solar,expected", [("2100-02-09", (2100, 1, 1)), ("2100-12-31", (2100, 12, 1))]
)
def test_lunar_conversion_exposes_its_finite_source_on_all_transports(
    solar, expected, rest, tmp_path, capsys
):
    spec = SPECS["nongli_time"]
    args = {"date": solar, "time": "12:00:00", "zone": "Asia/Shanghai", "time_alg": 1}
    response = rest.post(spec.rest_path, json=args)
    protocol = asyncio.run(native(spec, args))
    code, local = call_cli(
        spec, args, tmp_path, capsys, flags=["--response-char-limit", "0"]
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    outputs = [response.json(), local, protocol.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        lunar = result["lunar_calendar"]
        assert (lunar["year"], lunar["month"], lunar["day"]) == expected
        assert lunar["conversion_source"]["publisher"] == "香港天文台"
        assert lunar["conversion_source"]["raw_sha256"]
