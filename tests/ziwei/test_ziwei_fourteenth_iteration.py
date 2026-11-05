"""Printed meanings keep their conditions, source layers, and actual chart links."""

import asyncio
import hashlib
import json
import shutil
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client

import fatebridge.api as api
import scripts.ziwei.audit_ziwei_ming_properties as audit
from fatebridge.application.examples import (
    evidence_views,
    example_input,
    suggested_fields,
)
from fatebridge.application.execution import execute_tool
from fatebridge.cli import run
from fatebridge.core.metaphysics.ziwei import build_ziwei_chart
from fatebridge.core.ziwei_ming_properties import (
    contextual_readings,
    ming_property_evidence,
)
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_ziwei_birth
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.utils.birth_input import create_person_info
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from scripts.ziwei.audit_ziwei_limits import _seed
from tests.fixtures.mcp_receipt import assert_same_run_receipt, verified_inline_business


def test_printed_definitions_keep_unknowns_and_derived_check_denominators():
    r = audit.audit_ming_properties()
    assert (r["source_clauses"], r["source_entities"]) == (47, 53)
    assert (
        r["natal_star_definitions"],
        r["transformation_definitions"],
        r["cycle_definitions"],
    ) == (32, 4, 12)
    assert (r["conditional_chart_inputs"], r["calculation_joins_checked"]) == (
        360,
        16080,
    )
    assert not r["mismatches"]
    assert r["manual_reader_count"] == 1
    assert r["positive_star_count_note"]["printed_count"] == 18
    assert r["positive_star_count_note"]["enumerated_modern_star_names"] == 19
    assert r["unresolved_quote_tails"] == dict(jiangjun=["入和", "人和"])
    assert not r["independent_placement_or_calendar_oracle"]
    assert (
        not r["full_section_transcription_certified"]
        and not r["whole_book_acceptance_passed"]
    )


def test_wrong_join_cannot_redefine_the_frozen_expected_source(monkeypatch):
    original = audit.build_ziwei_chart

    def wrong(*a, **kw):
        c = original(*a, **kw)
        c["ming_textual_properties"]["occurrences"][0]["definition_id"] = "wrong"
        return c

    monkeypatch.setattr(audit, "build_ziwei_chart", wrong)
    assert len(audit.audit_ming_properties()["mismatches"]) == 360


def test_rewriting_packaged_source_does_not_change_the_printed_reading(
    tmp_path, monkeypatch
):
    name = "src/fatebridge/data/classical/ziwei-naj-ming-symbolism.json"
    r = json.loads((audit.ROOT / name).read_text())
    r["clauses"][13]["quote"] = r["clauses"][13]["quote"].replace("將", "降")
    p = tmp_path / name
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(r))
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    assert (
        dict(case="production_source_data")
        in audit.audit_ming_properties()["mismatches"]
    )


def test_high_resolution_source_is_required(tmp_path):
    folder = "naj_ming_symbolism_v1"
    shutil.copytree(audit.FIXTURES / folder, tmp_path / folder)
    (tmp_path / folder / "tianliang-detail.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="Ming symbolism source checksum mismatch"):
        audit.audit_ming_properties(tmp_path)


@pytest.mark.parametrize("gender", ["男", "未知"])
def test_primary_glyphs_and_same_name_layers_are_preserved(gender):
    c = build_ziwei_chart(_seed(1984), gender)
    e = c["ming_textual_properties"]
    d = e["definitions"]
    assert "將星" in d["qisha"]["quote"] and "化陰" in d["tianliang"]["quote"]
    assert d["wenchang"]["quote"].endswith("文魁之宿")
    assert d["tiantong"]["elements"] == ["水", "金"] and d["qisha"]["elements"] == [
        "火",
        "金",
    ]
    assert d["guanfu"]["elements"] == d["bingfu"]["elements"] == []
    assert d["guanfusymbol"]["elements"] == ["火"]
    rows = e["occurrences"]
    names = {(x["kind"], x["name"]) for x in rows}
    assert ("natal_star", "地空") in names and ("natal_star", "天空") not in names
    assert ("boshi_cycle_label", "飞廉") in names and (
        "natal_star",
        "蜚廉",
    ) not in names
    assert ("unassigned_source_label", "官符") not in names
    assert len(e["unresolved_boshi_labels"]) == (10 if gender == "未知" else 0)
    old = {r["star"]: r for r in c["symbolic_properties"]["records"]}
    assert "降星" in old["七杀"]["source_quote"] and old["文昌"][
        "source_quote"
    ].endswith("文魁之首")
    assert old["天梁"]["source_quote"].find("化荫") >= 0


@pytest.mark.parametrize(
    "palace,branch,ming,shen,terms",
    [
        ("官禄宫", "午", "子", "午", ["官祿主", "次桃花"]),
        ("命宫", "卯", "卯", "卯", ["次桃花"]),
        ("财帛宫", "午", "子", "寅", []),
    ],
)
def test_lianzhen_conditions_overlap_without_renaming_actual_palaces(
    palace, branch, ming, shen, terms
):
    p = [
        dict(
            name=palace,
            ganzhi="甲" + branch,
            stars_detail=[dict(name="廉贞", mutagen="化禄")],
        ),
        dict(
            name="兄弟宫",
            ganzhi="甲亥",
            stars_detail=[
                dict(name="七杀", mutagen=None),
                dict(name="紫微", mutagen=None),
            ],
        ),
    ]
    original = deepcopy(p)
    r = contextual_readings(p, ming_branch=ming, shen_branch=shen)
    assert r["lianzhen"]["applicable_terms_given_selected_reading"] == terms
    assert not r["lianzhen"]["terms_are_new_palace_names"]
    assert r["qisha"]["same_palace"] and r["qisha"]["condition_match"] is None
    assert r["qisha"]["actual_qisha_mutagen"] is None
    assert not r["qisha"]["symbolic_quan_is_new_sihua_assignment"]
    assert p == original


def test_star_and_transformation_elements_are_distinct_and_returned_data_is_isolated():
    c = build_ziwei_chart(_seed(1984), "男")
    before = deepcopy(c)
    e = c["ming_textual_properties"]
    sun = next(
        r for r in e["occurrences"] if r["kind"] == "natal_star" and r["name"] == "太阳"
    )
    ji = next(
        r
        for r in e["occurrences"]
        if r["kind"] == "natal_transformation" and r["name"] == "化忌"
    )
    assert sun["calculation_path"] == ji["calculation_path"] and ji["star"] == "太阳"
    assert e["definitions"][sun["definition_id"]]["elements"] == ["火"]
    assert e["definitions"][ji["definition_id"]]["elements"] == ["水"]
    fresh = ming_property_evidence(
        c["palaces"],
        ming_branch=c["ming_gong"]["branch"],
        shen_branch=c["shen_gong"]["branch"],
    )
    fresh["definitions"]["qisha"]["elements"].append("水")
    fresh["positive_star_count_note"]["printed_count"] = 19
    assert c == before
    assert ming_property_evidence(
        c["palaces"],
        ming_branch=c["ming_gong"]["branch"],
        shen_branch=c["shen_gong"]["branch"],
    )["definitions"]["qisha"]["elements"] == ["火", "金"]


@pytest.mark.parametrize(
    "branch,steps,opposite,trine",
    [
        ("丑", 1, False, False),
        ("辰", 4, False, True),
        ("午", 6, True, False),
        ("申", 8, False, True),
    ],
)
def test_observed_geometry_does_not_define_the_source_encounter_word(
    branch, steps, opposite, trine
):
    p = [
        dict(
            name="命宫",
            ganzhi="甲子",
            stars_detail=[
                dict(name="紫微", mutagen=None),
                dict(name="廉贞", mutagen="化禄"),
            ],
        ),
        dict(
            name="财帛宫",
            ganzhi="甲" + branch,
            stars_detail=[dict(name="七杀", mutagen=None)],
        ),
    ]
    r = contextual_readings(p, ming_branch="子", shen_branch="卯")["qisha"]
    assert (r["separation_steps"], r["opposite_palace"], r["trine"]) == (
        steps,
        opposite,
        trine,
    )
    assert r["condition_match"] is None


@pytest.mark.parametrize("profile", ["iztro_2_5_8", "quanshu_v2_excerpt"])
def test_real_chart_can_satisfy_career_and_shen_premises_together(profile):
    # Conditional regression: this date is lunar 甲子年三月初六 in HKO.
    # Neither source phrase becomes a claim about a real person's career.
    r = calculate_ziwei_birth(
        create_person_info(
            1984,
            4,
            6,
            4,
            gender="男",
            birth_timezone="Asia/Shanghai",
            use_true_solar_time=False,
        ),
        rule_profile=profile,
    )
    c = r["ziwei_birth"]
    e = c["ming_textual_properties"]["conditional_readings"]["lianzhen"]
    assert c["lunar_date"] == dict(year=1984, month=3, day=6, is_leap_month=False)
    assert c["ming_gong"]["branch"] == "寅" and c["shen_gong"]["branch"] == "午"
    assert e["natal_palace_name"] == "官禄宫" and e["natal_branch"] == "午"
    assert e["at_career_palace"] and e["at_shen_branch"] and not e["at_ming_branch"]
    assert e["applicable_terms_given_selected_reading"] == ["官祿主", "次桃花"]


def test_actual_run_rejects_an_invented_applied_condition():
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    request = spec.request_model.model_validate(
        dict(
            birth_year=1984,
            birth_month=3,
            birth_day=15,
            birth_hour=12,
            gender="男",
            birth_timezone="Asia/Shanghai",
            use_true_solar_time=False,
        )
    )
    payload = execute_tool(spec, request)
    receipt = payload["run_metadata"]

    def claim(value):
        return CalculationClaim(
            path="ziwei_birth.ming_textual_properties.conditional_readings.qisha.condition_match",
            value=value,
            run_id=receipt["run_id"],
            business_output_sha256=receipt["business_output_sha256"],
        )

    assert (
        verify_calculation_claims(payload, [claim(None)])["status"]
        == "verified_structured_facts"
    )
    assert verify_calculation_claims(payload, [claim(True)])["status"] == "rejected"


@pytest.mark.parametrize("view", ["ming_symbolism", "contextual_symbolism"])
@pytest.mark.parametrize("gender", ["男", "未知"])
def test_sources_and_conditions_survive_three_surfaces_with_verified_same_run_pages(
    view, gender, monkeypatch, capsys
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    fields = evidence_views(spec)[view]["fields"]
    inputs = dict(
        birth_year=1984,
        birth_month=3,
        birth_day=15,
        birth_hour=12,
        gender=gender,
        birth_timezone="Asia/Shanghai",
        use_true_solar_time=False,
    )
    opts = dict(
        as_of="2026-10-22T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
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

    async def call():
        async with Client(create_mcp_app(families="metaphysics")) as client:
            r = await client.call_tool(
                "ziwei_birth", {**inputs, **opts}, raise_on_error=False
            )
            assert not r.is_error, r.content
            if view == "contextual_symbolism":
                return await verified_inline_business(client, r.structured_content)
            payload = r.structured_content
            assert len(json.dumps(payload, ensure_ascii=False)) <= 8192
            if "result_delivery" not in payload:
                return payload
            ref = payload["result_delivery"]
            uri = ref["first_page_uri"]
            pieces = []
            while uri:
                page = json.loads((await client.read_resource(uri))[0].text)
                pieces.append(page["text"])
                uri = page["next_uri"]
            raw = "".join(pieces)
            assert hashlib.sha256(raw.encode()).hexdigest() == ref["sha256"]
            full = json.loads(raw)
            assert_same_run_receipt(
                payload["run_metadata"],
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
    code = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert code == 0, cli
    assert rest.status_code == 200, rest.text
    bodies = [
        {k: v for k, v in r.items() if k not in ("run_metadata", "result_delivery")}
        for r in (rest.json(), native, cli)
    ]
    assert bodies[0] == bodies[1] == bodies[2]
    e = bodies[0]["ziwei_birth"]["ming_textual_properties"]
    assert e["conditional_readings"]["qisha"]["condition_match"] is None
    if view == "ming_symbolism":
        assert len(e["definitions"]) == 47 and len(e["occurrences"]) == (
            48 if gender == "男" else 38
        )


@pytest.mark.parametrize("birth_year", [None, 1933])
def test_complete_default_reading_survives_the_same_budget_on_three_surfaces(
    monkeypatch, capsys, birth_year
):
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    spec = next(s for s in CATALOG if s.key == "ziwei_birth")
    fields = suggested_fields(spec)
    inputs = {**example_input(spec), "rule_profile": "quanshu_v2_excerpt"}
    if birth_year is not None:
        inputs["birth_year"] = birth_year
    opts = dict(
        as_of="2026-10-15T12:00:00+08:00",
        fields=fields,
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=8192,
    )
    client = TestClient(api.app)
    response = client.post(
        "/api/cn/ziwei/birth",
        json=inputs,
        params=[
            ("as_of", opts["as_of"]),
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
            ("response_char_limit", "8192"),
            ("compact", "true"),
            *[("fields", f) for f in fields],
        ],
    )
    assert response.status_code == 200, response.text

    async def native_call():
        async with Client(create_mcp_app(families="metaphysics")) as c:
            r = await c.call_tool(
                "ziwei_birth", {**inputs, **opts}, raise_on_error=False
            )
            assert not r.is_error, r.content
            await verified_inline_business(c, r.structured_content)
            return r.structured_content

    native = asyncio.run(native_call())
    args = ["ziwei_birth"]
    for k, v in inputs.items():
        args += ["--" + k.replace("_", "-"), str(v)]
    args += [
        "--as-of",
        opts["as_of"],
        "--strict-fields",
        "--no-include-snapshot-text",
        "--compact",
        "--response-char-limit",
        "8192",
        "--fields",
        *fields,
    ]
    capsys.readouterr()
    code = run(args)
    cli = json.loads(capsys.readouterr().out)
    assert code == 0, cli
    bodies = []
    for p in (response.json(), native, cli):
        assert len(json.dumps(p, ensure_ascii=False, separators=(",", ":"))) <= 8192
        reading = p["ziwei_birth"]["reading_view"]
        assert (
            len(reading["palaces"]) == 12
            and sum(len(x["stars"]) for x in reading["palaces"]) == 67
        )
        if "result_delivery" in p:
            ref = p["result_delivery"]
            assert "run_metadata.runtime" in ref["deferred_fields"]
            assert set(ref["deferred_fields"]) <= {
                "run_metadata.runtime",
                "run_metadata.provenance",
                "run_metadata.determinism",
                "run_metadata.calculation_evidence",
            }
            chunks = []
            offset = 0
            while True:
                q = client.get(
                    f"/api/results/{ref['result_id']}/pages", params={"offset": offset}
                )
                assert q.status_code == 200, q.text
                page = q.json()
                chunks.append(page["text"])
                offset = page["next_offset"]
                if offset is None:
                    break
            text = "".join(chunks)
            assert hashlib.sha256(text.encode()).hexdigest() == ref["sha256"]
            full = json.loads(text)
            assert_same_run_receipt(
                p["run_metadata"],
                full["run_metadata"],
                deferred_fields=ref["deferred_fields"],
            )
            assert {
                k: v
                for k, v in p.items()
                if k not in ("run_metadata", "result_delivery")
            } == {k: v for k, v in full.items() if k != "run_metadata"}
        bodies.append(
            {k: v for k, v in p.items() if k not in ("run_metadata", "result_delivery")}
        )
    assert bodies[0] == bodies[1] == bodies[2]
