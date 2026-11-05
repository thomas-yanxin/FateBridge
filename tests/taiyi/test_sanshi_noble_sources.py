"""Source-edition noble starts must survive selection and public delivery."""

import asyncio
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.ren_gods import noble_start
from fatebridge.core.metaphysics.taiyi_dangshi import noble_source_assessment
from fatebridge.core.output_sanshi import NobleSourceAssessment
from fatebridge.core.requests.divination import SanShiUnitedRequest
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.divination import calculate_sanshiunited_analysis
from fatebridge.services.tool_catalog import CATALOG

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_dangshi_noble_v40"
SOURCE_FREEZE = "2ad83f1a72c0c941dd83f2ff5f4247871ae18227be9a8bdcb06baaa08b0de47c"


def source_readings():
    assert (
        hashlib.sha256((CORPUS / "freeze.json").read_bytes()).hexdigest()
        == SOURCE_FREEZE
    )
    frozen = json.loads((CORPUS / "freeze.json").read_text())
    for base, key in ((CORPUS, "files"), (ROOT, "prior_sources")):
        for name, digest in frozen[key].items():
            assert hashlib.sha256((base / name).read_bytes()).hexdigest() == digest
    return json.loads((CORPUS / "readings.json").read_text())


def test_sanshi_exposes_an_explicit_noble_profile_without_changing_default():
    field = SanShiUnitedRequest.model_fields.get("liureng_guiren_profile")
    assert field is not None
    assert field.default == "liuren_common_v1"


@pytest.mark.parametrize("mode", [None, "year", "month", "day", "hour"])
def test_comparison_uses_the_actual_mode_summary_including_default_year(mode):
    options = {"calculation_mode": mode} if mode else None
    result = calculate_sanshiunited_analysis(
        date="2026-10-25",
        time="12:00:00",
        zone="+08:00",
        use_true_solar_time=False,
        taiyi_options=options,
    )
    assert "synthesis" in result, result
    actual = result["synthesis"]["noble_source_assessment"]
    assert (
        actual["taiyi_mode"]
        == result["taiyi"]["calendar_summary"]["calculation_mode"]
        == (mode or "year")
    )
    assert actual["whole_dangshi_method_acceptance_passed"] is False


@pytest.mark.parametrize("profile", ["liuren_common_v1", "tanyuan_xieji_v1"])
def test_selected_noble_profile_reaches_the_actual_same_run_board(profile):
    result = calculate_sanshiunited_analysis(
        date="2026-10-25",
        time="12:00:00",
        zone="+08:00",
        use_true_solar_time=False,
        taiyi_options={"calculation_mode": "hour"},
        liureng_guiren_profile=profile,
    )
    assert "synthesis" in result, result
    assert result["input_normalized"]["liureng_guiren_profile"] == profile
    assert result["liureng"]["meta"]["guiren_profile"] == profile
    assessment = result["synthesis"]["noble_source_assessment"]
    assert assessment["status"] == "compared_noble_start_only"
    assert assessment["actual_profile"] == profile
    assert assessment["source_morning_evening_boundary_adjudicated"] is False
    trace = result["liureng"]["rule_trace"][assessment["actual_trace_index"]]
    assert trace["rule_id"] == "liuren.guiren_start"
    assert assessment["actual_start_branch"] == trace["result"]["start_branch"]
    for row in assessment["comparisons"]:
        reading = next(
            e for e in source_readings()["editions"] if e["id"] == row["source_id"]
        )
        expected = next(
            r for r in reading["rows"] if r["stem"] == assessment["day_stem"]
        )
        expected_branch = expected[
            "morning_branch" if assessment["is_diurnal"] else "evening_branch"
        ]
        assert row["source_branch"] == expected_branch
        assert row["matches"] is (expected_branch == assessment["actual_start_branch"])
    assert "[三式贵人来源对照]" in result["snapshot_text"]
    exported = next(
        s
        for s in result["snapshot_export"]["sections"]
        if s["title"] == "三式贵人来源对照"
    )
    assert exported["included"] and exported["content"] in result["snapshot_text"]


@pytest.mark.parametrize("profile", ["liuren_common_v1", "tanyuan_xieji_v1"])
@pytest.mark.parametrize("is_day", [True, False])
@pytest.mark.parametrize("stem", list("甲乙丙丁戊己庚辛壬癸"))
def test_all_twenty_starts_for_each_profile_keep_both_source_editions(
    profile, is_day, stem
):
    board = {
        "meta": {"guiren_profile": profile, "is_diurnal": is_day},
        "rule_trace": [
            {
                "rule_id": "liuren.guiren_start",
                "result": {
                    "profile": profile,
                    "is_diurnal": is_day,
                    "start_branch": noble_start(stem, is_day, profile),
                    "earth_branch": "辰",
                },
            }
        ],
    }
    actual = noble_source_assessment(stem, board, taiyi_mode="hour")
    NobleSourceAssessment.model_validate(actual)
    readings = source_readings()["editions"]
    assert len(actual["comparisons"]) == 2
    for source, comparison in zip(readings, actual["comparisons"], strict=True):
        row = next(r for r in source["rows"] if r["stem"] == stem)
        expected = row["morning_branch" if is_day else "evening_branch"]
        assert comparison["source_branch"] == expected
        assert comparison["matches"] is (actual["actual_start_branch"] == expected)
        aligned = (profile == "liuren_common_v1") == ("ming" in source["id"])
        assert comparison["matches"] is (aligned or stem in "丁戊己庚癸")
    assert (
        actual["actual_start_branch"] != "辰"
    )  # Earth position is not the source start.
    actual["comparisons"][0]["source_branch"] = "破坏返回值"
    assert (
        noble_source_assessment(stem, board, taiyi_mode="hour")["comparisons"][0][
            "source_branch"
        ]
        != "破坏返回值"
    )


@pytest.fixture
def actual_ren():
    return {
        "meta": {"guiren_profile": "liuren_common_v1", "is_diurnal": True},
        "rule_trace": [
            {
                "rule_id": "liuren.guiren_start",
                "result": {
                    "profile": "liuren_common_v1",
                    "is_diurnal": True,
                    "start_branch": "丑",
                },
            }
        ],
    }


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "duplicate",
        "string_day",
        "meta_profile",
        "meta_day",
        "bad_start",
        "bad_stem",
    ],
)
def test_missing_or_conflicting_actual_trace_never_selects_a_source_by_fit(
    actual_ren, fault
):
    board = deepcopy(actual_ren)
    stem = "甲"
    if fault == "missing":
        board["rule_trace"] = []
    elif fault == "duplicate":
        board["rule_trace"] *= 2
    elif fault == "string_day":
        board["rule_trace"][0]["result"]["is_diurnal"] = "true"
    elif fault == "meta_profile":
        board["meta"]["guiren_profile"] = "tanyuan_xieji_v1"
    elif fault == "meta_day":
        board["meta"]["is_diurnal"] = False
    elif fault == "bad_start":
        board["rule_trace"][0]["result"]["start_branch"] = "乾"
    else:
        stem = ""
    result = noble_source_assessment(stem, board, taiyi_mode="hour")
    assert result["status"] == "not_assessed" and result["comparisons"] == []
    assert not result["whole_dangshi_method_acceptance_passed"]


def test_comparison_reads_the_supplied_result_instead_of_recalculating_a_profile(
    actual_ren,
):
    actual_ren["rule_trace"][0]["result"]["start_branch"] = "卯"
    compared = noble_source_assessment("甲", actual_ren, taiyi_mode="year")
    assert compared["actual_start_branch"] == "卯"
    assert all(not row["matches"] for row in compared["comparisons"])
    assert compared["applicability"] == "cross_time_scope_table_comparison_only"


@pytest.mark.parametrize("profile", ["liuren_common_v1", "tanyuan_xieji_v1"])
@pytest.mark.parametrize("is_day", [True, False])
def test_noble_selection_and_evidence_are_identical_on_rest_mcp_cli(
    monkeypatch, capsys, profile, is_day
):
    spec = next(s for s in CATALOG if s.key == "sanshiunited")
    fields = suggested_fields(spec, view="noble_sources")
    payload = dict(
        date="2026-10-25",
        time="12:00:00",
        zone="+08:00",
        use_true_solar_time=False,
        taiyi_options={"calculation_mode": "hour"},
        liureng_guiren_profile=profile,
        liureng_is_diurnal=is_day,
    )
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
        as_of="2026-10-25T12:00:00+08:00",
    )
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    response = TestClient(api.app).post(
        spec.rest_path,
        json=payload,
        params=[("fields", f) for f in fields]
        + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "0"),
            ("as_of", opts["as_of"]),
        ],
    )
    assert response.status_code == 200, response.text

    async def invoke():
        async with Client(create_mcp_app()) as client:
            result = await client.call_tool(
                "sanshiunited", {**payload, **opts}, raise_on_error=False
            )
            assert not result.is_error, result
            return result.structured_content

    protocol = asyncio.run(invoke())
    argv = ["sanshiunited"]
    for key, value in payload.items():
        argv += [
            "--" + key.replace("_", "-"),
            json.dumps(value) if isinstance(value, dict) else str(value),
        ]
    argv += [
        "--fields",
        *fields,
        "--strict-fields",
        "--no-include-snapshot-text",
        "--response-char-limit",
        "0",
        "--as-of",
        opts["as_of"],
    ]
    capsys.readouterr()
    assert run(argv) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in body.items() if k != "run_metadata"}
        for body in (response.json(), protocol, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    assessment = bodies[0]["synthesis"]["noble_source_assessment"]
    assert (
        assessment["actual_profile"] == profile and assessment["is_diurnal"] is is_day
    )


@pytest.mark.parametrize(
    "profile", ["best", None, True, "jinjing_ming_dangshi_noble_v1"]
)
def test_source_ids_and_arbitrary_values_are_not_request_profile_choices(profile):
    with pytest.raises(ValidationError):
        SanShiUnitedRequest.model_validate(
            dict(date="2026-10-25", time="12:00:00", liureng_guiren_profile=profile)
        )


@pytest.mark.parametrize("view", ["noble_sources", "scoped_evidence"])
def test_default_mcp_budget_preserves_the_selected_same_run_source_evidence(view):
    from tests.taiyi.test_taiyi_transports import _same_run_payload

    spec = next(s for s in CATALOG if s.key == "sanshiunited")

    async def invoke():
        async with Client(create_mcp_app()) as client:
            response = await client.call_tool(
                "sanshiunited",
                dict(
                    date="2026-10-25",
                    time="12:00:00",
                    zone="+08:00",
                    use_true_solar_time=False,
                    taiyi_options={"calculation_mode": "hour"},
                    liureng_guiren_profile="tanyuan_xieji_v1",
                    fields=suggested_fields(spec, view=view),
                    strict_fields=True,
                    include_snapshot_text=False,
                ),
                raise_on_error=False,
            )
            full = await _same_run_payload(
                client, response, require_business_inline=view == "noble_sources"
            )
            assert (
                full["synthesis"]["noble_source_assessment"]["actual_profile"]
                == "tanyuan_xieji_v1"
            )
            assert len(full["synthesis"]["noble_source_assessment"]["comparisons"]) == 2

    asyncio.run(invoke())
