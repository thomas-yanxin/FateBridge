"""Source-specific cases share one public full/card transport contract.

Independent meanings, source failures and numerical expectations remain in
coordinate_context, root_bodies, circuit_topology, primary_diagrams and
profile_partition; this suite checks that their complete facts survive delivery.
"""

import json
from pathlib import Path

import pytest

from fatebridge.application.examples import evidence_views
from fatebridge.validation.human_design import verify_human_design_reading
from tests.support.transports import SPECS, business
from tests.support.transports import rest as rest
from tests.support.transports import surface_calls

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures"
ROOT_PLAN = json.loads((FIXTURES / "human-design-root-body-plan.json").read_text())
CROSSES = json.loads((FIXTURES / "human-design-official-cross-charts.json").read_text())
CASES = [
    (
        "coordinate",
        "apparent_positions",
        dict(
            birth_year=2236,
            birth_month=3,
            birth_day=1,
            birth_hour=12,
            birth_minute=0,
            birth_timezone="UTC",
        ),
    ),
    (
        "topology",
        "topology",
        dict(
            birth_year=1990,
            birth_month=4,
            birth_day=6,
            birth_hour=9,
            birth_minute=33,
            birth_timezone="Asia/Shanghai",
        ),
    ),
    *[
        (
            f"root-{i}-{mode}",
            "root_endpoints",
            {**ROOT_PLAN["cases"][i]["input"], "node_mode": mode},
        )
        for i in (0, 2, 3)
        for mode in ("true", "mean")
    ],
    *[
        (
            f"diagram-{case['id']}-{mode}",
            "primary_diagrams",
            {**case["birth_input"], "node_mode": mode},
        )
        for case in CROSSES["cases"]
        if case["id"] in {"cross-left-09", "cross-left-16", "cross-right-16"}
        for mode in ("true", "mean")
    ],
    *[
        (
            f"partition-{mode}",
            "profile_partition",
            dict(
                birth_year=1981,
                birth_month=5,
                birth_day=6,
                birth_hour=16,
                birth_minute=22,
                birth_timezone="Europe/London",
                node_mode=mode,
            ),
        )
        for mode in ("true", "mean")
    ],
]


@pytest.mark.parametrize("case_id,view,payload", CASES, ids=[c[0] for c in CASES])
@pytest.mark.parametrize("empty_files", [False, True])
def test_full_source_facts_and_published_card_on_three_surfaces(
    case_id, view, payload, empty_files, surface_calls, monkeypatch, tmp_path
):
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path if empty_files else ROOT / "ephe"))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    spec = SPECS["human_design"]
    options = {"response_char_limit": 0}
    http, protocol, code, cli = surface_calls(
        spec,
        payload,
        params=options,
        options=options,
        flags=["--response-char-limit", "0"],
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0, http.text
    results = [http.json(), protocol.structured_content, cli]
    assert business(results[0]) == business(results[1]) == business(results[2])
    complete = results[0]
    assert (
        verify_human_design_reading(complete)["status"]
        == "verified_fixed_template_reading"
    )
    fields = evidence_views(spec)[view]["fields"]
    options.update(fields=fields, strict_fields=True, include_snapshot_text=False)
    http, protocol, code, cli = surface_calls(spec, payload, projection=options)
    assert http.status_code == 200 and not protocol.is_error and code == 0, http.text
    results = [http.json(), protocol.structured_content, cli]
    assert business(results[0]) == business(results[1]) == business(results[2])
    for result in results:
        spec.output_model.model_validate(result)
    for field in fields:
        expected, actual = complete, results[0]
        for key in field.split("."):
            expected, actual = expected[key], actual[key]
        assert actual == expected, (case_id, field)
