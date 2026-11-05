"""Source term identity cannot manufacture a duty, force or hidden root."""

import asyncio
from copy import deepcopy

import pytest

from fatebridge.core.month_duty_scan_reference import build_month_duty_scan_reference
from fatebridge.utils.data import BRANCH_HIDDEN_STEMS
from tests.bazi.test_bazi_year_contract import TOPICS
from tests.evaluation.test_agentic_nested_outputs import (
    AS_OF,
    SPECS,
    business,
    call_cli,
    inputs,
    native,
)
from tests.evaluation.test_agentic_nested_outputs import rest as _rest_fixture

# Re-export the actual fixture object; test arguments refer to this registration.
rest = _rest_fixture


def chart(branch="寅"):
    return dict(
        year=("己", "午"), month=("丙", branch), day=("戊", "辰"), hour=("庚", "申")
    )


def layer(pillars):
    return build_month_duty_scan_reference(pillars)["cross_chapter_identities"]


@pytest.mark.parametrize("branch", list("寅卯辰巳午未申酉戌亥子丑"))
def test_all_months_join_source_identity_and_actual_positions_without_rewriting_claims(
    branch,
):
    pillars = chart(branch)
    before, catalog = deepcopy(pillars), deepcopy(BRANCH_HIDDEN_STEMS)
    witness = build_month_duty_scan_reference(pillars)
    value = witness["cross_chapter_identities"]
    assert pillars == before and BRANCH_HIDDEN_STEMS == catalog
    assert value["month_branch"] == branch
    observations = value["month_term_observations"]
    assert len(observations) == (1 if branch in "寅申" else 0)
    assert value["selected_duty_stem"] is None
    assert value["effective_command_status"] == "not_adjudicated"
    assert value["calculation_effect"] == "none"
    for observation in observations:
        assert observation["chapter_only_canonical_stem"] is None
        stem = observation["cross_chapter_canonical_stem"]
        if stem:
            assert stem == "戊" and branch == "寅"
            assert observation["visible_positions"] == [
                p for p in pillars if pillars[p][0] == stem
            ]
            assert observation["hidden_positions"] == [
                dict(pillar=p, branch=pillars[p][1], hidden_rank=i)
                for p in pillars
                for i, s in enumerate(catalog[pillars[p][1]])
                if s == stem
            ]
        else:
            assert branch == "申" and observation["source_name"] == "坤土"
            assert (
                observation["visible_positions"]
                is observation["hidden_positions"]
                is None
            )
        original = witness["duration_source_layers"][0]["claims"][0]
        assert original["canonical_stem"] is None
        assert original["visible_positions"] is original["hidden_positions"] is None


def test_source_definition_has_actual_anchor_and_retains_conflicting_context():
    value = layer(chart())
    anchors = {a["id"]: a for a in value["anchors"]}
    gen, kun = value["identity_claims"]
    assert gen["canonical_stem"] == "戊"
    assert "即戊土也" in anchors[gen["definition_anchor_ids"][0]]["literal_quote"]
    assert anchors[gen["definition_anchor_ids"][0]]["original_pdf_pages"] == [17]
    assert kun["canonical_stem"] is None and kun["definition_anchor_ids"] == []
    assert "坤土庚金" in anchors["gui_shen_kun"]["literal_quote"]
    assert "若以戊生申己生卯" in anchors["soil_birth_dispute"]["literal_quote"]
    assert "足以破前說之偏" in anchors["yin_yang_critique"]["literal_quote"]
    assert value["independent_expert_review"] == "not_completed"


def test_gen_identity_is_not_a_duty_choice_and_does_not_relabel_ji_table():
    witness = build_month_duty_scan_reference(chart())
    prose, table = witness["duration_source_layers"]
    observation = witness["cross_chapter_identities"]["month_term_observations"][0]
    assert (prose["claims"][0]["source_name"], prose["claims"][0]["days"]) == (
        "艮土",
        5,
    )
    assert (table["claims"][0]["source_name"], table["claims"][0]["days"]) == (
        "己土",
        7,
    )
    assert table["claims"][0]["canonical_stem"] == "己"
    assert observation["literal_days"] == 5
    assert observation["effective_command_status"] == "not_adjudicated"
    assert witness["selected_duty_stem"] is None


def test_returned_source_identity_and_occurrences_cannot_mutate_cache_or_inputs():
    pillars = chart()
    first = layer(pillars)
    expected = deepcopy(first)
    first["source"]["chapter_original_pdf_pages"].append(-1)
    first["identity_claims"][0]["canonical_stem"] = "己"
    first["anchors"][0]["literal_quote"] = "changed"
    first["month_term_observations"][0]["hidden_positions"].clear()
    assert layer(pillars) == expected


@pytest.mark.parametrize("topic", TOPICS)
def test_identity_layer_matches_actual_rest_native_mcp_cli_for_all_ten_tools(
    topic, rest, tmp_path, capsys
):
    spec = SPECS["bazi_" + topic]
    prefix = "bazi_birth" if topic == "birth" else topic + "_analysis"
    chain = prefix + (
        ".structure_profile.evidence_chain" if topic == "birth" else ".evidence_chain"
    )
    path = (
        chain
        + ".month_command.intra_month_duty.source_reference.scanned_witness.cross_chapter_identities"
    )
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
    identity = evidence["month_command"]["intra_month_duty"]["source_reference"][
        "scanned_witness"
    ]["cross_chapter_identities"]
    assert (
        identity["month_term_observations"][0]["cross_chapter_canonical_stem"] == "戊"
    )
    assert (
        identity["selected_duty_stem"] is None
        and identity["effective_command_status"] == "not_adjudicated"
    )
