"""Unknown relation coverage must not become positive classical conditions."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.api as api
from fatebridge.application.examples import suggested_fields
from fatebridge.application.projection import project_fields
from fatebridge.cli import run
from fatebridge.core.metaphysics.taiyi_conditions import (
    conditions_text,
    conjunction,
    five_general_conditions,
    update_conjunction,
)
from fatebridge.core.metaphysics.taiyi_year import cyclic_core, structural_patterns
from fatebridge.core.output_chinese import Taiyi
from fatebridge.core.output_taiyi_conditions import TaiyiConditionClause
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_taiyi_analysis
from fatebridge.services.tool_catalog import CATALOG
from scripts.audit_taiyi_condition_coverage import CORPUS, audit
from tests.test_taiyi_enclosures import resolve, transport_payload
from tests.test_taiyi_transports import _same_run_payload

TRUTH = json.loads((CORPUS / "truth-table.json").read_text())


def test_four_literal_notes_are_not_four_complete_charts_or_a_new_guan_rule():
    report = audit()
    assert report["selected_source_notes"] == 4
    assert (
        report["required_count_observations"]
        == report["matching_count_observations"]
        == 4
    )
    assert (
        report["required_center_observations"]
        == report["matching_center_observations"]
        == 4
    )
    assert report["literal_non_dispatch_readings_retained"] == 4
    assert report["supplementary_facsimile_images_verified"] == 5
    assert report["initial_expectations_unchanged_after_facsimile_check"] is True
    assert (
        report["synthetic_conjunction_cases"]
        == report["synthetic_conjunction_matches"]
        == 36
    )
    assert report["same_camp_guan_adjudicated"] is False
    assert report["whole_classic_acceptance_passed"] is False
    assert all(not r["annotation_absence_is_negative"] for r in report["rows"])


@pytest.mark.parametrize("case", TRUTH["two_inputs"] + TRUTH["three_inputs"])
def test_entire_frozen_synthetic_truth_table_and_layer_composition(case):
    assert conjunction(*case["values"]) is case["expected"]
    if len(case["values"]) == 2:
        a = {
            "five_generals": {"conditions_satisfied": case["values"][0]},
            "three_gates": {"conditions_satisfied": case["values"][1]},
        }
        update_conjunction(a)
        assert a["menju_jiangfa"] is case["expected"]
        assert a["five_generals"]["conditions_satisfied"] is case["values"][0]
        assert a["three_gates"]["conditions_satisfied"] is case["values"][1]


@pytest.mark.parametrize("values", [(), ("false",), (0,), (1,), ([],)])
def test_missing_or_coerced_logic_input_does_not_make_a_pass(values):
    with pytest.raises(ValueError):
        conjunction(*values)


def test_missing_core_and_partial_core_cannot_prove_absent_relations():
    for c in [None, {}, {"main_general": 5}]:
        a = five_general_conditions([], core=c)
        assert a["five_generals"]["conditions_satisfied"] is None
        assert a["five_generals"]["assessed_conditions_satisfied"] is True
        assert a["five_generals"]["same_core_coverage_checked"] is False
        assert all(
            r["satisfied"] is None and r["unassessed"]
            for r in a["five_generals"]["clauses"]
        )
        assert a["menju_jiangfa"] is None
    a = five_general_conditions([{"name": "击", "subject": "始击", "variant": "test"}])
    assert a["five_generals"]["conditions_satisfied"] is False
    assert a["menju_jiangfa"] is False
    assert a["five_generals"]["clauses"][1]["satisfied"] is None


def test_all_144_cores_keep_patterns_and_retain_both_unknowns_and_blockers():
    pending, withheld = 0, 0
    for yin in [False, True]:
        for ju in range(1, 73):
            c = cyclic_core(ju, yin=yin)
            old = json.loads(json.dumps(c, ensure_ascii=False))
            patterns = structural_patterns(c)
            previous = json.loads(json.dumps(patterns, ensure_ascii=False))
            a = five_general_conditions(patterns, core=c)
            assert c == old and patterns == previous
            f = a["five_generals"]
            unknowns = [u for clause in f["clauses"] for u in clause["unassessed"]]
            expected = sum(
                c[s + "_general"] == c[s + "_vice_general"] for s in ["main", "guest"]
            )
            assert len(unknowns) == expected
            pending += bool(unknowns)
            for u in unknowns:
                assert len(u["basis"]) == 2
                for fact in u["basis"]:
                    assert resolve({"core_board": c}, fact["field"]) == fact["value"]
            blockers = [b for clause in f["clauses"] for b in clause["blockers"]]
            if blockers:
                assert f["conditions_satisfied"] is False
            elif unknowns:
                assert f["conditions_satisfied"] is None
                withheld += 1
            else:
                assert f["conditions_satisfied"] is True
            assert f["assessed_conditions_satisfied"] is (not blockers)
            Taiyi.model_validate({"condition_assessment": a})
    # Software impact counts, never a source-conformance percentage.
    assert pending == 42 and withheld == 21


def test_partial_projection_retains_unknown_and_its_fact_paths():
    b = calculate_taiyi_analysis(**transport_payload("taiyi", 2020))["taiyi"]
    a = b["condition_assessment"]
    assert a["five_generals"]["conditions_satisfied"] is None
    assert a["three_gates"]["conditions_satisfied"] is True
    assert a["menju_jiangfa"] is None
    for field in [
        "five_generals.conditions_satisfied",
        "five_generals.assessed_conditions_satisfied",
        "five_generals.same_core_coverage_checked",
        "five_generals.clauses",
        "ruleset.coverage_policy",
        "menju_jiangfa",
    ]:
        Taiyi.model_validate(
            project_fields(
                {"taiyi": b},
                ["taiyi.condition_assessment." + field],
                strict_fields=True,
            )["taiyi"]
        )
    clause = a["five_generals"]["clauses"][2]
    for key in clause:
        TaiyiConditionClause.model_validate(
            project_fields({"clause": clause}, ["clause." + key], strict_fields=True)[
                "clause"
            ]
        )
    text = conditions_text(a)
    assert "主客大小将无相关：未定" in text
    for u in clause["unassessed"]:
        for f in u["basis"]:
            assert f"{f['field']}={f['value']}" in text
    with pytest.raises(ValidationError):
        TaiyiConditionClause.model_validate({"satisfied": "unknown"})


@pytest.mark.parametrize("mutation", ["drop_note", "declare_guan", "change_truth"])
def test_frozen_knowledge_cannot_be_changed_to_make_acceptance_pass(tmp_path, mutation):
    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target)
    p = target / (
        "truth-table.json" if mutation == "change_truth" else "center-notes.json"
    )
    d = json.loads(p.read_text())
    if mutation == "drop_note":
        d["records"].pop()
    elif mutation == "declare_guan":
        d["center_implies_guan"] = True
    else:
        d["two_inputs"][4]["expected"] = True
    p.write_text(json.dumps(d, ensure_ascii=False))
    with pytest.raises(ValueError, match="指纹"):
        audit(target)


@pytest.mark.parametrize("name", ["gujin3216-page78.jpg", "facsimile-check.json"])
def test_supplementary_facsimile_fingerprints_are_enforced(tmp_path, name):
    target = tmp_path / "corpus"
    shutil.copytree(CORPUS, target)
    (target / name).write_bytes(b"altered")
    with pytest.raises(ValueError, match="指纹"):
        audit(target)


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
def test_actual_rest_mcp_cli_keep_false_true_and_unknown_distinct(
    key, monkeypatch, capsys
):
    spec = next(s for s in CATALOG if s.key == key)
    fields = ["taiyi.condition_assessment"]
    api._reset_runtime_state_for_tests()
    monkeypatch.setattr(
        api,
        "API_KEY_AUTHENTICATOR",
        api.ApiKeyAuthenticator(header_name="X-API-Key", api_keys={}),
    )
    rest = {}
    with TestClient(api.app) as c:
        for year in [1906, 1922, 2020]:
            r = c.post(
                spec.rest_path,
                json=transport_payload(key, year),
                params=[
                    ("strict_fields", "true"),
                    ("response_char_limit", "0"),
                    ("fields", fields[0]),
                ],
            )
            assert r.status_code == 200, r.text
            rest[year] = r.json()["taiyi"]["condition_assessment"]

    async def mcp():
        out = {}
        async with Client(create_mcp_app()) as c:
            for year in rest:
                r = await c.call_tool(
                    spec.tool_name,
                    {
                        **transport_payload(key, year),
                        "fields": fields,
                        "strict_fields": True,
                        "include_snapshot_text": False,
                        "response_char_limit": 0,
                    },
                    raise_on_error=False,
                )
                assert not r.is_error, r
                out[year] = r.structured_content["taiyi"]["condition_assessment"]
        return out

    native = asyncio.run(mcp())
    for year, expected in [(1906, False), (1922, True), (2020, None)]:
        args = [key, "--strict-fields", "--no-use-true-solar-time", "--fields", *fields]
        for name, value in transport_payload(key, year).items():
            if name == "use_true_solar_time":
                continue
            args.extend(
                [
                    "--" + name.replace("_", "-"),
                    json.dumps(value) if isinstance(value, dict) else str(value),
                ]
            )
        assert run(args) == 0
        cli = json.loads(capsys.readouterr().out)["taiyi"]["condition_assessment"]
        assert rest[year] == native[year] == cli
        assert "conditions_satisfied" in cli["five_generals"]
        assert cli["five_generals"]["conditions_satisfied"] is expected
        assert cli["menju_jiangfa"] is expected


@pytest.mark.parametrize("key", ["taiyi", "sanshiunited"])
def test_default_budget_condition_view_keeps_all_requested_facts_and_unknowns(key):
    spec = next(s for s in CATALOG if s.key == key)
    view = "conditions" if key == "taiyi" else "taiyi_conditions"

    async def call():
        async with Client(create_mcp_app()) as c:
            for year in [1906, 1922, 2020]:
                r = await c.call_tool(
                    spec.tool_name,
                    {
                        **transport_payload(key, year),
                        "fields": suggested_fields(spec, view=view),
                        "strict_fields": True,
                        "include_snapshot_text": False,
                    },
                    raise_on_error=False,
                )
                await _same_run_payload(c, r, require_business_inline=True)
                a = r.structured_content["taiyi"]["condition_assessment"]
                if year == 2020:
                    assert a["five_generals"]["conditions_satisfied"] is None
                    assert a["five_generals"]["clauses"][2]["unassessed"]

    asyncio.run(call())
