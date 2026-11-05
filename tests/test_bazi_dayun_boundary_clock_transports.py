"""Full and projected REST/MCP/CLI preserve analysis-independent gap probes."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.core.timing import TimingAnalysis
from tests.test_agentic_nested_outputs import business, call_cli, native
from tests.test_agentic_nested_outputs import rest as _shared_rest
from tests.test_bazi_birth_seconds import SPECS

ROW = json.loads(
    (Path(__file__).parent / "data/bazi/dayun-boundary-clock-input.json").read_text()
)
TOOLS = [s for s in SPECS if s.key in {"timing_analysis", "dayun_analysis"}]


rest = _shared_rest


@pytest.mark.parametrize("spec", TOOLS, ids=lambda s: s.key)
@pytest.mark.parametrize("project", [False, True])
def test_shifted_analysis_keeps_safe_boundary_witness_on_three_surfaces(
    spec, project, rest, tmp_path, capsys
):
    analysis = ROW["contexts"][1]["analysis_at"]
    values = {**ROW["input"], "birth_time_uncertainty_minutes": 1}
    options = dict(as_of=analysis, include_snapshot_text=True, response_char_limit=0)
    flags = [
        "--as-of",
        analysis,
        "--include-snapshot-text",
        "true",
        "--response-char-limit",
        "0",
    ]
    if project:
        fields = suggested_fields(spec, view="birth_time_sensitivity")
        options.update(fields=fields, strict_fields=True)
        flags += ["--fields", *fields, "--strict-fields", "true"]
    mcp = asyncio.run(native(spec, values, **options))
    code, cli = call_cli(spec, values, tmp_path, capsys, flags=flags)
    response = rest.post(spec.rest_path, json=values, params=options)
    assert not mcp.is_error and code == 0 and response.status_code == 200
    results = [mcp.structured_content, cli, response.json()]
    for result in results:
        assert business(result) == business(results[0])
        spec.output_model.model_validate(result)
        sensitivity = result["birth_time_sensitivity"]
        event = sensitivity["dayun_event_analysis"]
        assert event["method_id"] == "dayun_all_boundary_gap_and_analysis_probes_v4"
        assert event["boundary_clock_scan"]["boundary_count"] == 13
        assert event["physical_precision_certified"] is False
        assert any(
            e["source"].get("scan_basis")
            == "projected_boundary_wall_image_independent_of_analysis_context"
            for e in event["events"]
        )
        period = sensitivity["dayun_boundary_ranges"][0]
        low = datetime.fromisoformat(period["earliest_start_at"]).astimezone(
            timezone.utc
        )
        high = datetime.fromisoformat(period["latest_start_at"]).astimezone(
            timezone.utc
        )
        for probe in ROW["probes"]:
            if probe["safe"]:
                timeline = TimingAnalysis.calculate_dayun_timeline(
                    datetime.fromisoformat(probe["birth_utc"]),
                    ROW["input"]["gender"],
                    ("甲", "子"),
                    ROW["zone"],
                )
                assert (
                    low
                    <= datetime.fromisoformat(timeline["start_at"]).astimezone(
                        timezone.utc
                    )
                    <= high
                )
