"""Opaque-box E2E tests for M3 (`run_batch`), M6 (Clock, Timezone & Place), and Tier 4 workflows."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

from tests.e2e.conftest import (
    AUGMENTED_TOOL_INPUTS,
    assert_isomorphic_subset,
    call_cli,
    call_cli_tool,
    call_mcp_tool,
    call_python_run,
    call_rest,
    extract_error_issues,
    find_bloat_keys,
    rest_path_for,
    strip_run_metadata,
)

DEFAULT_PAYLOAD_BUDGET_BYTES = 10_240

ALICE_SUBJECT: dict[str, Any] = {
    "name": "Alice",
    "gender": "female",
    "birth_year": 1990,
    "birth_month": 5,
    "birth_day": 15,
    "birth_hour": 11,
    "birth_minute": 5,
    "birth_place": "乌鲁木齐",
    "birth_longitude": 87.6168,
    "birth_latitude": 43.8256,
    "timezone": "Asia/Shanghai",
    "use_true_solar_time": True,
}

BOB_SUBJECT: dict[str, Any] = {
    "name": "Bob",
    "gender": "male",
    "birth_year": 1992,
    "birth_month": 3,
    "birth_day": 2,
    "birth_hour": 8,
    "birth_minute": 18,
    "birth_place": "北京",
    "birth_longitude": 116.4074,
    "birth_latitude": 39.9042,
    "timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
}

CONSULTATION_CONTEXT: dict[str, Any] = {
    "year": 2027,
    "month": 10,
    "day": 12,
    "hour": 4,
    "minute": 0,
    "place": "北京",
    "longitude": 116.4074,
    "latitude": 39.9042,
    "timezone": "Asia/Shanghai",
    "use_true_solar_time": False,
}


def _call_cli_batch(batch_payload: dict[str, Any]) -> Any:
    return call_cli(
        ["batch", "--request-file", "-"],
        stdin_text=json.dumps(batch_payload, ensure_ascii=False),
    )


# ---------------------------------------------------------------------------
# M3: `run_batch` 4-Level Precedence, Subject Mapping & Boundaries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_four_level_precedence_across_surfaces(
    mcp_client: Client,
    rest_client: TestClient,
    e2e_as_of: str,
) -> None:
    """Verify precedence `defaults < context < subject(s) < call.arguments` across surfaces."""
    import fatebridge

    batch_payload: dict[str, Any] = {
        "subjects": {"alice": ALICE_SUBJECT},
        "context": CONSULTATION_CONTEXT,
        "defaults": {
            "analysis_year": 2026,
            "use_true_solar_time": False,
            "zi_hour_policy": "day_rollover_at_23",
        },
        "as_of": e2e_as_of,
        "calls": [
            {"id": "ctx_beats_def", "tool": "bazi_yearly_timing", "subject": "alice"},
            {"id": "subj_beats_ctx", "tool": "bazi_birth_chart", "subject": "alice"},
            {
                "id": "args_beat_ctx",
                "tool": "bazi_yearly_timing",
                "subject": "alice",
                "arguments": {"analysis_year": 2028},
            },
            {
                "id": "args_beat_subj",
                "tool": "bazi_birth_chart",
                "subject": "alice",
                "arguments": {"use_true_solar_time": False},
            },
        ],
    }

    mcp_out = await call_mcp_tool(mcp_client, "run_batch", batch_payload)
    rest_out = call_rest(rest_client, "POST", "/api/batch", json_body=batch_payload)
    cli_out = _call_cli_batch(batch_payload)

    for out in (mcp_out, rest_out, cli_out):
        assert out.ok, out.payload
        assert out.payload["status"] == "ok"
        assert out.payload["succeeded"] == 4
        assert out.payload["as_of"] == e2e_as_of

    mcp_by_id = {item["id"]: item["result"] for item in mcp_out.payload["results"]}
    rest_by_id = {item["id"]: item["result"] for item in rest_out.payload["results"]}
    cli_by_id = {item["id"]: item["result"] for item in cli_out.payload["results"]}

    for cid in ("ctx_beats_def", "subj_beats_ctx", "args_beat_ctx", "args_beat_subj"):
        assert strip_run_metadata(mcp_by_id[cid]) == strip_run_metadata(rest_by_id[cid])
        assert strip_run_metadata(mcp_by_id[cid]) == strip_run_metadata(cli_by_id[cid])

    assert mcp_by_id["ctx_beats_def"]["liunian"]["year"] == 2027
    assert mcp_by_id["args_beat_ctx"]["liunian"]["year"] == 2028
    assert mcp_by_id["subj_beats_ctx"]["bazi_birth"]["four_pillars"]["hour"] == {
        "stem": "庚",
        "branch": "辰",
    }
    assert mcp_by_id["args_beat_subj"]["bazi_birth"]["four_pillars"]["hour"] == {
        "stem": "壬",
        "branch": "午",
    }

    py_batch = fatebridge.batch(
        batch_payload["calls"],
        subjects=batch_payload["subjects"],
        context=batch_payload["context"],
        defaults=batch_payload["defaults"],
        as_of=batch_payload["as_of"],
    )
    assert py_batch["status"] == "ok"
    assert py_batch["succeeded"] == 4
    py_by_id = {item["id"]: item["result"] for item in py_batch["results"]}
    for cid in ("ctx_beats_def", "subj_beats_ctx", "args_beat_ctx", "args_beat_subj"):
        assert strip_run_metadata(py_by_id[cid]) == strip_run_metadata(mcp_by_id[cid])


@pytest.mark.asyncio
async def test_batch_multi_subject_compatibility_and_fengshui_occupants(
    mcp_client: Client,
    rest_client: TestClient,
    e2e_as_of: str,
) -> None:
    batch_payload: dict[str, Any] = {
        "subjects": {"alice": ALICE_SUBJECT, "bob": BOB_SUBJECT},
        "defaults": {
            "house_system": "P",
            "zodiac_type": "Tropic",
            "relationship_type": "marriage",
            "relative_mode": "Composite",
        },
        "as_of": e2e_as_of,
        "calls": [
            {
                "id": "bazi_pair",
                "tool": "bazi_compatibility",
                "subjects": ["alice", "bob"],
            },
            {
                "id": "sukuyo_pair",
                "tool": "sukuyo_compatibility",
                "subjects": ["alice", "bob"],
            },
            {
                "id": "astro_pair",
                "tool": "relationship_chart",
                "subjects": ["alice", "bob"],
            },
            {
                "id": "bazhai",
                "tool": "fengshui_bazhai",
                "subjects": ["alice", "bob"],
                "arguments": {"house": {"sitting_trigram": "坎"}},
            },
            {
                "id": "assess",
                "tool": "fengshui_assess",
                "subjects": ["alice", "bob"],
                "arguments": {"house": {"sitting_trigram": "坎"}},
                "include": ["*"],
            },
        ],
    }

    mcp_out = await call_mcp_tool(mcp_client, "run_batch", batch_payload)
    rest_out = call_rest(rest_client, "POST", "/api/batch", json_body=batch_payload)
    cli_out = _call_cli_batch(batch_payload)

    for out in (mcp_out, rest_out, cli_out):
        assert out.ok, out.payload
        assert out.payload["status"] == "ok"
        assert out.payload["succeeded"] == 5

    by_id = {item["id"]: item["result"] for item in rest_out.payload["results"]}
    assert "cross_chart_relations" in by_id["bazi_pair"]
    assert by_id["sukuyo_pair"]["person1"]["name"] == "Alice"
    assert by_id["sukuyo_pair"]["person2"]["name"] == "Bob"
    assert (
        by_id["astro_pair"]["relationship_profile"]["relative_mode_normalized"]
        == "composite"
    )
    assert "bazhai" in by_id["bazhai"]["layers"]
    assert "layers" in by_id["assess"]
    assert strip_run_metadata(
        mcp_out.payload["results"][0]["result"]
    ) == strip_run_metadata(by_id["bazi_pair"])
    assert strip_run_metadata(
        cli_out.payload["results"][0]["result"]
    ) == strip_run_metadata(by_id["bazi_pair"])


@pytest.mark.asyncio
async def test_batch_invalid_subject_mappings_and_unknown_subject(
    mcp_client: Client,
    rest_client: TestClient,
    e2e_as_of: str,
) -> None:
    subjects = {
        "alice": ALICE_SUBJECT,
        "bob": BOB_SUBJECT,
        "carol": {**BOB_SUBJECT, "name": "Carol"},
    }
    bad_mappings = [
        (
            "pair_1",
            {"id": "c1", "tool": "bazi_compatibility", "subjects": ["alice"]},
            "invalid_subject_count",
        ),
        (
            "pair_3",
            {
                "id": "c1",
                "tool": "bazi_compatibility",
                "subjects": ["alice", "bob", "carol"],
            },
            "invalid_subject_count",
        ),
        (
            "pair_single",
            {"id": "c1", "tool": "relationship_chart", "subject": "alice"},
            "pair_subjects_required",
        ),
        (
            "nonpair_multi",
            {"id": "c1", "tool": "bazi_birth_chart", "subjects": ["alice", "bob"]},
            "unsupported_subjects",
        ),
    ]
    for case_id, call_spec, expected_code in bad_mappings:
        payload = {"subjects": subjects, "as_of": e2e_as_of, "calls": [call_spec]}
        rest_out = call_rest(rest_client, "POST", "/api/batch", json_body=payload)
        mcp_out = await call_mcp_tool(mcp_client, "run_batch", payload)
        for out in (rest_out, mcp_out):
            assert out.ok, f"{case_id} outer call failed: {out.payload}"
            assert out.payload["status"] == "error"
            assert out.payload["succeeded"] == 0 and out.payload["failed"] == 1
            err = out.payload["results"][0]["error"]
            assert err["status_code"] == 422
            issues = extract_error_issues(err)
            assert issues and issues[0]["code"] == expected_code

    # Upfront unknown_subject 422
    unknown_payload = {
        "subjects": {"alice": ALICE_SUBJECT},
        "as_of": e2e_as_of,
        "calls": [{"id": "c1", "tool": "bazi_birth_chart", "subject": "missing"}],
    }
    mcp_unk = await call_mcp_tool(mcp_client, "run_batch", unknown_payload)
    rest_unk = call_rest(rest_client, "POST", "/api/batch", json_body=unknown_payload)
    cli_unk = _call_cli_batch(unknown_payload)
    assert not mcp_unk.ok and mcp_unk.status_code == 422
    assert not rest_unk.ok and rest_unk.status_code == 422
    assert not cli_unk.ok and cli_unk.exit_code == 1
    for out in (mcp_unk, rest_unk, cli_unk):
        issues = extract_error_issues(out.payload)
        assert issues and issues[0]["code"] == "unknown_subject"
        assert issues[0].get("constraints") == {"available": ["alice"]}


@pytest.mark.asyncio
async def test_batch_per_call_delivery_partial_error_and_stop_on_error(
    mcp_client: Client,
    rest_client: TestClient,
    e2e_as_of: str,
) -> None:
    mixed_payload: dict[str, Any] = {
        "subjects": {"alice": ALICE_SUBJECT},
        "context": CONSULTATION_CONTEXT,
        "as_of": e2e_as_of,
        "calls": [
            {"id": "ok_def", "tool": "bazi_birth_chart", "subject": "alice"},
            {
                "id": "ok_star",
                "tool": "bazi_birth_chart",
                "subject": "alice",
                "include": ["*"],
            },
            {
                "id": "ok_fld",
                "tool": "bazi_birth_chart",
                "subject": "alice",
                "fields": ["bazi_birth.day_master"],
            },
            {
                "id": "bad_inc",
                "tool": "bazi_birth_chart",
                "subject": "alice",
                "include": ["calendar_basi"],
            },
        ],
    }
    mcp_mix = await call_mcp_tool(mcp_client, "run_batch", mixed_payload)
    rest_mix = call_rest(rest_client, "POST", "/api/batch", json_body=mixed_payload)
    cli_mix = _call_cli_batch(mixed_payload)
    for out in (mcp_mix, rest_mix, cli_mix):
        assert out.ok and out.payload["status"] == "partial_error"
        assert out.payload["succeeded"] == 3 and out.payload["failed"] == 1
        by_id = {r["id"]: r for r in out.payload["results"]}
        assert_isomorphic_subset(by_id["ok_def"]["result"], by_id["ok_star"]["result"])
        assert set(strip_run_metadata(by_id["ok_fld"]["result"])) == {"bazi_birth"}
        assert set(by_id["ok_fld"]["result"]["bazi_birth"]) == {"day_master"}
        bad_issues = extract_error_issues(by_id["bad_inc"]["error"])
        assert bad_issues and bad_issues[0]["code"] == "unknown_projection_path"
        assert "calendar_basis" in (
            bad_issues[0]["constraints"].get("suggestions") or []
        )

    # stop_on_error halts before skipped call (2nd-call fail -> partial_error; 1st-call fail -> error across surfaces)
    import fatebridge

    stop_payload = {
        "subjects": {"alice": ALICE_SUBJECT},
        "as_of": e2e_as_of,
        "stop_on_error": True,
        "calls": [
            {"id": "c1", "tool": "bazi_birth_chart", "subject": "alice"},
            {
                "id": "c2_bad",
                "tool": "bazi_birth_chart",
                "subject": "alice",
                "include": ["nonexistent_view"],
            },
            {"id": "c3_skip", "tool": "fengshui_minggua", "subject": "alice"},
        ],
    }
    stop_out = call_rest(rest_client, "POST", "/api/batch", json_body=stop_payload)
    assert stop_out.ok and stop_out.payload["status"] == "partial_error"
    assert [r["id"] for r in stop_out.payload["results"]] == ["c1", "c2_bad"]

    stop_first_payload = {
        "subjects": {"alice": ALICE_SUBJECT},
        "as_of": e2e_as_of,
        "stop_on_error": True,
        "calls": [
            {
                "id": "c1_bad",
                "tool": "bazi_birth_chart",
                "subject": "alice",
                "include": ["nonexistent_view"],
            },
            {"id": "c2_skip", "tool": "fengshui_minggua", "subject": "alice"},
        ],
    }
    rest_first = call_rest(
        rest_client, "POST", "/api/batch", json_body=stop_first_payload
    )
    mcp_first = await call_mcp_tool(mcp_client, "run_batch", stop_first_payload)
    cli_first = _call_cli_batch(stop_first_payload)
    py_first = fatebridge.batch(
        stop_first_payload["calls"],
        subjects=stop_first_payload["subjects"],
        as_of=e2e_as_of,
        stop_on_error=True,
    )
    for out_payload in (
        rest_first.payload,
        mcp_first.payload,
        cli_first.payload,
        py_first,
    ):
        assert out_payload["status"] == "error"
        assert out_payload["succeeded"] == 0 and out_payload["failed"] == 1
        assert [r["id"] for r in out_payload["results"]] == ["c1_bad"]


@pytest.mark.asyncio
async def test_batch_max_calls_boundary_32_pass_vs_33_fail_422(
    mcp_client: Client,
    rest_client: TestClient,
    e2e_as_of: str,
) -> None:
    import fatebridge

    calls_32 = [
        {"id": f"c{i}", "tool": "gua_lookup", "arguments": {"queries": ["乾"]}}
        for i in range(32)
    ]
    calls_33 = calls_32 + [
        {"id": "c32", "tool": "gua_lookup", "arguments": {"queries": ["乾"]}}
    ]

    ok_payload = {"calls": calls_32, "as_of": e2e_as_of}
    err_payload = {"calls": calls_33, "as_of": e2e_as_of}
    empty_payload = {"calls": [], "as_of": e2e_as_of}

    for surface_out in (
        call_rest(rest_client, "POST", "/api/batch", json_body=ok_payload),
        await call_mcp_tool(mcp_client, "run_batch", ok_payload),
        _call_cli_batch(ok_payload),
    ):
        assert surface_out.ok and surface_out.payload["status"] == "ok"
        assert surface_out.payload["succeeded"] == 32

    py_ok = fatebridge.batch(calls_32, as_of=e2e_as_of)
    assert py_ok["status"] == "ok" and py_ok["succeeded"] == 32

    for bad_payload in (empty_payload, err_payload):
        py_err = fatebridge.batch(bad_payload["calls"], as_of=e2e_as_of)
        assert py_err.get("status_code") == 422
        assert py_err.get("error_code") == "validation_error"
        py_issues = extract_error_issues(py_err)
        assert py_issues and py_issues[0]["path"] == "calls"

        for err_out in (
            call_rest(rest_client, "POST", "/api/batch", json_body=bad_payload),
            await call_mcp_tool(mcp_client, "run_batch", bad_payload),
            _call_cli_batch(bad_payload),
        ):
            assert not err_out.ok
            assert err_out.status_code == 422
            assert err_out.payload.get("error_code") == "validation_error"
            issues = extract_error_issues(err_out.payload)
            assert issues and issues[0]["path"] == "calls"


@pytest.mark.asyncio
async def test_batch_unseeded_liuyao_seed_isolation(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    liuyao_base = {
        k: v
        for k, v in all_tool_specs["liuyao"]["example_input"].items()
        if k not in ("seed", "coins", "lines", "gua_code")
    }
    liuyao_base["method"] = "coin"
    payload = {
        "as_of": e2e_as_of,
        "calls": [
            {"id": "coin_1", "tool": "liuyao", "arguments": liuyao_base},
            {"id": "coin_2", "tool": "liuyao", "arguments": liuyao_base},
        ],
    }
    for out in (
        await call_mcp_tool(mcp_client, "run_batch", payload),
        call_rest(rest_client, "POST", "/api/batch", json_body=payload),
    ):
        assert out.ok and out.payload["succeeded"] == 2
        s1 = out.payload["results"][0]["result"]["run_metadata"]["replay"]["overrides"][
            "seed"
        ]
        s2 = out.payload["results"][1]["result"]["run_metadata"]["replay"]["overrides"][
            "seed"
        ]
        assert isinstance(s1, int) and isinstance(s2, int) and s1 != s2


@pytest.mark.asyncio
async def test_tier4_multi_tradition_batch_consultation_workflow(
    mcp_client: Client,
    e2e_as_of: str,
) -> None:
    """Tier 4: Realistic multi-tradition batch consultation under frozen clock."""
    batch_payload: dict[str, Any] = {
        "subjects": {"native": ALICE_SUBJECT, "partner": BOB_SUBJECT},
        "context": CONSULTATION_CONTEXT,
        "defaults": {
            "zi_hour_policy": "day_rollover_at_23",
            "house_system": "P",
            "zodiac_type": "Tropic",
            "relationship_type": "marriage",
        },
        "as_of": e2e_as_of,
        "calls": [
            {"id": "bazi_natal", "tool": "bazi_birth_chart", "subject": "native"},
            {
                "id": "bazi_timing",
                "tool": "bazi_timing",
                "subject": "native",
                "fields": ["dayun", "liunian", "summary"],
            },
            {"id": "ziwei", "tool": "ziwei_birth_chart", "subject": "native"},
            {
                "id": "astro",
                "tool": "astrology_chart",
                "subject": "native",
                "arguments": {"max_aspects": 10},
            },
            {
                "id": "pair",
                "tool": "bazi_compatibility",
                "subjects": ["native", "partner"],
            },
            {"id": "minggua", "tool": "fengshui_minggua", "subject": "native"},
            {
                "id": "fengshui",
                "tool": "fengshui_assess",
                "subjects": ["native", "partner"],
                "arguments": {"house": {"sitting_trigram": "坎"}},
            },
            {
                "id": "ipip",
                "tool": "ipip_big_five",
                "arguments": AUGMENTED_TOOL_INPUTS["ipip_big_five"],
            },
            {
                "id": "ref",
                "tool": "knowledge_read",
                "arguments": AUGMENTED_TOOL_INPUTS["knowledge_read"],
                "include": ["human_design_line_reference"],
            },
        ],
    }

    out = await call_mcp_tool(mcp_client, "run_batch", batch_payload)
    assert out.ok, out.payload
    assert out.payload["status"] == "ok"
    assert out.payload["succeeded"] == 9
    for item in out.payload["results"]:
        res = item["result"]
        assert find_bloat_keys(res) == []
        assert res["run_metadata"]["replay"]["as_of"] == e2e_as_of
        if item["id"] != "ref":
            assert (
                len(json.dumps(res, ensure_ascii=False).encode("utf-8"))
                <= DEFAULT_PAYLOAD_BUDGET_BYTES
            )


# ---------------------------------------------------------------------------
# M6: Frozen Clock (`as_of`), DST/Fold, Timezone & Place Resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frozen_as_of_dst_fold_cross_surface_parity(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    tool_name = "bazi_birth_chart"
    rest_path = rest_path_for(tool_name, all_tool_specs)
    base_fold = {
        "gender": "male",
        "birth_year": 1980,
        "birth_month": 10,
        "birth_day": 26,
        "birth_hour": 1,
        "birth_minute": 30,
        "birth_timezone": "America/New_York",
        "birth_longitude": -74.0060,
    }
    edt_payload = {**base_fold, "birth_utc_offset": "-04:00"}
    est_payload = {**base_fold, "birth_utc_offset": "-05:00"}

    py_edt = call_python_run(tool_name, edt_payload, as_of=e2e_as_of, include=["*"])
    py_est = call_python_run(tool_name, est_payload, as_of=e2e_as_of, include=["*"])
    mcp_est = await call_mcp_tool(
        mcp_client,
        "run_calculation",
        {
            "tool": tool_name,
            "arguments": est_payload,
            "as_of": e2e_as_of,
            "include": ["*"],
        },
    )
    rest_est = call_rest(
        rest_client,
        "POST",
        rest_path,
        json_body=est_payload,
        params=[("as_of", e2e_as_of), ("include", "*")],
    )
    cli_est = call_cli_tool(tool_name, est_payload, as_of=e2e_as_of, include=["*"])

    for out in (py_edt, py_est, mcp_est, rest_est, cli_est):
        assert out.ok, out.payload
        assert out.payload["run_metadata"]["replay"]["as_of"] == e2e_as_of

    assert strip_run_metadata(py_edt.payload) != strip_run_metadata(py_est.payload)
    expected_est = strip_run_metadata(py_est.payload)
    for out in (mcp_est, rest_est, cli_est):
        assert strip_run_metadata(out.payload) == expected_est

    # Ambiguous DST birth without birth_utc_offset -> 400/422 across all 4 surfaces
    for out in (
        call_python_run(tool_name, base_fold, as_of=e2e_as_of),
        await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {"tool": tool_name, "arguments": base_fold, "as_of": e2e_as_of},
        ),
        call_rest(
            rest_client,
            "POST",
            rest_path,
            json_body=base_fold,
            params=[("as_of", e2e_as_of)],
        ),
        call_cli_tool(tool_name, base_fold, as_of=e2e_as_of),
    ):
        assert not out.ok
        assert out.status_code in {400, 422}
        assert out.payload.get("error_code") == "validation_error"
        assert "ambiguous" in out.payload.get("error", "").lower()


@pytest.mark.asyncio
async def test_omitted_analysis_time_emits_current_time_frozen_warning(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
) -> None:
    tool_name = "bazi_yearly_timing"
    rest_path = rest_path_for(tool_name, all_tool_specs)
    frozen_jan = "2027-01-15T12:00:00+08:00"
    payload = {
        "gender": "male",
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_minute": 30,
        "birth_timezone": "Asia/Shanghai",
        "year_boundary_policy": "lichun",
    }

    outcomes = [
        call_python_run(tool_name, payload, as_of=frozen_jan),
        await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {"tool": tool_name, "arguments": payload, "as_of": frozen_jan},
        ),
        call_rest(
            rest_client,
            "POST",
            rest_path,
            json_body=payload,
            params=[("as_of", frozen_jan)],
        ),
        call_cli_tool(tool_name, payload, as_of=frozen_jan),
    ]
    for out in outcomes:
        assert out.ok, out.payload
        assert "current_time_frozen" in (
            out.payload["run_metadata"].get("warnings") or []
        )
        assert out.payload["liunian"]["year"] == 2026


@pytest.mark.asyncio
async def test_unresolved_timezone_offset_and_missing_solar_longitude_errors(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    # 1. Antarctica/Vostok historical unresolved UT offset -> 422 unresolved_timezone_offset
    tz_args = {
        "date": "1994-06-01",
        "time": "12:34:56+00:00",
        "timezone": "Antarctica/Vostok",
        "gua_code": "111111",
    }
    tz_outcomes = [
        call_python_run("liuyao", tz_args, as_of=e2e_as_of),
        await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {"tool": "liuyao", "arguments": tz_args, "as_of": e2e_as_of},
        ),
        call_rest(
            rest_client,
            "POST",
            rest_path_for("liuyao", all_tool_specs),
            json_body=tz_args,
            params=[("as_of", e2e_as_of)],
        ),
        call_cli_tool("liuyao", tz_args, as_of=e2e_as_of),
    ]
    for out in tz_outcomes:
        assert not out.ok
        assert out.status_code == 422
        assert out.payload.get("error_code") == "validation_error"
        issues = extract_error_issues(out.payload)
        assert issues and issues[0]["code"] == "unresolved_timezone_offset"

    # 2. use_true_solar_time=True without longitude -> 400 longitude_required_for_solar_time
    solar_args = {
        "birth_year": 1990,
        "birth_month": 5,
        "birth_day": 15,
        "birth_hour": 10,
        "gender": "male",
        "birth_place": "未提供",
        "use_true_solar_time": True,
    }
    solar_outcomes = [
        call_python_run("bazi_birth_chart", solar_args, as_of=e2e_as_of),
        await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {"tool": "bazi_birth_chart", "arguments": solar_args, "as_of": e2e_as_of},
        ),
        call_rest(
            rest_client,
            "POST",
            rest_path_for("bazi_birth_chart", all_tool_specs),
            json_body=solar_args,
            params=[("as_of", e2e_as_of)],
        ),
        call_cli_tool("bazi_birth_chart", solar_args, as_of=e2e_as_of),
    ]
    for out in solar_outcomes:
        assert not out.ok
        assert out.status_code == 400
        assert out.payload.get("error_code") == "validation_error"
        issues = extract_error_issues(out.payload)
        assert issues and issues[0]["code"] == "longitude_required_for_solar_time"


@pytest.mark.asyncio
async def test_place_lookup_statuses_and_cross_surface_parity(
    mcp_client: Client,
    rest_client: TestClient,
    all_tool_specs: dict[str, dict[str, Any]],
    e2e_as_of: str,
) -> None:
    rest_path = rest_path_for("place_lookup", all_tool_specs)
    cases = [
        ("北京朝阳", "resolved"),
        ("朝阳", "ambiguous"),
        ("江苏省未收录地点", "resolved"),
        ("不存在的地名xyz", "not_found"),
    ]
    for query, expected_status in cases:
        args = {"query": query, "limit": 5}
        py_out = call_python_run("place_lookup", args, as_of=e2e_as_of)
        mcp_out = await call_mcp_tool(
            mcp_client,
            "run_calculation",
            {"tool": "place_lookup", "arguments": args, "as_of": e2e_as_of},
        )
        rest_out = call_rest(
            rest_client,
            "POST",
            rest_path,
            json_body=args,
            params=[("as_of", e2e_as_of)],
        )
        cli_out = call_cli_tool("place_lookup", args, as_of=e2e_as_of)

        for out in (py_out, mcp_out, rest_out, cli_out):
            assert out.ok, out.payload
            assert out.payload["status"] == expected_status
        expected_biz = strip_run_metadata(py_out.payload)
        for out in (mcp_out, rest_out, cli_out):
            assert strip_run_metadata(out.payload) == expected_biz
