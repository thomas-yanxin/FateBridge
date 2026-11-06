"""Source geometry, untested qualifiers, and actual witnesses remain separate."""

import asyncio
import json
import shutil
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
import scripts.ziwei.audit_ziwei_conditions as audit
from fatebridge.application.examples import evidence_views, suggested_fields
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.core.output_chinese import ZiweiStructuralConditionRecord
from fatebridge.core.ziwei_conditions import structural_condition_evidence
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from scripts.ziwei.audit_ziwei_limits import _seed
from tests.fixtures.mcp_receipt import verified_inline_business
from tests.fixtures.mcp_result_delivery import assert_same_run_receipt


def test_independent_printed_examples_are_distinct_from_derived_coverage():
    r = audit.audit_conditions()
    assert not r["differences"]
    assert (
        r["source_clauses"],
        r["literal_placement_examples"],
        r["source_manual_readers"],
    ) == (5, 2, 1)
    assert (
        r["conditional_chart_inputs"],
        r["premises_checked"],
        r["actual_star_joins_checked"],
    ) == (34560, 172800, 380160)
    assert r["original_preimplementation_chart_inputs"] == 1152
    assert r["postimplementation_chart_inputs"] == 33408
    assert r["postimplementation_coverage_declared"]
    assert all(v == [False, True] for v in r["evaluated_premise_outcomes"].values())
    assert (
        r["full_traditional_judgments_evaluated"] == 0
        and r["new_independent_editions"] == 0
    )
    assert not r["independent_placement_or_calendar_oracle"]
    assert (
        not r["flanking_generalization_independently_adjudicated"]
        and not r["whole_book_acceptance_passed"]
    )
    assert r["live_model_blind_evaluation"] == "not_run"


def test_wrong_geometric_result_is_detected_against_frozen_neighbor_lists(monkeypatch):
    original = audit.build_ziwei_chart

    def wrong(*a, **kw):
        c = original(*a, **kw)
        r = c["ming_structural_conditions"]["records"][3]
        r["geometry_match"] = not r["geometry_match"]
        return c

    monkeypatch.setattr(audit, "build_ziwei_chart", wrong)
    assert len(audit.audit_conditions()["differences"]) == 34560


def test_original_images_are_required(tmp_path):
    shutil.copytree(
        audit.FIXTURES / "naj_ming_conditions_v1", tmp_path / "naj_ming_conditions_v1"
    )
    (tmp_path / "naj_ming_conditions_v1/frame_0059.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="condition source checksum mismatch"):
        audit.audit_conditions(tmp_path)


def _palaces(positions, ming):
    return [
        dict(
            name="命宫" if b == ming else "条件测试宫",
            ganzhi="甲" + b,
            stars_detail=[
                dict(name=n, mutagen=None) for n, p in positions.items() if p == b
            ],
        )
        for b in "子丑寅卯辰巳午未申酉戌亥"
    ]


@pytest.mark.parametrize(
    "ming,left,right,expected",
    [
        ("丑", "子", "寅", True),
        ("丑", "寅", "子", True),
        ("子", "亥", "丑", True),
        ("亥", "戌", "子", True),
        ("丑", "子", "子", False),
        ("丑", "丑", "寅", False),
        ("丑", "未", "丑", False),
    ],
)
def test_selected_bilateral_reading_rejects_same_side_same_palace_or_opposition(
    ming, left, right, expected
):
    p = _palaces({"左辅": left, "右弼": right}, ming)
    before = deepcopy(p)
    e = structural_condition_evidence(p, ming_branch=ming, year_stem="甲")
    r = next(r for r in e["records"] if r["id"] == "fubi_flank_ming")
    assert r["geometry_match"] is expected and r["full_traditional_judgment"] is None
    assert r["source_outcome_claim_adopted"] is False and p == before


@pytest.mark.parametrize("duplicate", [False, True])
def test_missing_or_duplicated_star_is_unknown_not_a_negative(duplicate):
    p = _palaces({"左辅": "子", "右弼": "寅"}, "丑")
    next(x for x in p if x["ganzhi"][1] == "寅")["stars_detail"] = []
    if duplicate:
        next(x for x in p if x["ganzhi"][1] == "卯")["stars_detail"] = [
            dict(name="左辅", mutagen=None)
        ]
    r = next(
        r
        for r in structural_condition_evidence(p, ming_branch="丑", year_stem="甲")[
            "records"
        ]
        if r["id"] == "fubi_flank_ming"
    )
    assert (
        r["geometry_match"] is None and r["evaluated_necessary_premises_match"] is None
    )
    assert "右弼" in r["missing_or_duplicated_stars"]


def test_known_stem_failure_does_not_become_unknown_when_another_fact_is_missing():
    r = structural_condition_evidence([], ming_branch="寅", year_stem="乙")["records"][
        0
    ]
    assert (
        r["geometry_match"] is None and r["evaluated_necessary_premises_match"] is False
    )


def test_all_evaluated_premises_do_not_discharge_unresolved_no_sha_qualification():
    r = structural_condition_evidence(
        _palaces({"紫微": "寅", "天府": "寅"}, "寅"), ming_branch="寅", year_stem="甲"
    )["records"][0]
    assert r["geometry_match"] and r["evaluated_necessary_premises_match"]
    assert (
        r["source_qualifications_not_evaluated"]
        and r["full_traditional_judgment"] is None
    )
    assert r["source_outcome_claim_adopted"] is False
    with pytest.raises(ValidationError):
        ZiweiStructuralConditionRecord.model_validate(
            {**r, "full_traditional_judgment": True}
        )


def test_source_example_orientation_is_distinct_from_selected_general_geometry():
    e = structural_condition_evidence(
        _palaces({"天魁": "巳", "天钺": "卯"}, "辰"), ming_branch="辰", year_stem="壬"
    )
    r = next(r for r in e["records"] if r["id"] == "kuiyue_flank_ming")
    assert r["geometry_match"] and not r["source_literal_example_matches"]
    assert not e["actual_assignments_modified"]


def test_returned_witnesses_do_not_mutate_cached_source_or_chart():
    c = build_ziwei_chart(_seed(1992, 9, hour="午"), "未知")
    before = deepcopy(c)
    e = structural_condition_evidence(
        c["palaces"], ming_branch=c["ming_gong"]["branch"], year_stem=c["year_stem"]
    )
    e["records"][0]["source_qualifications_not_evaluated"].clear()
    e["records"][0]["actual_occurrences"]["紫微"][0]["natal_branch"] = "假"
    assert (
        c == before
        and c["ming_structural_conditions"]["records"][0][
            "source_qualifications_not_evaluated"
        ]
    )


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
@pytest.mark.parametrize("source", ["rule_profile", "naj_ming_v1"])
def test_source_summary_and_null_judgment_match_rest_native_mcp_cli(
    profile, source, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    inputs = dict(
        birth_year=1992,
        birth_month=10,
        birth_day=1,
        birth_hour=12,
        gender="未知",
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=False,
        rule_profile=profile,
        sihua_source=source,
    )
    fields = evidence_views(spec)["classical_conditions"]["fields"]
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        as_of="2026-10-22T12:00:00+08:00",
    )
    rest = TestClient(api.app).post(
        spec.rest_path,
        json=inputs,
        params=[
            ("as_of", opts["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            *[("fields", f) for f in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            r = await client.call_tool("ziwei_birth", {**inputs, **opts})
            assert not r.is_error
            return await verified_inline_business(client, r.structured_content)

    native = asyncio.run(call())
    args = ["ziwei_birth"]
    for k, v in inputs.items():
        args += ["--" + k.replace("_", "-"), str(v)]
    args += [
        "--as-of",
        opts["as_of"],
        "--strict-fields",
        "--no-include-snapshot-text",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in p.items() if k not in ("run_metadata", "result_delivery")}
        for p in [rest.json(), native, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    e = bodies[0]["ziwei_birth"]["ming_structural_conditions"]
    assert "records" not in e  # A summary run cannot promise omitted detail.
    assert len(e["index"]) == 5 and all(
        r["full_traditional_judgment"] is None for r in e["index"]
    )


def test_same_run_claim_distinguishes_unknown_full_judgment_from_true():
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    request = spec.request_model.model_validate(
        dict(
            birth_year=1992,
            birth_month=10,
            birth_day=1,
            birth_hour=12,
            gender="未知",
            birth_timezone="Asia/Shanghai",
            use_true_solar_time=False,
        )
    )
    p = execute_tool(spec, request)
    m = p["run_metadata"]

    def claim(value):
        return CalculationClaim(
            path="ziwei_birth.ming_structural_conditions.records.0.full_traditional_judgment",
            value=value,
            run_id=m["run_id"],
        )

    assert (
        verify_calculation_claims(p, [claim(None)])["status"]
        == "verified_structured_facts"
    )
    assert verify_calculation_claims(p, [claim(True)])["status"] == "rejected"


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_complete_conditions_and_witnesses_survive_same_run_pagination(
    profile, monkeypatch, capsys
):
    import hashlib

    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    inputs = dict(
        birth_year=1992,
        birth_month=10,
        birth_day=1,
        birth_hour=12,
        gender="未知",
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=False,
        rule_profile=profile,
    )
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    fields = evidence_views(spec)["classical_condition_details"]["fields"]
    opts = dict(
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        as_of="2026-10-22T12:00:00+08:00",
    )
    rest = TestClient(api.app).post(
        "/api/cn/ziwei/birth",
        json=inputs,
        params=[
            ("as_of", opts["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            *[("fields", f) for f in fields],
        ],
    )
    assert rest.status_code == 200, rest.text

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            r = await client.call_tool("ziwei_birth", {**inputs, **opts})
            assert not r.is_error
            p = r.structured_content
            assert len(json.dumps(p, ensure_ascii=False, separators=(",", ":"))) <= 8192
            if "result_delivery" not in p:
                return p
            ref = p["result_delivery"]
            uri = ref["first_page_uri"]
            raw = ""
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                raw += page["text"]
                uri = page["next_uri"]
            assert hashlib.sha256(raw.encode()).hexdigest() == ref["sha256"]
            full = json.loads(raw)
            assert_same_run_receipt(
                p["run_metadata"],
                full["run_metadata"],
                deferred_fields=ref["deferred_fields"],
            )
            return full

    native = asyncio.run(call())
    args = ["ziwei_birth"]
    for k, v in inputs.items():
        args += ["--" + k.replace("_", "-"), str(v)]
    args += [
        "--as-of",
        opts["as_of"],
        "--strict-fields",
        "--no-include-snapshot-text",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    assert run(args) == 0
    cli = json.loads(capsys.readouterr().out)
    bodies = [
        {k: v for k, v in p.items() if k not in ("run_metadata", "result_delivery")}
        for p in [rest.json(), native, cli]
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    e = bodies[0]["ziwei_birth"]["ming_structural_conditions"]
    assert len(e["records"]) == 5
    assert (
        sum(
            len(items)
            for r in e["records"]
            for items in r["actual_occurrences"].values()
        )
        == 11
    )
    assert all(
        r["full_traditional_judgment"] is None
        and r["source_qualifications_not_evaluated"]
        for r in e["records"]
    )
