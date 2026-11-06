"""Keep actual first-response facts while paging only their original receipt."""

import json
from copy import deepcopy

import pytest

from fatebridge.application import result_delivery
from fatebridge.application.examples import suggested_fields
from fatebridge.application.execution import execute_tool
from fatebridge.application.projection import project_fields
from fatebridge.application.result_delivery import ResultStore, bound_response
from fatebridge.core.response_models import RunMetadata
from fatebridge.services.tool_catalog import CATALOG
from tests.fixtures.mcp_result_delivery import assert_same_run_receipt

SPEC = next(spec for spec in CATALOG if spec.key == "sanshiunited")


@pytest.mark.parametrize("view", [None, "palace_correspondences"])
@pytest.mark.parametrize(
    "mode,profile",
    [
        ("year", None),
        ("month", None),
        ("month", "key_month_tianzheng_jie_v1"),
        ("day", None),
        ("hour", None),
        ("hour", "key_hour_winter_jiazi_v1"),
    ],
)
def test_current_twelve_payloads_keep_essential_receipts_and_exact_same_run(
    mode, profile, view, monkeypatch, tmp_path
):
    store = ResultStore(tmp_path / "delivery")
    monkeypatch.setattr(result_delivery, "RESULT_STORE", store)
    options = {"calculation_mode": mode}
    if profile is not None:
        options[mode + "_profile"] = profile
    request = SPEC.request_model.model_validate(
        {
            "date": "2026-04-04",
            "time": "12:00:00",
            "zone": "Asia/Shanghai",
            "use_true_solar_time": False,
            "taiyi_options": options,
        }
    )
    payload = project_fields(
        execute_tool(SPEC, request),
        suggested_fields(SPEC, view=view),
        strict_fields=True,
    )
    assert "error" not in payload
    untouched = deepcopy(payload)
    first = bound_response(payload, response_char_limit=8192)
    encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    assert len(encode(first)) <= 8192 and payload == untouched
    RunMetadata.model_validate(first["run_metadata"])
    ref = first["result_delivery"]
    assert "run_metadata" not in ref["deferred_fields"]
    full = store.get(ref["result_id"])
    assert full == untouched
    assert len(encode(full)) == ref["total_chars"]
    assert_same_run_receipt(
        first["run_metadata"],
        full["run_metadata"],
        deferred_fields=ref["deferred_fields"],
    )
    for key in (
        "run_id",
        "trace_id",
    ):
        assert first["run_metadata"][key] == full["run_metadata"][key]
    business_deferred = {
        p for p in ref["deferred_fields"] if not p.startswith("run_metadata.")
    }
    assert business_deferred == set(full) - set(first)
    for key in set(full) & set(first) - {"run_metadata"}:
        assert first[key] == full[key]
    if business_deferred:
        # Prove that the complete business cannot fit even after removing all
        # permitted supplementary receipt fields and duplicate locators.
        minimal_receipt = {
            k: v
            for k, v in first["run_metadata"].items()
            if k not in {"provenance", "determinism"}
        }
        minimal_reference = {k: ref[k] for k in ("result_id", "manifest_uri")}
        assert (
            len(
                encode(
                    {
                        **full,
                        "run_metadata": minimal_receipt,
                        "result_delivery": minimal_reference,
                    }
                )
            )
            > 8192
        )
