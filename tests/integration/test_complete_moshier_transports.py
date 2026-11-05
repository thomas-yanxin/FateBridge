"""Unchanged DE440 TT values constrain the same current result on three ports."""

import asyncio
import json
from pathlib import Path

import pytest

from fatebridge.core.moshier_solar import MODEL_ID, PROVIDER
from tests.evaluation.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)


@pytest.mark.local_data
@pytest.mark.parametrize("year", [1800, 2200])
def test_original_years_current_roots_pass_the_original_gate_on_three_ports(
    year, monkeypatch, tmp_path, capsys, rest
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    reference = json.loads(
        (Path(__file__).parents[1] / "data/solar/de440-guard-tt.json").read_text()
    )
    assert reference["tolerance_seconds"] == 1.0
    expected = {row["index"]: row for row in reference["rows"] if row["year"] == year}
    assert len(expected) == 24
    spec = SPECS["jieqi_timeline_analysis"]
    payload = {**inputs(spec), "target_year": year}
    field = "target_year_jieqi"
    http = rest.post(
        spec.rest_path,
        json=payload,
        params={
            "fields": field,
            "strict_fields": True,
            "include_snapshot_text": False,
            "response_char_limit": 0,
        },
    )
    protocol = asyncio.run(
        native(
            spec,
            payload,
            fields=[field],
            strict_fields=True,
            include_snapshot_text=False,
        )
    )
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        ["--fields", field, "--strict-fields", "--response-char-limit", "0"],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    outputs = [business(p) for p in (http.json(), protocol.structured_content, cli)]
    assert outputs[0] == outputs[1] == outputs[2]
    for output in outputs:
        rows = output[field]
        assert len(rows) == 24
        for index, row in enumerate(rows):
            assert row["resolution_provider"] == PROVIDER
            assert row["ephemeris_model"] == MODEL_ID
            details = row["solar_model_details"]
            assert details["model_id"] == MODEL_ID
            error = (
                details["selected_crossing_jd_tt"] - expected[index]["jd_tt"]
            ) * 86400
            assert abs(error) <= reference["tolerance_seconds"]
