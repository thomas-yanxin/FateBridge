"""Daily/intrinsic/branch distinctions and same-run faithful delivery."""

import copy
import hashlib
import importlib.util
import json
import shutil
from dataclasses import replace
from itertools import product
from pathlib import Path

import pytest
from fastmcp import Client
from pydantic import ValidationError

import fatebridge.application.execution as execution
from fatebridge.application.examples import evidence_views
from fatebridge.core.metaphysics.jinkou_stems import (
    build_stem_relations,
    ganzhi_pair_facts,
    wuzidun_stem,
)
from fatebridge.core.metaphysics.ren_evidence import xun_dun_stems
from fatebridge.core.output_jinkou_stems import JinkouStemRelations
from fatebridge.mcp_server import create_mcp_app
from fatebridge.services.metaphysics import calculate_jinkou_analysis
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims
from tests.fixtures.mcp_result_delivery import assert_same_run_receipt
from tests.support.transports import AS_OF, SPECS, business, rest, surface_calls

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "stem_audit", ROOT / "scripts/ren/audit_jinkou_stems.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
REFERENCE = AUDIT.reference()
PAYLOAD = dict(
    analysis_year=2026,
    analysis_month=2,
    analysis_day=20,
    analysis_hour=4,
    analysis_timezone="Asia/Shanghai",
    use_true_solar_time=False,
    di_fen="午",
)


def test_literal_denominators_and_derived_checks_remain_separate():
    result = AUDIT.audit()
    assert len(result["literal_wuzi_groups"]) == 5
    assert (
        result["expanded_dun_match_count"] == len(result["expanded_dun_checks"]) == 120
    )
    assert result["literal_partial_example_count"] == 1
    assert len(result["literal_example_anchor_checks"]) == 2
    assert (
        len(result["directed_clause_checks"]) == 4
        and len(result["literal_stem_pair_checks"]) == 5
    )
    assert result["written_stem_matches"] == len(result["written_ganzhi_examples"]) == 6
    assert (
        result["written_branch_harmony_count"] == 1
        and result["written_same_xun_count"] == 3
    )
    assert result["synthetic_contexts"] == result["synthetic_context_matches"] == 1440
    assert result["derived_rule_checks"] == result["derived_rule_matches"] == 5760
    assert (
        result["all_sexagenary_pair_checks"]
        == result["all_sexagenary_pair_matches"]
        == 3600
    )
    assert not result["failures"] and result["selected_stem_checks_passed"]
    assert result["classical_acceptance_passed"] is result["goal_complete"] is False


@pytest.mark.parametrize("change", ["edit", "missing", "extra"])
def test_frozen_sources_cannot_silently_rewrite合_as_double_harmony(tmp_path, change):
    target = tmp_path / "corpus"
    shutil.copytree(AUDIT.CORPUS, target)
    if change == "edit":
        p = target / "reference.json"
        data = json.loads(p.read_text())
        data["written_ganzhi_examples"][0]["derived_branch_harmony"] = True
        p.write_text(json.dumps(data))
    elif change == "missing":
        (target / "source-pages.pdf").unlink()
    else:
        (target / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Frozen stem-reference"):
        AUDIT.reference(target)


def test_missing_clause_cannot_shrink_the_5760_required_checks(monkeypatch):
    import fatebridge.core.metaphysics.jinkou_stems as implementation

    original = implementation.build_stem_relations

    def missing(**kwargs):
        result = original(**kwargs)
        result["rule_evaluations"].pop()
        return result

    monkeypatch.setattr(implementation, "build_stem_relations", missing)
    result = AUDIT.audit()
    assert not result["selected_stem_checks_passed"]
    assert (
        result["derived_rule_checks"] == 5760 and result["derived_rule_matches"] == 4320
    )
    assert result["failures"]


def test_all_symbolic_contexts_are_typed_without_pretending_full_identity_proof():
    for day, god, general in product(
        REFERENCE["stems"], REFERENCE["branches"], REFERENCE["branches"]
    ):
        JinkouStemRelations.model_validate(
            build_stem_relations(
                day_stem=day, rows=AUDIT.symbolic_rows(REFERENCE, day, god, general)
            )
        )


def test_last_written_pair_is_continued_cycle_not_a_replacement_for_same_day_子():
    assert wuzidun_stem("甲", "子") == "甲" and wuzidun_stem("乙", "子") == "丙"
    last = ganzhi_pair_facts("辛未", "丙子")
    assert last["stem_harmony_matched"] and not last["branch_harmony_matched"]
    assert not last["same_ganzhi_xun"] and last["transformation_confirmed"] is None


def test_stem_harmony_does_not_erase_control_before_transformation_is_adjudicated():
    result = build_stem_relations(
        day_stem="甲", rows=AUDIT.symbolic_rows(REFERENCE, "甲", "丑", "午")
    )
    assert result["god"]["dun_stem"] == "乙" and result["general"]["dun_stem"] == "庚"
    assert result["relation"] == "将干克神干"
    assert result["pair_facts"]["stem_harmony_matched"]
    assert result["pair_facts"]["candidate_element"] == "金"
    assert result["pair_facts"]["transformation_confirmed"] is None
    assert result["god"]["dun_element"] == "木"


def test_jinkou_wuzi_stem_is_independent_of_liuren_day_xun_stem():
    assert wuzidun_stem("乙", "午") == "壬"
    assert xun_dun_stems("乙丑")["午"] == "庚"
    assert xun_dun_stems("乙卯")["午"] == "戊"
    assert REFERENCE["six_yi_example"]["god_intrinsic_ganzhi"] == "丙午"


@pytest.mark.parametrize(
    "bad", ["bad_day", "bad_branch", "bad_pair", "wrong_stem", "wrong_intrinsic"]
)
def test_invalid_or_disagreeing_stem_inputs_are_rejected(bad):
    if bad == "bad_day":
        with pytest.raises(ValueError):
            wuzidun_stem("甲子", "子")
    elif bad == "bad_branch":
        with pytest.raises(ValueError):
            wuzidun_stem("甲", "甲")
    elif bad == "bad_pair":
        with pytest.raises(ValueError):
            ganzhi_pair_facts("甲丑", "己巳")
    else:
        rows = AUDIT.symbolic_rows(REFERENCE, "乙", "午", "卯")
        rows[1]["dun_stem" if bad == "wrong_stem" else "intrinsic_ganzhi"] = (
            "丙" if bad == "wrong_stem" else "己巳"
        )
        with pytest.raises(ValueError):
            build_stem_relations(day_stem="乙", rows=rows)


@pytest.mark.parametrize("project", [False, True])
def test_three_ports_keep_intrinsic_daily_and_branch_relations_distinct(
    project, surface_calls
):
    spec = SPECS["jinkou"]
    fields = [
        "jinkou.stem_relations",
        "jinkou.rows",
        "jinkou.motions",
        "jinkou.overview",
    ]
    params = [("as_of", AS_OF), ("response_char_limit", "0")]
    flags = ["--response-char-limit", "0"]
    options = {}
    if project:
        params += [("fields", f) for f in fields] + [
            ("strict_fields", "true"),
            ("include_snapshot_text", "false"),
        ]
        flags += [
            "--fields",
            *fields,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ]
        options.update(fields=fields, strict_fields=True, include_snapshot_text=False)
    http, protocol, code, cli = surface_calls(
        spec, PAYLOAD, params=params, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    for body in (http.json(), protocol.structured_content, cli):
        spec.output_model.model_validate(body)
        board = body["jinkou"]
        stems = board["stem_relations"]
        assert stems["guishen_intrinsic_ganzhi"] == "丙午"
        assert (
            stems["god"]["dun_ganzhi"] == "壬午" and stems["god"]["dun_element"] == "水"
        )
        assert (
            stems["general"]["dun_ganzhi"] == "己卯"
            and stems["general"]["dun_element"] == "土"
        )
        assert (
            stems["relation"] == "将干克神干" and stems["motion_analogue"] == "财动同类"
        )
        assert [m["name"] for m in board["motions"]] == ["妻动"]
        assert (
            stems["god"]["branch_element"] == "火"
            and not stems["god"]["branch_si_da_kong"]
        )
        assert board["overview"]["xun_head"] == "甲子"
        assert (
            stems["pair_facts"]["left_ganzhi_xun_head"]
            == stems["pair_facts"]["right_ganzhi_xun_head"]
            == "甲戌"
        )
        assert (
            stems["pair_facts"]["same_ganzhi_xun"]
            and stems["pair_facts"]["transformation_confirmed"] is None
        )
        if not project:
            assert "贵神固有干支：丙午；当日神干壬午、将干己卯" in body["snapshot_text"]
            assert (
                next(
                    t
                    for t in board["rule_trace"]
                    if t["rule_id"] == "jinkou.dun_stem_relations"
                )["result"]
                == stems
            )
    assert "jinkou.stem_relations" in evidence_views(spec)["core"]["fields"]


FAULTS = [
    "row_god_dun",
    "row_general_dun",
    "row_god_branch",
    "row_intrinsic",
    "dun_element",
    "compound",
    "role",
    "relation",
    "motion",
    "both",
    "same_xun",
    "candidate",
    "transformation",
    "du_he",
    "full_claim",
    "numeric_claim",
    "missing_rule",
    "duplicate_rule",
    "rule_direction",
    "pair_left",
]


def corrupt(payload, fault):
    bad = copy.deepcopy(payload)
    b = bad["jinkou"]
    s = b["stem_relations"]
    if fault == "row_god_dun":
        b["rows"][1]["dun_stem"] = "丙"
    elif fault == "row_general_dun":
        b["rows"][2]["dun_stem"] = "甲"
    elif fault == "row_god_branch":
        b["rows"][1]["content"] = "巳"
    elif fault == "row_intrinsic":
        b["rows"][1]["intrinsic_ganzhi"] = "甲午"
    elif fault == "dun_element":
        s["god"]["dun_element"] = "火"
    elif fault == "compound":
        s["god"]["dun_ganzhi"] = "壬申"
    elif fault == "role":
        s["god"]["position"] = "将神"
    elif fault == "relation":
        s["relation"] = "神干生将干"
    elif fault == "motion":
        s["motion_analogue"] = "贼动同类"
    elif fault == "both":
        s["pair_facts"]["both_harmonies_matched"] = True
    elif fault == "same_xun":
        s["pair_facts"]["same_ganzhi_xun"] = False
    elif fault == "candidate":
        s["pair_facts"]["candidate_element"] = "火"
    elif fault == "transformation":
        s["pair_facts"]["transformation_confirmed"] = True
    elif fault == "du_he":
        s["pair_facts"]["du_he"] = False
    elif fault == "full_claim":
        s["complete_classical_conformance"] = True
    elif fault == "numeric_claim":
        s["complete_classical_conformance"] = 0
    elif fault == "missing_rule":
        s["rule_evaluations"].pop()
    elif fault == "duplicate_rule":
        s["rule_evaluations"][0]["id"] = s["rule_evaluations"][1]["id"]
    elif fault == "rule_direction":
        s["rule_evaluations"][0]["source_position"] = "将神"
    else:
        s["pair_facts"]["left_ganzhi"] = "丙午"
    return bad


@pytest.mark.parametrize("fault", FAULTS)
@pytest.mark.parametrize("project", [False, True])
def test_corrupt_complete_business_facts_fail_before_projection(
    fault, project, monkeypatch, surface_calls
):
    spec = SPECS["jinkou"]
    valid = calculate_jinkou_analysis(**PAYLOAD)
    execution.validate_output(spec, valid)
    bad = corrupt(valid, fault)
    with pytest.raises(ValidationError):
        spec.output_model.model_validate(bad)
    original = execution.execute_spec

    def broken(actual, request):
        if actual.key == spec.key:
            actual = replace(
                actual, bind=lambda _: (lambda: copy.deepcopy(bad), (), {})
            )
        return original(actual, request)

    monkeypatch.setattr(execution, "execute_spec", broken)
    options = {}
    params = dict(as_of=AS_OF, response_char_limit=0)
    flags = ["--response-char-limit", "0"]
    if project:
        params.update(fields="analysis_type", strict_fields="true")
        options.update(fields=["analysis_type"], strict_fields=True)
        flags += ["--fields", "analysis_type", "--strict-fields", "true"]
    http, protocol, code, out = surface_calls(
        spec, PAYLOAD, params=params, options=options, flags=flags, cli_first=False
    )
    assert http.status_code == 500 and protocol.is_error and code == 1
    assert out["error_code"] == "internal_error"


@pytest.mark.parametrize(
    "field",
    [
        "god.dun_stem",
        "rule_evaluations",
        "pair_facts.candidate_element",
        "pair_facts.transformation_confirmed",
        "complete_classical_conformance",
    ],
)
def test_sparse_objects_keep_false_null_and_complete_rule_arrays(field, surface_calls):
    spec = SPECS["jinkou"]
    path = "jinkou.stem_relations." + field
    http, protocol, code, cli = surface_calls(
        spec,
        PAYLOAD,
        params=dict(
            as_of=AS_OF,
            response_char_limit=0,
            fields=path,
            strict_fields="true",
            include_snapshot_text="false",
        ),
        options={
            "fields": [path],
            "strict_fields": True,
            "include_snapshot_text": False,
        },
        flags=[
            "--response-char-limit",
            "0",
            "--fields",
            path,
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
        ],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    spec.output_model.model_validate(cli)


def test_section_export_and_receipt_do_not_replace_壬_with_intrinsic_丙(surface_calls):
    spec = SPECS["jinkou"]
    payload = {**PAYLOAD, "selected_sections": ["金口诀四位"]}
    http, protocol, code, cli = surface_calls(
        spec,
        payload,
        params=dict(as_of=AS_OF, response_char_limit=0),
        flags=["--response-char-limit", "0"],
        cli_first=False,
    )
    assert http.status_code == 200 and not protocol.is_error and code == 0
    assert (
        business(http.json()) == business(protocol.structured_content) == business(cli)
    )
    exported = cli["snapshot_export"]
    assert (
        exported["selected_sections"] == ["金口诀四位"]
        and "[起盘信息]" not in exported["export_text"]
    )
    assert "贵神固有干支：丙午；当日神干壬午、将干己卯" in exported["export_text"]
    receipt = cli["run_metadata"]
    claim = CalculationClaim(
        path="jinkou.stem_relations.god.dun_stem",
        value="壬",
        run_id=receipt["run_id"],
    )
    assert (
        verify_calculation_claims(cli, [claim])["status"] == "verified_structured_facts"
    )
    assert (
        verify_calculation_claims(cli, [claim.model_copy(update={"value": "丙"})])[
            "status"
        ]
        == "rejected"
    )


@pytest.mark.asyncio
async def test_published_first_view_reads_all_stem_evidence_from_one_run():
    contract = json.loads((ROOT / "docs/contracts/jinkou.json").read_text())
    async with Client(create_mcp_app()) as client:
        response = await client.call_tool(
            "jinkou",
            {
                **PAYLOAD,
                **contract["first_view"],
                "as_of": AS_OF,
                "response_char_limit": 6000,
            },
        )
        assert not response.is_error
        inline = response.structured_content
        reference = inline["result_delivery"]
        pieces = []
        uri = reference["first_page_uri"]
        while uri:
            page = json.loads((await client.read_resource(uri))[0].text)
            pieces.append(page["text"])
            uri = page["next_uri"]
    text = "".join(pieces)
    assert (
        len(pieces) > 1
        and hashlib.sha256(text.encode()).hexdigest() == reference["sha256"]
    )
    complete = json.loads(text)
    assert_same_run_receipt(
        inline["run_metadata"],
        complete["run_metadata"],
        deferred_fields=reference["deferred_fields"],
    )
    assert complete["jinkou"]["stem_relations"]["relation"] == "将干克神干"
