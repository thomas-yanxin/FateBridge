"""Actual adapters deliver the same physical solar-clock receipt."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core.astro import runtime
from fatebridge.utils.errors import EphemerisSourceError
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")

REFERENCE = json.loads(
    (
        Path(__file__).parents[1] / "data/astro/solar_clock_coherence/reference.json"
    ).read_text()
)
ROWS = [
    next(r for r in REFERENCE["rows"] if r["id"] == "model-" + stamp)
    for stamp in ["0001-08-11T12:00:00+00:00", "9999-08-11T12:00:00+00:00"]
]
KEYS = ["astro_chart", "astro_hellen", "astro_chart13", "astro_germany"]


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["id"])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_coherent_solar_clock_receipt_on_all_adapters(
    key, row, zodiacal, rest, tmp_path, capsys
):
    spec = SPECS[key]
    moment = datetime.fromisoformat(row["utc"])
    payload = dict(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        use_true_solar_time=True,
        zodiacal=zodiacal,
    )
    path = "base_chart.person_info" if key == "astro_germany" else "person_info"
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[
            ("fields", path),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ],
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        [
            "--fields",
            path,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=[path],
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        spec.output_model.model_validate(value)
        person = (
            value["base_chart"]["person_info"]
            if key == "astro_germany"
            else value["person_info"]
        )
        assert (
            abs(
                (
                    datetime.fromisoformat(person["utc_datetime"]) - moment
                ).total_seconds()
                - row["eot_seconds"]
            )
            <= 0.0002
        )
        receipt = person["true_solar"]["time_reference"]
        assert receipt["method_id"] == "western_solar_rebase_coherent_tt_ut1_v2"
        assert receipt["recorded_julian_day_tt"] == row["jd_tt"]
        assert (
            receipt["solar_ephemeris_source"]["by_factor"]["equatorial_Sun"]["model"]
            == "swieph"
        )


@pytest.mark.parametrize("key", KEYS)
def test_clock_source_failure_remains_a_503_on_all_adapters(
    key, rest, tmp_path, capsys, monkeypatch
):
    spec = SPECS[key]
    original = runtime.ephemeris_call

    def fail(operation, *args, **kwargs):
        if operation == "calc" and args[1] == runtime.swe.SUN:
            raise EphemerisSourceError("unavailable_during")
        return original(operation, *args, **kwargs)

    monkeypatch.setattr(runtime, "ephemeris_call", fail)
    payload = dict(
        birth_year=2000,
        birth_month=1,
        birth_day=1,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        use_true_solar_time=True,
    )
    http = rest.post(spec.rest_path, json=payload, params={"fields": "analysis_type"})
    code, cli = call_cli(spec, payload, tmp_path, capsys, ["--fields", "analysis_type"])
    protocol = asyncio.run(native(spec, payload, fields=["analysis_type"]))
    value = json.loads(protocol.content[0].text)
    assert http.status_code == 503 and code == 1 and protocol.is_error
    assert cli["status_code"] == value["status_code"] == 503
    assert (
        cli["error_code"]
        == value["error_code"]
        == http.json()["error_code"]
        == "ephemeris_source_inconsistent"
    )
