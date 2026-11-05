"""Selected birth instants reach every actual BaZi/timing public surface."""

import asyncio

import pytest

from tests.test_agentic_nested_outputs import (
    AS_OF,
    business,
    call_cli,
    inputs,
    native,
)
from tests.test_agentic_nested_outputs import rest as _shared_rest
from tests.test_bazi_birth_fold import SHANGHAI
from tests.test_bazi_birth_seconds import SPECS
from tests.test_bazi_birth_seconds_transports import leaf, receipt_path

rest = _shared_rest


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.key)
@pytest.mark.parametrize("project", [False, True])
@pytest.mark.parametrize(
    "offset,utc,fold",
    [
        ("+09:00", "1991-09-14T16:30:00+00:00", 0),
        ("+08:00", "1991-09-14T17:30:00+00:00", 1),
    ],
)
def test_both_fold_occurrences_and_evidence_on_all_surfaces(
    spec, project, offset, utc, fold, rest, tmp_path, capsys
):
    payload = {**inputs(spec), **SHANGHAI, "birth_utc_offset": offset}
    opts = dict(include_snapshot_text=True, response_char_limit=0)
    flags = ["--include-snapshot-text", "true", "--response-char-limit", "0"]
    if project:
        opts.update(fields=[receipt_path(spec)], strict_fields=True)
        flags += ["--fields", receipt_path(spec), "--strict-fields", "true"]
    mcp = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(spec, payload, tmp_path, capsys, flags=flags)
    assert not mcp.is_error and code == 0
    observed = [mcp.structured_content, cli]
    if spec.rest_path is not None:
        http = rest.post(spec.rest_path, json=payload, params={"as_of": AS_OF, **opts})
        assert http.status_code == 200, http.text
        observed.append(http.json())
    else:
        assert spec.key == "analyze_destiny"
    for data in observed:
        assert business(data) == business(observed[0])
        receipt = leaf(data, receipt_path(spec))
        assert receipt["civil_instant_utc"] == utc
        assert receipt["requested_utc_offset"] == receipt["civil_utc_offset"] == offset
        assert receipt["civil_fold"] == fold and receipt["civil_time_ambiguous"] is True
        assert receipt["timezone"] == "Asia/Shanghai"
        assert receipt["observed_precision_certified"] is False
        assert receipt["timezone_rules"]["database"]
        spec.output_model.model_validate(data)
        if not project and data.get("snapshot_text"):
            assert (
                utc in data["snapshot_text"]
                and "不认证出生记录" in data["snapshot_text"]
            )


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.key)
@pytest.mark.parametrize("case", ["wrong_offset", "unknown_fold", "gap"])
def test_invalid_clock_creates_no_complete_report(spec, case, rest, tmp_path, capsys):
    payload = {**inputs(spec), **SHANGHAI}
    if case == "wrong_offset":
        payload["birth_utc_offset"] = "+07:00"
    elif case == "gap":
        payload.update(
            birth_month=4, birth_day=14, birth_hour=2, birth_utc_offset="+08:00"
        )
    mcp = asyncio.run(native(spec, payload))
    code, cli = call_cli(spec, payload, tmp_path, capsys)
    assert mcp.is_error and code != 0
    assert "birth_time_input" not in cli and "bazi_birth" not in cli
    if spec.rest_path is not None:
        http = rest.post(spec.rest_path, json=payload)
        assert http.status_code == 400, http.text


def test_input_identity_distinguishes_actual_instants_and_replays_same_selection(rest):
    spec = next(s for s in SPECS if s.key == "bazi_birth")
    outputs = []
    for offset in ["+09:00", "+08:00", "+09:00"]:
        response = rest.post(
            spec.rest_path,
            json={**SHANGHAI, "birth_utc_offset": offset},
            params={"as_of": AS_OF, "response_char_limit": 0},
        )
        assert response.status_code == 200, response.text
        outputs.append(response.json())
    assert (
        outputs[0]["run_metadata"]["input_sha256"]
        != outputs[1]["run_metadata"]["input_sha256"]
    )
    assert (
        outputs[0]["run_metadata"]["input_sha256"]
        == outputs[2]["run_metadata"]["input_sha256"]
    )
    assert business(outputs[0]) == business(outputs[2])
    assert outputs[0]["run_metadata"]["run_id"] != outputs[2]["run_metadata"]["run_id"]
