"""A scanned duration witness must never become an adopted duty or hidden root."""

import asyncio
import gzip
import inspect
import json
import types
from copy import deepcopy

import pytest

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.month_duty_reference import build_month_duty_reference
from fatebridge.core.month_duty_scan_reference import build_month_duty_scan_reference
from fatebridge.utils.data import BRANCH_HIDDEN_STEMS
from scripts.audit_bazi_month_duty_scan import (
    DATA,
    FIXTURE,
    ROOT,
    audit,
    compare_claims,
)
from scripts.sealed_bazi_runtime import replay
from tests.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)
from tests.test_bazi_year_contract import TOPICS


def chart(branch="寅"):
    return dict(
        year=("己", "午"), month=("丙", branch), day=("戊", "辰"), hour=("庚", "申")
    )


def test_all24_scan_rows_and69_numbers_keep_printed_arithmetic_disagreements():
    result = audit()
    assert (result["month_rows"], result["duration_claims"]) == (24, 69)
    assert result["duration_value_differences"] == []
    assert [
        (r["branch"], r["literal_duration_sum"])
        for r in result["nominal_month_totals_not_thirty"]
    ] == [("酉", 32), ("子", 26)]
    assert (result["annual_computed_literal_sum"], result["annual_stated_sum"]) == (
        380,
        360,
    )
    assert len(result["glyph_reading_differences"]) == 6
    assert not result["duty_calendar_profile_adopted"]
    assert not result["full_goal_complete"]
    assert result["independent_expert_acceptance"] == "not_completed"
    assert result["real_world_predictive_validity"] == "not_tested"


def test_source_differences_are_retained_without_a_must_agree_gate():
    old = [{"source_name": "辛", "days": 20}, {"source_name": "已土", "days": 7}]
    new = [{"source_name": "辛", "days": 18}, {"source_name": "己土", "days": 9}]
    before = deepcopy((old, new))
    durations, glyphs = compare_claims(
        old, new, profile="synthetic_control", branch="酉", pages=[70]
    )
    assert [(r["digital_days"], r["scanned_days"]) for r in durations] == [
        (20, 18),
        (7, 9),
    ]
    assert glyphs[0]["digital"] == "已土" and glyphs[0]["scanned_reading"] == "己土"
    assert (old, new) == before


@pytest.mark.parametrize("branch", list("寅卯辰巳午未申酉戌亥子丑"))
def test_each_scanned_month_names_actual_stems_without_inventing_roots_or_dates(branch):
    pillars = chart(branch)
    before, roots = deepcopy(pillars), deepcopy(BRANCH_HIDDEN_STEMS)
    old_and_new = build_month_duty_reference(pillars)
    witness = old_and_new["scanned_witness"]
    assert pillars == before and BRANCH_HIDDEN_STEMS == roots
    assert (
        len(witness["duration_source_layers"])
        == len(old_and_new["duration_source_layers"])
        == 2
    )
    assert witness["effective_command_status"] == "not_adjudicated"
    assert (
        witness["selected_duty_stem"] is None
        and witness["calculation_effect"] == "none"
    )
    assert (
        witness["source"]["source_identity_with_shidian_underlying_copy"]
        == "not_established"
    )
    assert witness["annual_duration_arithmetic"]["computed_literal_sum"] == 380
    assert witness["annual_duration_arithmetic"]["matches_stated_total"] is False
    for layer in witness["duration_source_layers"]:
        assert layer["calendar_mapping_status"] == "not_adopted"
        assert layer["selected_duty_stem"] is None
        for claim in layer["claims"]:
            stem = claim["canonical_stem"]
            if stem is None:
                assert claim["source_name"] in {"艮土", "坤土"}
                assert claim["visible_positions"] is claim["hidden_positions"] is None
            else:
                assert claim["visible_positions"] == [
                    p for p in ("year", "month", "day", "hour") if pillars[p][0] == stem
                ]
                assert claim["hidden_positions"] == [
                    dict(pillar=p, branch=pillars[p][1], hidden_rank=i)
                    for p in ("year", "month", "day", "hour")
                    for i, s in enumerate(roots[pillars[p][1]])
                    if s == stem
                ]


def test_explicit_scanned_ji_does_not_rewrite_digital_yi_or_month_hidden_catalog():
    value = build_month_duty_reference(chart())
    digital = value["duration_source_layers"][1]["claims"][0]
    assert digital["source_name"] == "已土" and digital["canonical_stem"] is None
    scanned = value["scanned_witness"]["duration_source_layers"][1]["claims"][0]
    assert scanned["source_name"] == "己土" and scanned["canonical_stem"] == "己"
    assert scanned["visible_positions"] == ["year"]
    assert scanned["hidden_positions"] == [
        dict(pillar="year", branch="午", hidden_rank=1)
    ]
    assert value["conventional_month_hidden_stems"] == ["甲", "丙", "戊"]
    assert (
        "己"
        in value["scanned_witness"]["duration_source_layers"][1][
            "source_stems_outside_month_hidden_catalog"
        ]
    )
    assert value["effective_command_status"] == "not_adjudicated"


def test_a_printed_you_month_ding_claim_is_not_a_physical_ding_root():
    value = build_month_duty_reference(chart("酉"))
    table = value["scanned_witness"]["duration_source_layers"][1]
    assert [(r["source_name"], r["days"]) for r in table["claims"]] == [
        ("辛", 20),
        ("庚", 7),
        ("丁", 5),
    ]
    assert value["conventional_month_hidden_stems"] == ["辛"]
    assert all(r["pillar"] != "month" for r in table["claims"][2]["hidden_positions"])


def test_returned_scan_pages_claims_and_critique_cannot_mutate_the_source_cache():
    one = build_month_duty_scan_reference(chart())
    expected = deepcopy(one)
    one["source"]["chapter_original_pdf_pages"].append(-1)
    one["duration_source_layers"][0]["claims"][0]["days"] = -1
    one["annual_duration_arithmetic"]["groups"][0]["each_days"] = -1
    assert build_month_duty_scan_reference(chart()) == expected


def test_all349_previous_complete_evidence_objects_preserve_every_old_value():
    program = (
        """import gzip, hashlib, inspect, json, sys, types
from copy import deepcopy
from pathlib import Path
from fatebridge.core.bazi_evidence import build_natal_evidence
payload = json.load(sys.stdin)
ROOT = Path(payload["root"])
FIXTURE = ROOT / payload["fixture"]
DATA = ROOT / payload["data"]
"""
        + inspect.getsource(
            _historical_all349_previous_complete_evidence_objects_preserve_every_old_value
        )
        + "\n_historical_all349_previous_complete_evidence_objects_preserve_every_old_value()\nprint('{}')"
    )
    assert (
        replay(
            program,
            {
                "root": str(ROOT),
                "fixture": str(FIXTURE.relative_to(ROOT)),
                "data": str(DATA.relative_to(ROOT)),
            },
            ROOT,
        )
        == {}
    )


def _historical_all349_previous_complete_evidence_objects_preserve_every_old_value():
    before = json.loads(
        gzip.decompress((FIXTURE / "before-source.json.gz").read_bytes())
    )
    old_month = types.ModuleType("_scan_old_month_duty")
    exec(
        compile(
            before["src/fatebridge/core/month_duty_reference.py"],
            "old_month_duty.py",
            "exec",
        ),
        old_month.__dict__,
    )
    old_evidence = types.ModuleType("_scan_old_evidence")
    exec(
        compile(
            before["src/fatebridge/core/bazi_evidence.py"], "old_evidence.py", "exec"
        ),
        old_evidence.__dict__,
    )
    old_evidence.build_month_duty_reference = old_month.build_month_duty_reference
    corpus = json.loads(
        gzip.decompress(
            (
                ROOT / "docs/validation/bazi-grader-policy-source-corpus-v1.json.gz"
            ).read_bytes()
        )
    )
    count = 0
    for group in corpus["groups"].values():
        for row in group["rows"]:
            pillars = dict(
                zip(("year", "month", "day", "hour"), map(tuple, row["pillars"]))
            )
            strength = dict(
                strength_level=row["actual_strength"], assessment=row["assessment"]
            )
            current = build_natal_evidence(pillars, strength)
            current["month_command"]["intra_month_duty"]["source_reference"].pop(
                "scanned_witness"
            )
            assert current == old_evidence.build_natal_evidence(pillars, strength), row[
                "id"
            ]
            count += 1
    assert count == 349
    assert (ROOT / "src/fatebridge/data/bazi_month_duty_sources_v1.json").read_text(
        encoding="utf-8"
    ) == before["src/fatebridge/data/bazi_month_duty_sources_v1.json"]
    assert DATA.read_bytes() == (FIXTURE / "witness-first.json").read_bytes()


@pytest.mark.parametrize("topic", TOPICS)
def test_scan_witness_matches_actual_rest_native_mcp_cli_for_all_ten_tools(
    topic, rest, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    prefix = "bazi_birth" if topic == "birth" else topic + "_analysis"
    chain = prefix + (
        ".structure_profile.evidence_chain" if topic == "birth" else ".evidence_chain"
    )
    path = chain + ".month_command.intra_month_duty.source_reference.scanned_witness"
    payload = {
        **inputs(spec),
        "birth_year": 1990,
        "birth_month": 2,
        "birth_day": 15,
        "birth_hour": 10,
        "birth_timezone": "Asia/Shanghai",
        "gender": "男",
        "use_true_solar_time": False,
    }
    opts = dict(
        as_of=AS_OF,
        fields=[path],
        strict_fields=True,
        include_snapshot_text=False,
        response_char_limit=0,
    )
    http = rest.post(spec.rest_path, json=payload, params=opts)
    protocol = asyncio.run(native(spec, payload, **opts))
    code, cli = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=[
            "--response-char-limit",
            "0",
            "--strict-fields",
            "true",
            "--include-snapshot-text",
            "false",
            "--fields",
            path,
        ],
    )
    assert http.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(http.json()) == business(cli) == business(protocol.structured_content)
    )
    value = http.json()[prefix]
    evidence = (
        value["structure_profile"]["evidence_chain"]
        if topic == "birth"
        else value["evidence_chain"]
    )
    witness = evidence["month_command"]["intra_month_duty"]["source_reference"][
        "scanned_witness"
    ]
    assert witness["month_branch"] == "寅"
    assert witness["source"]["chapter_original_pdf_pages"] == list(range(66, 74))
    assert (
        witness["source"]["source_pdf_sha256"]
        == "af4a8ca65cc4dfdf63d6294adc7925a868214563d0d52664c7ba779b833db14a"
    )
    assert witness["annual_duration_arithmetic"]["computed_literal_sum"] == 380
    assert witness["annual_duration_arithmetic"]["matches_stated_total"] is False
    assert witness["selected_duty_stem"] is None
    assert witness["effective_command_status"] == "not_adjudicated"
    assert witness["independent_expert_review"] == "not_completed"
