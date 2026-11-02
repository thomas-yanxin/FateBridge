"""Full and strict projected natal responses retain the actual point identity."""

import asyncio
import json

import pytest

from tests.test_agentic_nested_outputs import SPECS, call_cli, native, rest
from tests.test_western_natal_reference_points import INPUT


@pytest.mark.parametrize("variant", ["chart", "hellen_chart", "chart13"])
@pytest.mark.parametrize("zodiacal", [0, 1])
@pytest.mark.parametrize("project", [False, True])
def test_actual_point_receipts_survive_all_protocols(
    variant, zodiacal, project, monkeypatch, rest, tmp_path, capsys
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["astro_chart"]
    inputs = dict(INPUT, chart_variant=variant, zodiacal=zodiacal)
    params = [("response_char_limit", 0)]
    flags = ["--response-char-limit", "0"]
    kwargs = {}
    if project:
        fields = ["chart_profile.ephemeris_reference_points", "summary"]
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        kwargs = dict(fields=fields, strict_fields=True, include_snapshot_text=False)
    http = rest.post(spec.rest_path, json=inputs, params=params)
    assert http.status_code == 200, http.text
    code, cli = call_cli(spec, inputs, tmp_path, capsys, flags)
    protocol = asyncio.run(native(spec, inputs, **kwargs))
    assert code == 0 and not protocol.is_error
    values = [http.json(), cli, json.loads(protocol.content[0].text)]
    expected = values[0]["chart_profile"]["ephemeris_reference_points"]
    for value in values:
        spec.output_model.model_validate(value)
        p = value["chart_profile"]["ephemeris_reference_points"]
        assert p == expected
        assert p["center_body_correction_applied"] is False
        assert {"Mars", "Jupiter", "Saturn"} <= set(p["system_barycenters"])
        assert not p["approximate_points"] and not p["unresolved_points"]
        assert p["note_zh"] in value["summary"]
        if project:
            assert "planets" not in value
        else:
            assert p["note_zh"] in value["snapshot_text"]
