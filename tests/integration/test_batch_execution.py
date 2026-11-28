"""Integration tests for stateless batch / multi-subject / multi-tool execution."""

from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge import cli
from fatebridge.application.batch import (
    BatchCall,
    BatchRequest,
    SubjectProfile,
    execute_batch,
    resolve_call_arguments,
)
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.errors import ParameterError
from tests.support.transports import cached_mcp_app

SPECS = {spec.name: spec for spec in CATALOG}

ALICE_PROFILE = {
    "name": "Alice",
    "gender": "female",
    "birth_date": "1990-05-15",
    "birth_time": "10:30:00",
    "birth_place": "上海",
    "birth_longitude": 121.4737,
    "birth_latitude": 31.2304,
    "timezone": "Asia/Shanghai",
    "use_true_solar_time": True,
}

BOB_PROFILE = {
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


def _strip_run_metadata(batch_payload: dict[str, object]) -> dict[str, object]:
    normalized = {**batch_payload, "results": []}
    for entry in batch_payload["results"]:
        assert isinstance(entry, dict)
        cleaned = dict(entry)
        if cleaned.get("ok") and isinstance(cleaned.get("result"), dict):
            cleaned["result"] = {
                k: v for k, v in cleaned["result"].items() if k != "run_metadata"
            }
        normalized["results"].append(cleaned)
    return normalized


def test_subject_profile_auto_parses_birth_date_and_time() -> None:
    profile = SubjectProfile.model_validate(
        {
            "name": "Demo",
            "gender": "female",
            "birth_date": "1990-05-15",
            "birth_time": "10:30:45",
        }
    )
    assert (profile.birth_year, profile.birth_month, profile.birth_day) == (1990, 5, 15)
    assert (profile.birth_hour, profile.birth_minute, profile.birth_second) == (
        10,
        30,
        45,
    )

    with pytest.raises(ValidationError):
        SubjectProfile.model_validate({"birth_date": "1990-02-30"})
    with pytest.raises(ValidationError):
        SubjectProfile.model_validate({"birth_time": "25:00"})
    with pytest.raises(ValidationError):
        SubjectProfile.model_validate({"unknown_key": 1})


def test_resolve_call_arguments_precedence_and_dynamic_mapping() -> None:
    subjects = {
        "alice": SubjectProfile.model_validate(
            {**ALICE_PROFILE, "use_true_solar_time": True}
        ),
        "bob": SubjectProfile.model_validate(BOB_PROFILE),
    }
    defaults: dict[str, object] = {
        "house_system": "P",
        "zodiac_type": "Tropic",
        "zi_hour_policy": "night_zi_same_day_next_hour_stem",
        "use_true_solar_time": False,
        "analysis_year": 2026,
    }

    bazi_args = resolve_call_arguments(
        SPECS["bazi_birth_chart"],
        BatchCall(
            tool="bazi_birth_chart",
            subject="alice",
            arguments={"analysis_year": 2028, "use_true_solar_time": False},
        ),
        subjects=subjects,
        defaults=defaults,
    )
    # Filtered defaults omit western-only keys like house_system/zodiac_type
    assert "house_system" not in bazi_args
    assert "zodiac_type" not in bazi_args
    assert bazi_args["zi_hour_policy"] == "night_zi_same_day_next_hour_stem"
    # Precedence: defaults (2026) < call.arguments (2028)
    assert bazi_args["analysis_year"] == 2028
    # Precedence: defaults (False) < subject (True) < call.arguments (False)
    assert bazi_args["use_true_solar_time"] is False
    assert bazi_args["birth_year"] == 1990
    assert bazi_args["birth_timezone"] == "Asia/Shanghai"

    # Subject overrides defaults when arguments does not specify the key
    astro_args = resolve_call_arguments(
        SPECS["astrology_chart"],
        BatchCall(tool="astrology_chart", subject="alice"),
        subjects=subjects,
        defaults=defaults,
    )
    assert astro_args["house_system"] == "P"
    assert astro_args["zodiac_type"] == "Tropic"
    assert astro_args["use_true_solar_time"] is True
    assert "zi_hour_policy" not in astro_args

    # Date/time tools map birth_date/birth_time/timezone/longitude/latitude
    suzhan_args = resolve_call_arguments(
        SPECS["suzhan"],
        BatchCall(tool="suzhan", subject="bob"),
        subjects=subjects,
        defaults=defaults,
    )
    assert suzhan_args["date"] == "1992-03-02"
    assert suzhan_args["time"] == "08:18"
    assert suzhan_args["timezone"] == "Asia/Shanghai"
    assert suzhan_args["longitude"] == 116.4074
    assert suzhan_args["latitude"] == 39.9042

    # Fengshui minggua avoids sending both birth_date and birth_year
    minggua_args = resolve_call_arguments(
        SPECS["fengshui_minggua"],
        BatchCall(tool="fengshui_minggua", subject="alice"),
        subjects=subjects,
        defaults=defaults,
    )
    assert minggua_args["birth_date"] == "1990-05-15"
    assert "birth_year" not in minggua_args
    assert "effective_birth_year" not in minggua_args
    assert minggua_args["timezone_name"] == "Asia/Shanghai"

    # Dynamic inspection works for renamed fengshui-ergo fields (gender / birth_year) too
    from dataclasses import replace

    from pydantic import BaseModel

    class ErgoOccupant(BaseModel):
        subject_id: str | None = None
        timezone_name: str = "Asia/Shanghai"
        birth_date: str | None = None
        birth_year: int | None = None
        birth_at: str | None = None
        gender: str | None = None

    class ErgoAssess(BaseModel):
        occupants: list[ErgoOccupant] = []

    ergo_spec = replace(SPECS["fengshui_assess"], request_model=ErgoAssess)
    year_only_subjects = {
        "y": SubjectProfile.model_validate({"birth_year": 1988, "gender": "male"})
    }
    ergo_args = resolve_call_arguments(
        ergo_spec,
        BatchCall(tool="fengshui_assess", subjects=["y"]),
        subjects=year_only_subjects,
        defaults={},
    )
    assert ergo_args == {
        "occupants": [{"subject_id": "y", "gender": "male", "birth_year": 1988}]
    }


def test_single_subject_fanout_and_shared_as_of() -> None:
    request = BatchRequest.model_validate(
        {
            "subjects": {"alice": ALICE_PROFILE},
            "defaults": {
                "house_system": "P",
                "zodiac_type": "Tropic",
                "school": "default",
                "zi_hour_policy": "day_rollover_at_23",
            },
            "calls": [
                {
                    "id": "bazi",
                    "tool": "bazi_birth_chart",
                    "subject": "alice",
                    "fields": ["bazi_birth.day_master"],
                },
                {
                    "id": "ziwei",
                    "tool": "ziwei_birth_chart",
                    "subject": "alice",
                    "include": ["*"],
                },
                {"id": "astro", "tool": "astrology_chart", "subject": "alice"},
                {"id": "vedic", "tool": "vedic_chart", "subject": "alice"},
                {"id": "suzhan", "tool": "suzhan", "subject": "alice"},
                {
                    "id": "lunar",
                    "tool": "lunar_calendar_time",
                    "subject": "alice",
                    "arguments": {"time_alg": 0},
                },
                {"id": "minggua", "tool": "fengshui_minggua", "subject": "alice"},
            ],
        }
    )
    payload = execute_batch(SPECS, request)
    assert payload["status"] == "ok"
    assert payload["succeeded"] == 7
    assert payload["failed"] == 0
    assert isinstance(payload["as_of"], str) and payload["as_of"].endswith("Z")

    results = payload["results"]
    assert [item["id"] for item in results] == [
        "bazi",
        "ziwei",
        "astro",
        "vedic",
        "suzhan",
        "lunar",
        "minggua",
    ]
    assert all(item["ok"] for item in results)

    # Fields projection on call 0
    bazi_res = results[0]["result"]
    assert set(bazi_res["bazi_birth"]) == {"day_master"}
    # Audit override on call 1 shares the same frozen as_of
    ziwei_res = results[1]["result"]
    assert ziwei_res["run_metadata"]["replay"]["as_of"] == payload["as_of"]


def test_multi_subject_compatibility_and_fengshui_pairing() -> None:
    request = BatchRequest.model_validate(
        {
            "subjects": {"alice": ALICE_PROFILE, "bob": BOB_PROFILE},
            "defaults": {
                "house_system": "P",
                "zodiac_type": "Tropic",
                "relationship_type": "marriage",
                "relative_mode": "Composite",
            },
            "as_of": "2026-10-12T12:00:00+08:00",
            "calls": [
                {
                    "id": "bazi_pair",
                    "tool": "bazi_compatibility",
                    "subjects": ["alice", "bob"],
                },
                {
                    "id": "astro_pair",
                    "tool": "relationship_chart",
                    "subjects": ["alice", "bob"],
                },
                {
                    "id": "sukuyo_pair",
                    "tool": "sukuyo_compatibility",
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
    )
    payload = execute_batch(SPECS, request)
    assert payload["status"] == "ok"
    assert payload["succeeded"] == 5
    assert payload["failed"] == 0
    assert payload["as_of"] == "2026-10-12T04:00:00Z"

    by_id = {item["id"]: item["result"] for item in payload["results"]}
    assert "cross_chart_relations" in by_id["bazi_pair"]
    assert (
        by_id["astro_pair"]["relationship_profile"]["relative_mode_normalized"]
        == "composite"
    )
    assert by_id["sukuyo_pair"]["person1"]["name"] == "Alice"
    assert by_id["sukuyo_pair"]["person2"]["name"] == "Bob"
    assert "bazhai" in by_id["bazhai"]["layers"]
    assert "layers" in by_id["assess"]


def test_batch_error_isolation_stop_on_error_and_upfront_subject_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1. Unknown subject reference fails up front before any execution runs.
    monkeypatch.setattr(
        "fatebridge.application.batch.execute_with_receipt",
        lambda *args, **kwargs: pytest.fail("must not execute with unknown subject"),
    )
    bad_ref_req = BatchRequest.model_validate(
        {
            "subjects": {"alice": ALICE_PROFILE},
            "calls": [{"tool": "bazi_birth_chart", "subject": "charlie"}],
        }
    )
    with pytest.raises(ParameterError) as exc_info:
        execute_batch(SPECS, bad_ref_req)
    issue = exc_info.value.issues[0]
    assert issue["code"] == "unknown_subject"
    assert issue["path"] == "calls.0.subject"
    assert issue["constraints"] == {"available": ["alice"]}


def test_batch_partial_error_all_error_and_stop_on_error() -> None:
    # Partial error continues past failures
    partial_req = BatchRequest.model_validate(
        {
            "subjects": {"alice": ALICE_PROFILE},
            "as_of": "2026-10-12T04:00:00Z",
            "calls": [
                {"id": "ok1", "tool": "bazi_birth_chart", "subject": "alice"},
                {"id": "bad_tool", "tool": "bazi_birth_chrat", "subject": "alice"},
                {
                    "id": "bad_field",
                    "tool": "bazi_birth_chart",
                    "subject": "alice",
                    "fields": ["nonexistent_xyz"],
                },
                {"id": "ok2", "tool": "fengshui_minggua", "subject": "alice"},
            ],
        }
    )
    partial = execute_batch(SPECS, partial_req)
    assert partial["status"] == "partial_error"
    assert partial["succeeded"] == 2
    assert partial["failed"] == 2
    assert len(partial["results"]) == 4
    assert partial["results"][1]["error"]["error_code"] == "unknown_tool"
    assert (
        "bazi_birth_chart"
        in partial["results"][1]["error"]["issues"][0]["constraints"]["suggestions"]
    )
    assert (
        partial["results"][2]["error"]["issues"][0]["code"] == "unknown_projection_path"
    )

    # stop_on_error=True stops at first failure
    stop_req = BatchRequest.model_validate(
        {
            "subjects": {"alice": ALICE_PROFILE},
            "as_of": "2026-10-12T04:00:00Z",
            "stop_on_error": True,
            "calls": [
                {"id": "ok1", "tool": "bazi_birth_chart", "subject": "alice"},
                {"id": "bad_tool", "tool": "no_such_tool"},
                {"id": "skipped", "tool": "fengshui_minggua", "subject": "alice"},
            ],
        }
    )
    stopped = execute_batch(SPECS, stop_req)
    assert stopped["status"] == "partial_error"
    assert stopped["succeeded"] == 1
    assert stopped["failed"] == 1
    assert [item["id"] for item in stopped["results"]] == ["ok1", "bad_tool"]

    # All calls fail -> status == "error"
    all_err_req = BatchRequest.model_validate(
        {
            "calls": [{"id": "bad", "tool": "no_such_tool"}],
        }
    )
    all_err = execute_batch(SPECS, all_err_req)
    assert all_err["status"] == "error"
    assert all_err["succeeded"] == 0
    assert all_err["failed"] == 1


def test_three_surface_batch_parity_mcp_rest_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """MCP run_batch, REST POST /api/batch, and CLI `batch --request-file` produce identical payloads."""
    request_payload = {
        "subjects": {"alice": ALICE_PROFILE, "bob": BOB_PROFILE},
        "defaults": {
            "house_system": "P",
            "zodiac_type": "Tropic",
            "relationship_type": "general",
        },
        "as_of": "2026-10-12T12:00:00+08:00",
        "calls": [
            {
                "id": "alice_bazi",
                "tool": "bazi_birth_chart",
                "subject": "alice",
                "fields": ["bazi_birth.day_master"],
            },
            {
                "id": "alice_astro",
                "tool": "astrology_chart",
                "subject": "alice",
                "include": ["*"],
            },
            {
                "id": "pair_bazi",
                "tool": "bazi_compatibility",
                "subjects": ["alice", "bob"],
            },
            {
                "id": "alice_minggua",
                "tool": "fengshui_minggua",
                "subject": "alice",
            },
        ],
    }

    # 1. REST POST /api/batch
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    client_http = TestClient(api.app)
    rest_res = client_http.post("/api/batch", json=request_payload)
    assert rest_res.status_code == 200, rest_res.text
    rest_body = rest_res.json()

    # 2. MCP run_batch
    async def mcp_call():
        async with Client(cached_mcp_app()) as mcp_client:
            return await mcp_client.call_tool("run_batch", request_payload)

    mcp_res = asyncio.run(mcp_call())
    assert not mcp_res.is_error
    mcp_body = mcp_res.structured_content
    assert mcp_body is not None

    # 3. CLI batch --request-file <path>
    req_file = tmp_path / "batch.json"
    req_file.write_text(
        json.dumps(request_payload, ensure_ascii=False), encoding="utf-8"
    )
    capsys.readouterr()
    code = cli.run(["batch", "--request-file", str(req_file)])
    assert code == 0
    cli_body = json.loads(capsys.readouterr().out)

    # 4. CLI batch --request-file - (stdin)
    monkeypatch.setattr(
        cli.sys, "stdin", io.StringIO(json.dumps(request_payload, ensure_ascii=False))
    )
    code_stdin = cli.run(["batch", "--request-file", "-"])
    assert code_stdin == 0
    cli_stdin_body = json.loads(capsys.readouterr().out)

    assert (
        _strip_run_metadata(rest_body)
        == _strip_run_metadata(mcp_body)
        == _strip_run_metadata(cli_body)
        == _strip_run_metadata(cli_stdin_body)
    )
    assert (
        rest_body["as_of"]
        == mcp_body["as_of"]
        == cli_body["as_of"]
        == "2026-10-12T04:00:00Z"
    )


def test_batch_boundary_errors_across_surfaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bad_subject_payload = {
        "subjects": {"alice": ALICE_PROFILE},
        "calls": [{"tool": "bazi_birth_chart", "subject": "missing_person"}],
    }

    # REST unknown subject -> 422 ErrorEnvelope
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest_err = TestClient(api.app).post("/api/batch", json=bad_subject_payload)
    assert rest_err.status_code == 422
    assert rest_err.json()["error_code"] == "validation_error"
    assert rest_err.json()["issues"][0]["code"] == "unknown_subject"

    # MCP unknown subject -> is_error=True
    async def mcp_bad():
        async with Client(cached_mcp_app()) as mcp_client:
            return await mcp_client.call_tool(
                "run_batch", bad_subject_payload, raise_on_error=False
            )

    mcp_err = asyncio.run(mcp_bad())
    assert mcp_err.is_error
    assert mcp_err.structured_content["issues"][0]["code"] == "unknown_subject"

    # CLI unknown subject -> exit 1 JSON
    bad_file = tmp_path / "bad_subject.json"
    bad_file.write_text(json.dumps(bad_subject_payload), encoding="utf-8")
    capsys.readouterr()
    assert cli.run(["batch", "--request-file", str(bad_file)]) == 1
    cli_err = json.loads(capsys.readouterr().out)
    assert cli_err["issues"][0]["code"] == "unknown_subject"

    # CLI missing / invalid file -> exit 2 usage_error
    assert cli.run(["batch", "--request-file", str(tmp_path / "missing.json")]) == 2
    usage_err = json.loads(capsys.readouterr().out)
    assert usage_err["error_code"] == "usage_error"


def test_batch_field_level_validation_and_call_suggestions() -> None:
    with pytest.raises(ValidationError) as subj_err:
        SubjectProfile.model_validate({"birth_date": "1990-02-30"})
    assert subj_err.value.errors()[0]["ctx"]["path"] == "birth_date"

    with pytest.raises(ValidationError) as call_err:
        BatchCall.model_validate(
            {"tool": "bazi_birth_chart", "subject": "a", "subjects": ["a"]}
        )
    assert call_err.value.errors()[0]["ctx"]["path"] == "subjects"

    bad_arg_req = BatchRequest.model_validate(
        {
            "subjects": {"alice": ALICE_PROFILE},
            "calls": [
                {
                    "id": "typo",
                    "tool": "bazi_birth_chart",
                    "subject": "alice",
                    "arguments": {"birth_huor": 10},
                }
            ],
        }
    )
    res = execute_batch(SPECS, bad_arg_req)
    assert res["status"] == "error"
    issue = res["results"][0]["error"]["issues"][0]
    assert issue["code"] == "extra_forbidden"
    assert issue["path"] == "birth_huor"
    assert "birth_hour" in issue["constraints"]["suggestions"]
    assert "birth_hour" in issue["constraints"]["allowed_fields"]


def test_batch_analysis_context_place_and_nested_extra_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    batch_payload = {
        "context": {
            "analysis_datetime": "2026-04-06T09:30:00+08:00",
            "place": "杭州西湖区",
        },
        "calls": [
            {"id": "qm", "tool": "qimen"},
            {"id": "lr", "tool": "liuren_chart"},
            {"id": "jk", "tool": "jinkou"},
            {"id": "mh", "tool": "meihua_time_cast"},
            {"id": "hr", "tool": "horary_chart"},
            {"id": "ss", "tool": "sanshi_combined_chart"},
        ],
    }
    res = execute_batch(SPECS, BatchRequest.model_validate(batch_payload))
    assert res["status"] == "ok", res
    assert res["succeeded"] == 6

    example = cli.run(["batch", "--example"])
    assert example == 0
    ex_json = json.loads(capsys.readouterr().out)
    assert "context" in ex_json
    assert "defaults" in ex_json
    assert "as_of" in ex_json
    assert any("arguments" in c for c in ex_json["calls"])

    # Nested extra_forbidden returns allowed_fields & synonym suggestions on REST/MCP/CLI
    bad_nested_payload = {
        "context": {"analysis_datetime": "2026-04-06T09:30:00+08:00"},
        "calls": [
            {"tool": "qimen", "params": {"qimen_options": {"ju_method": "zhirun"}}}
        ],
    }
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest_err = TestClient(api.app).post("/api/batch", json=bad_nested_payload)
    assert rest_err.status_code == 422
    rest_issue = rest_err.json()["issues"][0]
    assert rest_issue["code"] == "extra_forbidden"
    assert rest_issue["constraints"]["suggestions"][0] == "arguments"
    assert "arguments" in rest_issue["constraints"]["allowed_fields"]

    bad_file = tmp_path / "bad_nested.json"
    bad_file.write_text(json.dumps(bad_nested_payload), encoding="utf-8")
    assert cli.run(["batch", "--request-file", str(bad_file)]) == 1
    cli_issue = json.loads(capsys.readouterr().out)["issues"][0]
    assert "arguments" in cli_issue["constraints"]["allowed_fields"]
    assert cli_issue["constraints"]["suggestions"][0] == "arguments"


def test_single_tool_offline_place_resolution() -> None:
    from fatebridge.core.requests.divination import (
        MeihuaAnalysisRequest,
        SanShiUnitedRequest,
    )
    from fatebridge.core.requests.sanshi import (
        JinkouAnalysisRequest,
        LiuRengGodsRequest,
        QimenAnalysisRequest,
    )
    from fatebridge.core.requests.western_events import (
        AstroHoraryRequest,
        AstroMundaneRequest,
    )

    qm = QimenAnalysisRequest(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_place="杭州西湖区",
    )
    assert qm.analysis_longitude is not None and 120.0 < qm.analysis_longitude < 120.3
    assert qm.analysis_timezone == "Asia/Shanghai"
    assert "analysis_place" not in qm.service_inputs()

    lr = LiuRengGodsRequest(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_place="杭州西湖区",
    )
    assert lr.analysis_latitude is not None and 30.1 < lr.analysis_latitude < 30.4

    jk = JinkouAnalysisRequest(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_place="杭州西湖区",
    )
    assert jk.analysis_longitude is not None

    mh = MeihuaAnalysisRequest(
        analysis_year=2026,
        analysis_month=4,
        analysis_day=6,
        analysis_hour=9,
        analysis_place="杭州西湖区",
    )
    assert mh.analysis_longitude is not None and mh.analysis_timezone == "Asia/Shanghai"
    assert "analysis_place" not in mh.service_inputs()

    ss = SanShiUnitedRequest(date="2026-04-06", time="09:30:00", place="杭州西湖区")
    assert ss.longitude is not None and float(ss.longitude) < 120.3
    assert ss.timezone == "Asia/Shanghai"
    assert "place" not in ss.service_inputs()

    hr = AstroHoraryRequest(
        question_year=2026,
        question_month=4,
        question_day=6,
        question_hour=9,
        place="杭州西湖区",
    )
    assert hr.longitude is not None and hr.latitude is not None
    assert hr.timezone_name == "Asia/Shanghai"
    assert "place" not in hr.service_inputs()

    # Solar clock must NOT populate timezone_name even when place is supplied
    hr_solar = AstroHoraryRequest(
        question_year=2026,
        question_month=4,
        question_day=6,
        question_hour=9,
        question_clock_basis="local_mean_solar",
        place="杭州西湖区",
    )
    assert hr_solar.longitude is not None and hr_solar.timezone_name is None

    mn = AstroMundaneRequest(year=2026, place="杭州西湖区")
    assert mn.longitude is not None and mn.timezone_name == "Asia/Shanghai"
    assert "place" not in mn.service_inputs()


def test_batch_memoizes_shared_primitives_without_cross_batch_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fatebridge.core.metaphysics.seed as seed_mod
    import fatebridge.core.qimen.ju as qimen_ju

    seed_calls = 0
    orig_build_seed = seed_mod.build_metaphysics_seed

    def tracked_seed(*args, **kwargs):
        nonlocal seed_calls
        seed_calls += 1
        return orig_build_seed(*args, **kwargs)

    monkeypatch.setattr(seed_mod, "build_metaphysics_seed", tracked_seed)

    qimen_calls = 0
    orig_assemble_qimen = qimen_ju.build_qimen_board

    def tracked_qimen(*args, **kwargs):
        nonlocal qimen_calls
        qimen_calls += 1
        return orig_assemble_qimen(*args, **kwargs)

    monkeypatch.setattr(qimen_ju, "build_qimen_board", tracked_qimen)

    batch_req = BatchRequest.model_validate(
        {
            "context": {
                "analysis_datetime": "2026-04-06T09:30:00+08:00",
                "place": "杭州西湖区",
            },
            "calls": [
                {"id": "qm", "tool": "qimen"},
                {"id": "lr", "tool": "liuren_chart"},
                {"id": "jk", "tool": "jinkou"},
                {"id": "ss", "tool": "sanshi_combined_chart"},
                {"id": "qm_dup", "tool": "qimen"},
            ],
            "as_of": "2026-04-06T09:30:00+08:00",
        }
    )
    res1 = execute_batch(SPECS, batch_req)
    assert res1["status"] == "ok" and res1["succeeded"] == 5
    # qimen/liuren_chart/jinkou share one build_analysis_seed call, and qm_dup hits raw cache
    assert seed_calls <= 2, f"Expected memoized seed builds <= 2, got {seed_calls}"
    assert qimen_calls <= 2, f"Expected memoized qimen builds <= 2, got {qimen_calls}"

    # Second independent batch must NOT reuse stale cache entries across scopes
    prev_seed_calls = seed_calls
    res2 = execute_batch(SPECS, batch_req)
    assert res2["status"] == "ok"
    assert seed_calls > prev_seed_calls
