"""All adapters preserve the confirmed offset during synthetic solar rebasing."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest

from tests.ephemeris_case_runtime import native_ephemeris_files_module

pytestmark = pytest.mark.usefixtures("native_ephemeris_files_module")


from tests.test_agentic_nested_outputs import SPECS, business, call_cli, native, rest

REFERENCE = json.loads(
    (
        Path(__file__).parent / "fixtures/western-solar-offset-v1/reference.json"
    ).read_text()
)
IDS = [
    "America/New_York-2024-03-10-1",
    "Australia/Lord_Howe-2024-10-05-1",
    "Asia/Shanghai-1991-04-13-1",
    "Pacific/Apia-2011-12-30-1",
]
ROWS = [next(r for r in REFERENCE["rows"] if r["id"] == key) for key in IDS]
KEYS = ["astro_chart", "astro_hellen", "astro_chart13", "astro_germany"]


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["id"])
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_named_clock_rebase_and_explanation_match_all_adapters(
    key, row, zodiacal, rest, tmp_path, capsys
):
    spec = SPECS[key]
    wall = datetime.fromisoformat(row["recorded_local"])
    payload = dict(
        birth_year=wall.year,
        birth_month=wall.month,
        birth_day=wall.day,
        birth_hour=wall.hour,
        birth_minute=wall.minute,
        birth_timezone=row["zone"],
        birth_longitude=row["longitude"],
        birth_latitude=row["latitude"],
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
                    datetime.fromisoformat(person["utc_datetime"])
                    - datetime.fromisoformat(row["expected_effective_utc"])
                ).total_seconds()
            )
            <= 0.0002
        )
        basis = person["true_solar"]["time_reference"]
        assert basis["rebase_arithmetic"] == "frozen_recorded_utc_offset_v1"
        assert basis["recorded_utc_offset_seconds"] == row["recorded_offset_seconds"]
        assert basis["recorded_local_datetime"] == row["recorded_local"]
        assert basis["rebased_utc"] == person["utc_datetime"]
        assert basis["rebased_solar_clock_datetime"] == person["birth_datetime"]
        assert (
            abs(basis["rebase_utc_shift_seconds"] - row["correction_seconds"]) <= 0.0002
        )


@pytest.mark.parametrize("key", KEYS)
def test_unconfirmed_repeated_nominal_hour_is_still_rejected(
    key, rest, tmp_path, capsys
):
    spec = SPECS[key]
    payload = dict(
        birth_year=2024,
        birth_month=11,
        birth_day=3,
        birth_hour=1,
        birth_minute=30,
        birth_timezone="America/New_York",
        birth_longitude=-74,
        birth_latitude=40,
        use_true_solar_time=True,
    )
    http = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys, [])
    protocol = asyncio.run(native(spec, payload))
    assert http.status_code == 400 and code == 1 and protocol.is_error
    for value in [http.json(), cli, json.loads(protocol.content[0].text)]:
        assert value["error_code"] == "validation_error"
        assert "ambiguous local time" in value["error"]
