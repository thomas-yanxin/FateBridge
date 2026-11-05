"""The resolved solar-clock basis is delivered through actual adapters."""

import json
from datetime import datetime

import pytest

from tests.support.ephemeris_case_runtime import (
    native_ephemeris_files_module as native_ephemeris_files_module,
)
from tests.support.transports import SPECS, business, rest, surface_calls
from tests.western.test_western_solar_eot_ut1 import COHERENT_BY_UTC

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")

ROW = COHERENT_BY_UTC["9999-08-11T12:00:00+00:00"]


@pytest.mark.parametrize(
    "key", ["astro_chart", "astro_hellen", "astro_chart13", "astro_germany"]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("use_solar", [False, True])
def test_optional_rebase_clock_basis_on_rest_mcp_cli(
    key, zodiacal, use_solar, surface_calls
):
    spec = SPECS[key]
    payload = dict(
        birth_year=9999,
        birth_month=8,
        birth_day=11,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        use_true_solar_time=use_solar,
        zodiacal=zodiacal,
    )
    person_path = "base_chart.person_info" if key == "astro_germany" else "person_info"
    fields = [person_path, "chart_profile"]
    http, protocol, code, cli = surface_calls(
        spec,
        payload,
        params=[("fields", f) for f in fields]
        + [("strict_fields", "true"), ("include_snapshot_text", "false")],
        options={
            "fields": fields,
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=[
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--response-char-limit",
            "0",
        ],
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
        solar = person["true_solar"]
        actual = (
            datetime.fromisoformat(person["utc_datetime"])
            - datetime.fromisoformat(ROW["utc"])
        ).total_seconds()
        assert abs(actual - (ROW["eot_seconds"] if use_solar else 0)) <= 0.0002
        if use_solar:
            basis = solar["time_reference"]
            assert basis["method_id"] == "western_solar_rebase_coherent_tt_ut1_v2"
            assert basis["recorded_utc"] == ROW["utc"]
            assert abs(basis["equation_of_time_seconds"] - ROW["eot_seconds"]) <= 0.0002
            assert (
                abs(basis["equation_of_time_julian_day_ut1"] - ROW["jd_ut1"]) * 86400
                <= 0.0002
            )
            assert basis["future_leap_seconds_assumed_unchanged"] is True
        else:
            assert solar == {"applied": False, "correction_minutes": 0.0}
