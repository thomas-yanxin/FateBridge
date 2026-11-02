"""Mixed native dependencies remain source failures over public adapters."""

import asyncio
import json

import pytest

from fatebridge.core.ephemeris_runtime import configure_ephemeris_path
from tests.test_agentic_nested_outputs import SPECS, call_cli, inputs, native, rest
from tests.test_western_mixed_moon import directories, selected


@pytest.mark.parametrize(
    "key",
    [
        "astro_chart",
        "astro_hellen",
        "astro_chart13",
        "astro_germany",
        "astro_horary",
        "astro_election",
        "profection",
        "solararc",
    ],
)
def test_partial_physical_data_is_an_explicit_source_error(
    key, selected, rest, tmp_path, capsys
):
    spec = SPECS[key]
    selected("planet_only")
    payload = inputs(spec)
    # All cases are synthetic catalog engineering fixtures at contemporary epochs.
    http = rest.post(spec.rest_path, json=payload)
    code, cli = call_cli(spec, payload, tmp_path, capsys, [])
    protocol = asyncio.run(native(spec, payload))
    assert http.status_code == 503 and code == 1 and protocol.is_error
    for index, value in enumerate(
        [http.json(), cli, json.loads(protocol.content[0].text)]
    ):
        assert value["error_code"] == "ephemeris_source_inconsistent"
        assert value["retryable"] is False
        assert value["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "swiss_dependency_unavailable"}
        ]
        assert (
            "backend" not in value and "planets" not in value and "score" not in value
        )
        (tmp_path / f"{key}-{index}.json").write_text(json.dumps(value))
