"""Selected-edition conditions are evidence, not a force or predictive verdict."""

import asyncio
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.classical import (
    build_classical_overview,
    classical_snapshot_lines,
    seasonal_climate_god,
)
from fatebridge.core.output_classical_seasonal import SeasonalClimateReference
from tests.bazi_transport_reader import (
    cli_payload,
    file_payload,
    native_with_manifest,
    save_json,
    verify_identity,
)
from tests.test_agentic_nested_outputs import SPECS, business, call_cli
from tests.test_agentic_nested_outputs import rest as _rest_fixture

rest = _rest_fixture
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/data/bazi_seasonal_bing_v1"
SOURCE = json.loads((FIXTURE / "source-collation-first.json").read_bytes())[
    "source_profile"
]
SOURCE_NOTES = json.loads((FIXTURE / "input-witness-notes-first.json").read_bytes())
CASES = SOURCE["examples"]
PUBLIC = json.loads((FIXTURE / "public-inputs-first.json").read_bytes())["cases"]
from tests import bazi_strength_reference_v3 as REFERENCE


def pillars(values):
    return dict(zip(("year", "month", "day", "hour"), map(tuple, values)))


def test_full_unit_first_transcription_retains_bounded_labels_and_all_charts():
    raw = (FIXTURE / "source-collation-first.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == (FIXTURE / "source-collation-first.json.sha256").read_text().strip()
    )
    assert (
        len(CASES) == 33 and sum(c["expected_strength"] is not None for c in CASES) == 4
    )
    assert [c["id"] for c in CASES if c["expected_strength"] is not None] == [
        "QT-BING-14",
        "QT-BING-15",
        "QT-BING-23",
        "QT-BING-24",
    ]
    assert CASES[15]["expected_strength"] is None
    assert CASES[15]["negative_constraints"] == [
        {
            "kind": "strength_not",
            "value": "弱",
            "source_anchor": "日元不弱",
            "pdf_page": 92,
        }
    ]
    assert CASES[27]["label_kind"] == "comparative_with_preceding_chart_not_fixed_bin"
    assert all(
        c["absolute_birth_datetime"] is None and c["day_after_term"] is None
        for c in CASES
    )
    assert SOURCE["boundary_review"]["last_bing_pdf"] == 101
    assert SOURCE["boundary_review"]["next_ding_summary_pdf"] == 102
    assert SOURCE == json.loads(
        (ROOT / "src/fatebridge/data/bazi_seasonal_qiongtong_bing_v1.json").read_bytes()
    )


@pytest.mark.parametrize("stem", list("甲乙丙丁戊己庚辛壬癸"))
@pytest.mark.parametrize("branch", list("子丑寅卯辰巳午未申酉戌亥"))
def test_current_candidate_cells_keep_source_scope_and_never_claim_adjudication(
    stem, branch
):
    value = seasonal_climate_god(stem, branch)
    assert value["chart_adjudication_status"] == "not_performed"
    expected = (
        "selected_jia_passages_not_full_acceptance"
        if stem == "甲"
        else (
            "bing_unit_developer_collation_not_full_acceptance"
            if stem == "丙"
            else "source_not_collated"
        )
    )
    assert value["source_review_status"] == expected
    if stem not in {"甲", "丙"}:
        assert "source_layers" not in value and "source_ref" not in value


@pytest.mark.parametrize("branch", list("寅卯辰巳午未申酉戌亥子丑"))
def test_every_month_keeps_author_conditions_and_first_source_examples(branch):
    value = seasonal_climate_god("丙", branch)
    expected = {
        **SOURCE["months"][branch],
        "general_fire_context": SOURCE["general_fire_context"],
    }
    notes = [n for n in SOURCE_NOTES["notes"] if n["month_branch"] == branch]
    if notes:
        expected["input_witness_notes"] = {**SOURCE_NOTES, "notes": notes}
    assert value["source_layers"] == expected
    assert value["source_ref"] == SOURCE["source"]
    assert value["source_layers"]["chart_conditions_status"] == "not_adjudicated"
    assert value["source_layers"]["body"]["conditions_not_evaluated"]
    SeasonalClimateReference.model_validate(value)
    before = copy.deepcopy(value)
    value["source_layers"]["body"]["conditions_not_evaluated"].append("invented effect")
    assert seasonal_climate_god("丙", branch) == before


@pytest.mark.parametrize("case", CASES, ids=lambda r: r["id"])
def test_all_literal_chart_observations_match_independent_hidden_stems_and_stay_unadjudicated(
    case,
):
    ps = pillars(case["pillars"])
    value = seasonal_climate_god("丙", ps["month"][1], ps)
    for row in value["stem_observations"]:
        assert row["visible_positions"] == [p for p in ps if ps[p][0] == row["stem"]]
        assert row["hidden_positions"] == [
            {"pillar": p, "branch": ps[p][1], "hidden_rank": i}
            for p in ps
            for i, stem in enumerate(REFERENCE.HIDDEN[ps[p][1]])
            if stem == row["stem"]
        ]
    assert value["chart_adjudication_status"] == "not_performed"
    assert value["source_layers"]["chart_conditions_status"] == "not_adjudicated"
    assert "主用" not in "\n".join(
        classical_snapshot_lines(build_classical_overview(ps))
    )


def test_source_indirect_root_does_not_manufacture_physical_fire_hidden_in_hai():
    ps = pillars(["辛酉", "己亥", "丙子", "壬辰"])
    value = seasonal_climate_god("丙", "亥", ps)
    assert "亥中甲" in value["source_layers"]["body"]["paraphrase"]
    row = next(r for r in value["stem_observations"] if r["stem"] == "甲")
    assert row["hidden_positions"] == [
        {"pillar": "month", "branch": "亥", "hidden_rank": 1}
    ]
    assert not any(
        REFERENCE.STEM_ELEMENT[s] == "火"
        for _, b in ps.values()
        for s in REFERENCE.HIDDEN[b]
    )
    assert value["chart_adjudication_status"] == "not_performed"
    assert (
        "冬至前後"
        in seasonal_climate_god("丙", "子")["source_layers"]["body"][
            "conditions_not_evaluated"
        ][0]
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"source_ref": {"id": "qiongtong_xu_qianqian_jia_v1"}},
        {"source_ref": {"source_sha256": "wrong"}},
        {"source_layers": {"chart_conditions_status": "adjudicated"}},
        {"source_layers": {"chart_conditions_status": {}}},
        {"chart_adjudication_status": "adjudicated"},
    ],
)
def test_contradictory_source_and_fabricated_decisions_are_rejected_but_projection_is_partial(
    patch,
):
    value = seasonal_climate_god("丙", "亥")
    with pytest.raises(ValidationError):
        SeasonalClimateReference.model_validate({**value, **patch})
    SeasonalClimateReference.model_validate(
        {"source_review_status": "bing_unit_developer_collation_not_full_acceptance"}
    )
    SeasonalClimateReference.model_validate({"source_ref": {"title": "窮通寶鑑評註"}})


@pytest.mark.parametrize("case", PUBLIC, ids=lambda r: r["id"])
def test_all_twelve_months_eleven_entries_actual_transports_and_scope_controls(
    case, rest, tmp_path, capsys
):
    spec = SPECS[case["tool"]]
    fields = suggested_fields(spec, view="seasonal_conditions")
    assert len(fields) == 4
    flags = {
        "fields": fields,
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 8192,
    }
    result, manifest = asyncio.run(
        native_with_manifest(spec, case["arguments"], case["as_of"], flags, tmp_path)
    )
    code, local = call_cli(
        spec,
        case["arguments"],
        tmp_path,
        capsys,
        flags=[
            "--strict-fields",
            "--include-snapshot-text",
            "false",
            "--fields",
            *fields,
        ],
    )
    save_json(tmp_path / "cli-original-response.json", local)
    rest_value = None
    rest_manifest = None
    if spec.rest_path:
        response = rest.post(spec.rest_path, json=case["arguments"], params=flags)
        rest_value = response.json()
        save_json(tmp_path / "rest-original-response.json", rest_value)
        assert response.status_code == 200, response.text
        if rest_value.get("result_delivery"):
            response = rest.get(
                "/api/results/" + rest_value["result_delivery"]["result_id"]
            )
            save_json(tmp_path / "rest-manifest.json", response.json())
            assert response.status_code == 200, response.text
            rest_manifest = response.json()
            verify_identity(
                rest_value["result_delivery"], rest_value["run_metadata"], rest_manifest
            )
    assert not result.is_error and code == 0
    payloads = [
        file_payload(result.structured_content, manifest, tmp_path, "mcp"),
        cli_payload(local, tmp_path, capsys),
    ]
    if rest_value is not None:
        payloads.append(file_payload(rest_value, rest_manifest, tmp_path, "rest"))
    for payload in payloads:
        spec.output_model.model_validate(payload)
    assert all(business(v) == business(payloads[0]) for v in payloads)
    values = []
    for path in fields:
        value = payloads[0]
        for part in path.split("."):
            value = value[part]
        values.append(value)
    climate, force, duty, passage = values
    assert set(force.values()) == {"not_adjudicated"} and duty == "not_adjudicated"
    assert passage["effective_passage"] == "not_adjudicated"
    assert climate["chart_adjudication_status"] == "not_performed"
    if case["kind"] == "bing":
        assert (
            climate["source_layers"]["body"]["pdf_pages"]
            == SOURCE["months"][case["expected_branch"]]["body"]["pdf_pages"]
        )
        assert climate["source_ref"]["id"] == "qiongtong_xu_qianqian_bing_v1"
        assert (
            climate["source_review_status"]
            == "bing_unit_developer_collation_not_full_acceptance"
        )
    elif case["kind"] == "jia":
        assert (
            climate["source_review_status"]
            == "selected_jia_passages_not_full_acceptance"
        )
    else:
        assert climate["source_review_status"] == "source_not_collated"
        assert "source_ref" not in climate


def test_printed_calendar_conflict_is_visible_without_rewriting_the_case():
    note = seasonal_climate_god("丙", "卯")["source_layers"]["input_witness_notes"][
        "notes"
    ][0]
    assert (
        note["literal_pillars"]
        == CASES[5]["pillars"]
        == ["乙亥", "丁卯", "丙申", "己亥"]
    )
    assert note["observed_printed_month_stem"] == "丁"
    assert note["current_formula_month_stem"] == "己"
    assert note["calculation_effect"] == "none"
    assert CASES[5]["absolute_birth_datetime"] is None
    assert (
        "input_witness_notes" not in seasonal_climate_god("丙", "寅")["source_layers"]
    )
    assert (
        "input_witness_notes" not in seasonal_climate_god("甲", "卯")["source_layers"]
    )
