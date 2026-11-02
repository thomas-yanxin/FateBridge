"""A source rejection cannot become a successful projection on any adapter."""

import asyncio
import json

import pytest

from fatebridge.utils.errors import EphemerisSourceError
from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest
from tests.test_western_source_errors import inject


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen", "astro_chart13"])
@pytest.mark.parametrize(
    "target",
    [
        "native_angles",
        "sun_event",
        "planetary_hour_calendar",
        "classical_obliquity",
        "tropical_house_layout",
        "sidereal_house_layout",
        "extended_utc_display",
    ],
)
def test_full_calculation_rejection_survives_unrelated_projection(
    key,
    target,
    monkeypatch,
    rest,
    tmp_path,
    capsys,
):
    spec = SPECS[key]
    failure = EphemerisSourceError("changed_during")
    inject(target, failure, monkeypatch)
    payload = dict(
        birth_year=1 if target == "extended_utc_display" else 2026,
        birth_month=1,
        birth_day=1 if target == "extended_utc_display" else 4,
        birth_hour=12,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        hsys=0 if target == "native_angles" else 3,
        zodiacal=int(target == "sidereal_house_layout"),
    )
    flags = dict(
        fields=["person_info.name"], strict_fields=True, include_snapshot_text=False
    )
    http = rest.post(
        spec.rest_path,
        json=payload,
        params={
            "fields": "person_info.name",
            "strict_fields": "true",
            "include_snapshot_text": "false",
        },
    )
    protocol = asyncio.run(native(spec, payload, **flags))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        [
            "--fields",
            "person_info.name",
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    assert http.status_code == 503, http.text
    assert protocol.is_error and code == 1
    values = [http.json(), json.loads(protocol.content[0].text), cli]
    for value in values:
        assert value["error_code"] == "ephemeris_source_inconsistent"
        assert value["retryable"] is False
        assert value["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "changed_during"}
        ]
        assert "person_info" not in value and "planetary_hours" not in value
