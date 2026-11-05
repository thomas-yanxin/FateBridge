"""Epoch labels, selected winter instants and unresolved activation differ."""

import asyncio
import json

import pytest

from fatebridge.application.examples import suggested_fields
from fatebridge.core.output_chinese import Taiyi
from scripts.taiyi.audit_taiyi_origin_selection import (
    calculate,
    inputs,
    inspect,
    native_inputs,
    references,
)
from tests.evaluation.test_agentic_nested_outputs import (  # noqa: F401 - imported pytest fixture
    AS_OF,
    SPECS,
    business,
    call_cli,
    native,
    rest,
)

ROWS = references()


@pytest.fixture(autouse=True)
def pinned_native_data():
    with native_inputs():
        yield


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row["id"])
def test_original_declared_numeric_policy_and_new_selection_receipt(row):
    result = calculate(row)
    checked = inspect(result, row)
    assert checked["numeric_control_passed"], checked
    assert checked["fidelity_receipt_passed"], checked
    Taiyi.model_validate(result["taiyi"])
    lines = [
        line
        for line in result["snapshot_text"].splitlines()
        if line.startswith("冬至选元约定：")
    ]
    assert len(lines) == 1
    assert result["snapshot_export"]["export_text"].count(lines[0]) == 1
    assert checked["actual_origin_clock"] in lines[0]
    assert checked["selected_winter_utc"] in lines[0]
    assert "未裁定" in lines[0]


@pytest.mark.parametrize(
    "row", [r for r in ROWS if r["year"] == 2026], ids=lambda r: r["id"]
)
def test_solar_labels_keep_the_same_actual_selection_lineage_without_claiming_a_new_clock_oracle(
    row,
):
    result = calculate(row, solar=True)
    assert inspect(result, row, solar=True)["fidelity_receipt_passed"]


@pytest.mark.parametrize("tool", ["taiyi", "sanshiunited"])
@pytest.mark.parametrize("mode", ["year", "month", "hour"])
def test_unrelated_profiles_do_not_fabricate_winter_jiazi_selection(tool, mode):
    row = next(r for r in ROWS if r["year"] == 2026 and r["tool"] == tool)
    values = inputs(row)
    options = values if tool == "taiyi" else values["taiyi_options"]
    options["calculation_mode"] = mode
    options.pop("hour_profile", None)
    from scripts.taiyi.audit_taiyi_solar_guard import calculate as call

    result = call(tool, values)
    assert "winter_origin_selection" not in result["taiyi"]
    assert "冬至选元约定：" not in result["snapshot_text"]


TRANSPORT_ROWS = [
    r
    for r in ROWS
    if r["year"] == 503
    and (
        (r["side"] == "before" and r["zone"] == "UTC")
        or (r["side"] == "after" and r["zone"] == "+08:00")
    )
]


@pytest.mark.parametrize("row", TRANSPORT_ROWS, ids=lambda r: r["id"])
def test_selection_view_on_all_three_transports(
    row, rest, tmp_path, capsys  # noqa: F811 - pytest fixture
):
    tool = row["tool"]
    spec = SPECS[tool]
    values = inputs(row)
    fields = suggested_fields(spec, view="winter_origin_selection")
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    http = rest.post(
        spec.rest_path,
        json=values,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            ("as_of", AS_OF),
        ],
    )
    mcp = asyncio.run(native(spec, values, **opts))
    code, cli = call_cli(
        spec,
        values,
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
    assert http.status_code == 200, http.text
    assert not mcp.is_error, mcp.structured_content
    assert code == 0, cli
    outputs = [http.json(), mcp.structured_content, cli]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for result in outputs:
        selected = result["taiyi"]["winter_origin_selection"]
        assert selected["classical_activation_adjudicated"] is False
        assert selected["count_origin_date"] == row["expected_count_origin_date"]
        assert selected["count_origin_clock"] == row["expected_count_origin_clock"]


def test_reference_math_is_not_a_classical_activation_decision():
    from scripts.taiyi.audit_taiyi_origin_selection import CORPUS

    phase = json.loads((CORPUS / "phase-reference.json").read_text())
    assert phase["cases"] == 120
    assert phase["origin_step_distribution"] == {"360": 109, "420": 11}
    assert all(
        r["hour_common720_phase_delta"] == 0 and not r["full_counters_identical"]
        for r in phase["rows"]
    )
    assert phase["independent_physical_or_classical_cases"] == 0
