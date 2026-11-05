"""All retained event witnesses share one full/projected three-surface check."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.core.timing import TimingAnalysis
from tests.bazi.test_bazi_dayun_carries import SELECTED as CARRIES
from tests.bazi.test_bazi_dayun_future_gaps import INITIAL, LATER
from tests.bazi.test_bazi_dayun_state_clipping import SELECTED as CLIPPING
from tests.support.transports import SPECS, business
from tests.support.transports import rest as rest
from tests.support.transports import surface_calls

BOUNDARY = json.loads(
    (
        Path(__file__).parents[1] / "data/bazi/dayun-boundary-clock-input.json"
    ).read_text()
)
CASES = [
    ("carry", CARRIES[0]),
    *[("future_gap", row) for row in [INITIAL[0], *LATER]],
    *[("clipping", row) for row in [CLIPPING[0], CLIPPING[10]]],
    ("boundary", BOUNDARY),
]


@pytest.mark.parametrize(
    "kind,row", CASES, ids=[f"{k}-{r.get('id', 'boundary')}" for k, r in CASES]
)
@pytest.mark.parametrize("tool", ["timing_analysis", "dayun_analysis"])
@pytest.mark.parametrize("project", [False, True])
def test_event_witnesses_on_full_and_published_three_surfaces(
    kind, row, tool, project, surface_calls
):
    spec = SPECS[tool]
    analysis = (
        row["contexts"][1]["analysis_at"] if kind == "boundary" else row["analysis_at"]
    )
    values = {**row["input"], "birth_time_uncertainty_minutes": 1}
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
    http, protocol, code, cli = surface_calls(
        spec, values, params=options, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0, http.text
    results = [http.json(), protocol.structured_content, cli]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        spec.output_model.model_validate(result)
    result = results[0]
    sensitivity = result["birth_time_sensitivity"]
    event = sensitivity["dayun_event_analysis"]
    assert event["physical_precision_certified"] is False
    actual = {
        (p["status"], p["period"]) for p in sensitivity["current_dayun_candidates"]
    }
    if kind in {"carry", "future_gap"}:
        if "expected_current_candidates" in row:
            assert sorted(actual) == [
                tuple(p) for p in row["expected_current_candidates"]
            ]
        else:
            assert sorted({p[0] for p in actual}) == row["expected_statuses"]
        assert (
            sensitivity["sample_count"]
            == sum(p["sample_count"] for p in sensitivity["pillars_candidates"])
            == 3
        )
        assert event["continuous_completeness_certified"] is False
        if kind == "carry":
            assert (
                event["events"]
                and event["probe_count"] == sensitivity["dayun_event_probe_count"] > 0
            )
            assert (
                "dayun_event_probe"
                in sensitivity["pillars_candidates"][0]["evidence_sources"]
            )
            if not project:
                assert "大运历法事件探针" in result["snapshot_text"]
                assert (
                    "尚未起运、相邻期数等全部状态"
                    in result["snapshot_export"]["export_text"]
                )
        else:
            assert any(
                e["kind"] == "dayun_future_civil_gap_end" for e in event["events"]
            )
            assert event["future_clock_scan"]["forward_gap_count"] == 1
            if not project:
                assert "未来跳时" in result["snapshot_text"]
                assert (
                    "计算覆盖期数不是寿命估计"
                    in result["snapshot_export"]["export_text"]
                )
                for state, text in [
                    ("before_dayun", "尚未起运"),
                    ("beyond_calculation", "超出已配置期数"),
                ]:
                    if any(p[0] == state for p in actual):
                        assert text in result["snapshot_text"]
    elif kind == "clipping":
        assert set(map(tuple, row["source_witness_states"])) <= actual
        expected_kind = row.get("expected_event_kind", "dayun_decade_leap_clip")
        assert any(e["kind"] == expected_kind for e in event["events"])
        if not project:
            assert (
                "未来回拨结束" if expected_kind.endswith("fold_end") else "十年闰日裁剪"
            ) in result["snapshot_text"]
            assert (
                "计算覆盖期数不是寿命估计" in result["snapshot_export"]["export_text"]
            )
    else:
        assert event["method_id"] == "dayun_all_boundary_gap_and_analysis_probes_v4"
        assert event["boundary_clock_scan"]["boundary_count"] == 13
        assert any(
            e["source"].get("scan_basis")
            == "projected_boundary_wall_image_independent_of_analysis_context"
            for e in event["events"]
        )
        period = sensitivity["dayun_boundary_ranges"][0]
        low, high = [
            datetime.fromisoformat(period[k]).astimezone(timezone.utc)
            for k in ("earliest_start_at", "latest_start_at")
        ]
        for probe in row["probes"]:
            if probe["safe"]:
                timeline = TimingAnalysis.calculate_dayun_timeline(
                    datetime.fromisoformat(probe["birth_utc"]),
                    row["input"]["gender"],
                    ("甲", "子"),
                    row["zone"],
                )
                assert (
                    low
                    <= datetime.fromisoformat(timeline["start_at"]).astimezone(
                        timezone.utc
                    )
                    <= high
                )
