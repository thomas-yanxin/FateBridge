"""Source durations and day command must not manufacture hidden roots or labels."""

import asyncio
import gzip
import hashlib
import inspect
import json
import types
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.classical_passage import SOURCE as PASSAGE_SOURCE
from fatebridge.core.month_duty_reference import build_month_duty_reference
from fatebridge.utils.data import BRANCH_HIDDEN_STEMS
from scripts.audit_bazi_month_duty_sources import audit, transcribe
from scripts.sealed_bazi_runtime import replay
from tests.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
    rest,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_month_duty_sources_v1"
DATA = ROOT / "src/fatebridge/data/bazi_month_duty_sources_v1.json"


def chart(branch="寅"):
    return {
        "year": ("甲", "子"),
        "month": ("丙", branch),
        "day": ("戊", "辰"),
        "hour": ("庚", "申"),
    }


def test_complete_24_month_rows_and_all69_durations_match_captured_full_chapter():
    result = audit()
    assert (
        result["source_paragraphs"],
        result["source_month_rows"],
        result["duration_claims"],
    ) == (13, 24, 69)
    assert all(r["all_transcribed_claims_match_captured_text"] for r in result["rows"])
    assert [
        (r["branch"], r["literal_duration_sum"])
        for r in result["nominal_month_totals_not_thirty"]
    ] == [("酉", 32), ("子", 26)]
    assert (result["annual_computed_literal_sum"], result["annual_stated_sum"]) == (
        380,
        360,
    )
    assert not result["duty_calendar_profile_adopted"]
    assert result["source_scan_collation_for_digital_text"] == "not_completed"
    assert DATA.read_bytes() == (FIXTURE / "source-layers-v3.json").read_bytes()


def test_original_failed_anchor_and_literal_soil_identity_corrections_are_preserved():
    first = json.loads((FIXTURE / "source-layers.json").read_text())
    preflight = json.loads((FIXTURE / "source-preflight-first.json").read_text())
    current = json.loads(DATA.read_text())
    assert not preflight["passed"]
    assert (
        first["sanming_critique"]["anchor"]
        not in first["sanming_critique"]["source_text"]
    )
    assert (
        current["sanming_critique"]["anchor"]
        in current["sanming_critique"]["source_text"]
    )
    assert first["profiles"] == current["profiles"]
    assert (
        first["sanming_critique"]["source_text"]
        == current["sanming_critique"]["source_text"]
    )
    assert current["annual_literal_claim"]["groups"][-1]["source_names"] == ["戊", "已"]
    assert (
        "All twelve literal month sections"
        in (FIXTURE / "source-auditor-first-failure.log").read_text()
    )
    prose = current["profiles"][0]["source_text"]
    assert "八月，建酉" in prose
    assert len(transcribe(prose, prose=True)) == 12
    with pytest.raises(ValueError, match="All twelve"):
        transcribe(prose.replace("八月，建酉", "缺一月"), prose=True)


@pytest.mark.parametrize("branch", list("寅卯辰巳午未申酉戌亥子丑"))
def test_each_month_retains_source_order_and_unknowns_without_expanding_roots(branch):
    pillars = chart(branch)
    before, roots = deepcopy(pillars), deepcopy(BRANCH_HIDDEN_STEMS)
    evidence = build_month_duty_reference(pillars)
    assert pillars == before and BRANCH_HIDDEN_STEMS == roots
    assert evidence["conventional_month_hidden_stems"] == list(roots[branch])
    assert evidence["effective_command_status"] == "not_adjudicated"
    assert evidence["calculation_effect"] == "none"
    assert evidence["annual_duration_arithmetic"]["matches"] is False
    for layer in evidence["duration_source_layers"]:
        assert layer["calendar_mapping_status"] == "not_adopted"
        assert layer["selected_duty_stem"] is None
        assert not layer["chronological_order_adjudicated"]
        for claim in layer["claims"]:
            stem = claim["canonical_stem"]
            if stem is None:
                assert (
                    claim["visible_positions"] is None
                    and claim["hidden_positions"] is None
                )
                assert claim["source_name"][0] in "艮坤已"
            else:
                assert claim["visible_positions"] == [
                    p for p in ("year", "month", "day", "hour") if pillars[p][0] == stem
                ]
                assert all(
                    row["hidden_rank"] == roots[row["branch"]].index(stem)
                    for row in claim["hidden_positions"]
                )
    if branch == "卯":
        assert evidence["duration_source_layers"][1][
            "source_stems_outside_month_hidden_catalog"
        ] == ["甲", "癸"]
        assert evidence["conventional_month_hidden_stems"] == ["乙"]


def test_returned_metadata_mutations_cannot_contaminate_the_cached_source():
    one = build_month_duty_reference(chart())
    kept = deepcopy(one)
    one["sources"][0]["pdf_pages"].append(-1)
    one["duration_source_layers"][0]["claims"][0]["days"] = -1
    one["ditian_original_note"]["month_ranges_as_printed"][0]["stem"] = "己"
    assert build_month_duty_reference(chart()) == kept


def test_nominal_source_identity_cannot_be_confused_with_effective_duty():
    value = build_natal_evidence(chart())["month_command"]["intra_month_duty"]
    assert (
        value["status"] == "not_adjudicated"
        and value["selected_stem"] is None
        and value["rule_profile"] is None
    )
    source = value["source_reference"]
    assert [c["days"] for c in source["duration_source_layers"][0]["claims"]] == [
        5,
        5,
        20,
    ]
    assert [c["days"] for c in source["duration_source_layers"][1]["claims"]] == [
        7,
        5,
        18,
    ]
    assert [
        c["stem"] for c in source["ditian_original_note"]["month_ranges_as_printed"]
    ] == ["戊", "丙", "甲"]
    ids = {s["id"] for s in source["sources"]}
    assert source["source_critique"]["source_id"] in ids
    assert source["ditian_ren_commentary"]["source_id"] in ids
    assert source["ditian_original_note"]["source_id"] in ids
    assert PASSAGE_SOURCE["pdf_pages"] == [197, 198, 199, 200, 215, 216]
    assert PASSAGE_SOURCE["printed_pages"] == [55, 56, 57, 58, 73, 74]


def test_all314_old_source_receipts_preserve_every_prior_evidence_value():
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
            _historical_all314_old_source_receipts_preserve_every_prior_evidence_value
        )
        + "\n_historical_all314_old_source_receipts_preserve_every_prior_evidence_value()\nprint('{}')"
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


def _historical_all314_old_source_receipts_preserve_every_prior_evidence_value():
    archive = json.loads(
        gzip.decompress((FIXTURE / "before-source.json.gz").read_bytes())
    )
    old_passage = types.ModuleType("_month_duty_old_passage")
    exec(
        compile(
            archive["src/fatebridge/core/classical_passage.py"],
            "old_passage.py",
            "exec",
        ),
        old_passage.__dict__,
    )
    old = types.ModuleType("_month_duty_old_evidence")
    exec(
        compile(
            archive["src/fatebridge/core/bazi_evidence.py"], "old_evidence.py", "exec"
        ),
        old.__dict__,
    )
    old.build_passage_evidence = old_passage.build_passage_evidence
    old.RULESETS = [
        deepcopy(old_passage.SOURCE) if s["id"] == old_passage.SOURCE["id"] else s
        for s in old.RULESETS
    ]
    report_path = ROOT / "docs/validation/bazi-source-corpus-first-v4.json.gz"
    assert (
        hashlib.sha256(report_path.read_bytes()).hexdigest()
        == Path(str(report_path) + ".sha256").read_text().strip()
    )
    rows = json.loads(gzip.decompress(report_path.read_bytes()))["groups"]
    count = 0
    for group in rows.values():
        for row in group["rows"]:
            pillars = dict(
                zip(("year", "month", "day", "hour"), map(tuple, row["pillars"]))
            )
            strength = {
                "strength_level": row["actual_strength"],
                "assessment": row["assessment"],
            }
            current = build_natal_evidence(pillars, strength)
            previous = old.build_natal_evidence(pillars, strength)
            current["month_command"]["intra_month_duty"].pop("source_reference")
            for source in [
                current["classical_passage"]["source"],
                *current["rulesets"],
            ]:
                if source["id"] == old_passage.SOURCE["id"]:
                    source["pdf_pages"].remove(200)
                    source["printed_pages"].remove(58)
            assert current == previous, row["id"]
            count += 1
    assert count == 314


@pytest.mark.parametrize(
    "topic",
    [
        "birth",
        "career",
        "wealth",
        "health",
        "children",
        "education",
        "personality",
        "relatives",
        "marriage",
        "romance",
    ],
)
def test_month_source_layers_match_rest_native_mcp_cli_for_all_ten_outputs(
    topic, rest, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    prefix = "bazi_birth" if topic == "birth" else topic + "_analysis"
    path = (
        prefix
        + (
            ".structure_profile.evidence_chain"
            if topic == "birth"
            else ".evidence_chain"
        )
        + ".month_command.intra_month_duty"
    )
    args = inputs(spec)
    flags = {"fields": [path], "strict_fields": True, "include_snapshot_text": False}
    response = rest.post(spec.rest_path, json=args, params=flags)
    protocol = asyncio.run(native(spec, {**args, **flags}))
    code, local = call_cli(
        spec,
        args,
        tmp_path,
        capsys,
        flags=["--response-char-limit", "0", "--strict-fields", "--fields", path],
    )
    assert response.status_code == 200 and code == 0 and not protocol.is_error
    assert (
        business(response.json())
        == business(local)
        == business(protocol.structured_content)
    )
    value = response.json()[prefix]
    chain = (
        value["structure_profile"]["evidence_chain"]
        if topic == "birth"
        else value["evidence_chain"]
    )
    duty = chain["month_command"]["intra_month_duty"]
    assert (
        duty["selected_stem"] is None
        and duty["source_reference"]["calculation_effect"] == "none"
    )
    assert len(duty["source_reference"]["duration_source_layers"]) == 2
