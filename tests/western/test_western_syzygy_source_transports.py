"""Lunation source receipts and integrity errors reach all public adapters."""

import asyncio
import json

import pytest

from fatebridge.core.astro import classical, runtime
from fatebridge.services.astrology import _build_almuten_figuris_line
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    native,
    rest,
)
from tests.support.syzygy_source_profiles import (  # noqa: F401
    syzygy_profile_directories,
    syzygy_source_profile,
)


def inputs(year, zodiacal):
    return dict(
        birth_year=year,
        birth_month=1,
        birth_day=10 if year == 1800 else 4,
        birth_hour=12,
        birth_minute=0,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=40,
        use_true_solar_time=False,
        zodiacal=zodiacal,
    )


@pytest.mark.parametrize("key", ["astro_chart", "astro_hellen", "astro_chart13"])
@pytest.mark.parametrize("year", [1800, 2026])
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize(
    "syzygy_source_profile", ["recorded5", "full37", "empty0"], indirect=True
)
def test_actual_source_history_on_rest_mcp_cli(
    key, year, zodiacal, rest, tmp_path, capsys, syzygy_source_profile
):
    spec = SPECS[key]
    payload = inputs(year, zodiacal)
    fields = [
        "classical.syzygy.ephemeris_source",
        "classical.syzygy.julian_day_tt",
        "classical.syzygy.longitude",
    ]
    http = rest.post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", 0),
        ],
    )
    assert http.status_code == 200, http.text
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        [
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
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=fields,
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    assert code == 0 and not protocol.is_error
    values = [http.json(), cli, protocol.structured_content]
    assert business(values[0]) == business(values[1]) == business(values[2])
    for value in values:
        spec.output_model.model_validate(value)
        syzygy = value["classical"]["syzygy"]
        source = syzygy["ephemeris_source"]
        mixed = syzygy_source_profile == "recorded5" and year == 1800
        assert source["models_stable"] == (not mixed)
        assert not source["absolute_accuracy_certified"]
        assert source["sample_contexts"]
        if mixed:
            assert source["models_by_body"] == {
                "Sun": ["moshier", "swieph"],
                "Moon": ["moshier", "swieph"],
            }
        else:
            model = "moshier" if syzygy_source_profile == "empty0" else "swieph"
            assert source["models_by_body"] == {"Sun": [model], "Moon": [model]}
        line = _build_almuten_figuris_line(
            {
                "classical": {
                    "almuten_figuris": {"winner": "Sun", "totals": {"Sun": 1}},
                    "syzygy": syzygy,
                }
            }
        )
        assert ("星历模型切换" in line) == mixed


@pytest.mark.parametrize("zodiacal", [0, 1])
def test_bad_lunation_frame_is_not_silently_omitted(
    zodiacal, monkeypatch, rest, tmp_path, capsys
):
    helper = classical._luminary_lon_speed
    native_call = runtime.ephemeris_call
    count = []

    def altered(operation, *args, **kwargs):
        result = native_call(operation, *args, **kwargs)
        if operation == "calc" and args[1] in [runtime.swe.SUN, runtime.swe.MOON]:
            count.append(args[0])
            return result[0], result[1] | runtime.swe.FLG_EQUATORIAL
        return result

    def wrapped(*args, **kwargs):
        with monkeypatch.context() as patch:
            patch.setattr(runtime, "ephemeris_call", altered)
            return helper(*args, **kwargs)

    monkeypatch.setattr(classical, "_luminary_lon_speed", wrapped)
    spec = SPECS["astro_chart"]
    payload = inputs(2026, zodiacal)
    http = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    protocol = asyncio.run(native(spec, payload))
    assert http.status_code == 503, http.text
    assert code == 1 and protocol.is_error and len(count) >= 3
    for value in [http.json(), cli, json.loads(protocol.content[0].text)]:
        assert value["error_code"] == "ephemeris_source_inconsistent"
        assert value["retryable"] is False
        assert "coordinate_contract_changed" in json.dumps(value["issues"])
