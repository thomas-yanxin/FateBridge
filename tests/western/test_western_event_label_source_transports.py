"""UTC-source faults stop full calculation before an unrelated field projection."""

import asyncio
import json

import pytest

from fatebridge.utils.errors import EphemerisSourceError
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)
from tests.western.test_western_event_label_sources import MODULES, install_carriers

CASES = [
    ("astro_horary", "planetary"),
    ("astro_horary", "lunar"),
    ("astro_election", "lunar"),
]


@pytest.mark.parametrize("key,wrapper", CASES)
@pytest.mark.parametrize("zodiac", ["Tropic", "Sidereal"])
@pytest.mark.parametrize("fault", [False, True])
def test_synthetic_carrier_control_and_source_failure_on_all_protocols(
    key, wrapper, zodiac, fault, monkeypatch, rest, tmp_path, capsys
):
    install_carriers(monkeypatch)
    if fault:

        def broken(_):
            raise EphemerisSourceError("changed_during")

        monkeypatch.setattr(MODULES[wrapper], "utc_from_tt", broken)
    spec = SPECS[key]
    payload = {**inputs(spec), "zodiac_type": zodiac}
    http = rest.post(
        spec.rest_path,
        json=payload,
        params={
            "fields": "analysis_type",
            "strict_fields": "true",
            "include_snapshot_text": "false",
        },
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=["analysis_type"],
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        [
            "--fields",
            "analysis_type",
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
    )
    values = [http.json(), json.loads(protocol.content[0].text), cli]
    if fault:
        assert http.status_code == 503, http.text
        assert protocol.is_error and code == 1
        for value in values:
            assert value["error_code"] == "ephemeris_source_inconsistent"
            assert value["issues"] == [
                {"path": "runtime.ephemeris_data", "code": "changed_during"}
            ]
            assert value["retryable"] is False
            assert "analysis_type" not in value
    else:
        assert http.status_code == 200, http.text
        assert not protocol.is_error and code == 0
        assert business(values[0]) == business(values[1]) == business(values[2])
        for value in values:
            assert value["analysis_type"]
            spec.output_model.model_validate(value)
