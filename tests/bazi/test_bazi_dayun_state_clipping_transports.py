"""All three public transports retain new states and explain actual events."""

import asyncio

import pytest

from fatebridge.application.examples import suggested_fields
from tests.bazi.test_bazi_birth_seconds import SPECS
from tests.bazi.test_bazi_dayun_state_clipping import SELECTED
from tests.support.transports import business, call_cli, native
from tests.support.transports import rest as _shared_rest

CASES = [SELECTED[0], SELECTED[10]]
TOOLS = [s for s in SPECS if s.key in {"timing_analysis", "dayun_analysis"}]


rest = _shared_rest


@pytest.mark.parametrize("row", CASES, ids=lambda r: r["id"])
@pytest.mark.parametrize("spec", TOOLS, ids=lambda s: s.key)
@pytest.mark.parametrize("project", [False, True])
def test_state_clipping_full_and_projected_three_surface_equality(
    row, spec, project, rest, tmp_path, capsys
):
    values = {**row["input"], "birth_time_uncertainty_minutes": 1}
    options = dict(
        as_of=row["analysis_at"], include_snapshot_text=True, response_char_limit=0
    )
    flags = [
        "--as-of",
        row["analysis_at"],
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
    assert not mcp.is_error and code == 0 and response.status_code == 200, response.text
    results = [mcp.structured_content, cli, response.json()]
    for result in results:
        assert business(result) == business(results[0])
        spec.output_model.model_validate(result)
        sensitivity = result["birth_time_sensitivity"]
        actual = {
            (r["status"], r["period"]) for r in sensitivity["current_dayun_candidates"]
        }
        assert set(map(tuple, row["source_witness_states"])) <= actual
        events = sensitivity["dayun_event_analysis"]
        expected_kind = row.get("expected_event_kind", "dayun_decade_leap_clip")
        assert any(e["kind"] == expected_kind for e in events["events"])
        assert events["physical_precision_certified"] is False
        if not project:
            assert (
                "未来回拨结束" if expected_kind.endswith("fold_end") else "十年闰日裁剪"
            ) in result["snapshot_text"]
            assert (
                "计算覆盖期数不是寿命估计" in result["snapshot_export"]["export_text"]
            )
