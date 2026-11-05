"""Source-role distinctions, missing prerequisites and real three-surface views."""

import asyncio
import copy
import hashlib
import json
from itertools import product
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from fatebridge.application.examples import suggested_fields
from fatebridge.core.bazi_evidence import build_natal_evidence
from fatebridge.core.classical import build_classical_overview, classical_snapshot_lines
from fatebridge.core.classical_candidate_selection import build_candidate_selection
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_candidate_selection import (
    CandidateSelection,
    MonthStructureReference,
)
from fatebridge.core.rules import BaZiRules
from tests.test_agentic_nested_outputs import (
    SPECS,
    business,
    call_cli,
    inputs,
    native,
)
from tests.test_agentic_nested_outputs import rest as _shared_rest

FIXTURE = Path(__file__).parent / "data/bazi_month_paths_v1/source-observations.json"
REFERENCE = json.loads(FIXTURE.read_text())
ORDER = ("year", "month", "day", "hour")
TOPICS = [
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
]


def chart(values):
    return dict(
        zip(ORDER, map(tuple, values.split() if isinstance(values, str) else values))
    )


def path_by_id(selection, key):
    return next(p for p in selection["paths"] if p["id"] == key)


rest = _shared_rest


@pytest.mark.parametrize("case", REFERENCE["cases"], ids=lambda c: c["id"])
def test_source_path_observations_are_not_force_or_formation_labels(case):
    assert (
        hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        == FIXTURE.with_suffix(".sha256").read_text().strip()
    )
    pillars = chart(case["pillars"])
    evidence = build_natal_evidence(pillars)
    selection = evidence["candidate_selection"]
    row = path_by_id(selection, case["expected_path"])
    assert row["status"] == "requires_force_adjudication"
    assert case["basis"] in row["month_anchor_basis"]
    if case.get("required_ref"):
        assert case["required_ref"] in {
            ref for c in row["observed_conditions"] for ref in c.get("star_refs", [])
        }
    ids = {
        s["evidence_id"] for entries in evidence["ten_gods"].values() for s in entries
    }
    assert all(
        set(c.get("star_refs", [])) <= ids
        for p in selection["paths"]
        for c in p["observed_conditions"]
    )
    assert all(
        c["status"] == "unknown"
        for p in selection["paths"]
        for c in p["force_conditions"]
    )
    assert (
        selection["chosen_path_id"] is None
        and selection["adjudication_status"] == "not_adjudicated"
    )
    CandidateSelection.model_validate(selection)
    assert selection == BaZiRules.chart_useful_profile(pillars)["candidate_selection"]


def test_original_seal_and_revealed_killer_are_not_collapsed_into_an_accepted_transformation():
    pillars = chart("壬寅 戊申 壬辰 壬寅")
    selection = build_candidate_selection(pillars)
    assert selection["selected_month"]["ten_god"] == "七杀"
    assert selection["selected_month"]["original_main_qi"] == {
        "stem": "庚",
        "ten_god": "偏印",
    }
    assert path_by_id(selection, "seal_killer")["month_anchor_basis"] == [
        "original_main_qi"
    ]
    assert path_by_id(selection, "killer_seal")["month_anchor_basis"] == ["selected"]
    assert selection["selected_month"]["basis_status"] == "original_and_selected_differ"
    assert (
        ElementAnalysis.analyze_day_master_strength(pillars)["strength_level"] == "中和"
    )
    text = "\n".join(classical_snapshot_lines(build_classical_overview(pillars)))
    assert "本气为偏印" in text and "所选为七杀" in text
    assert "变格、兼格" in text and "成格与取用未裁定" in text


def test_hidden_killer_is_observed_without_inventing_revelation_or_correcting_the_source_hour():
    source = chart("戊戌 乙卯 丙午 乙亥")
    result = build_candidate_selection(source)
    condition = path_by_id(result, "seal_killer")["observed_conditions"][0]
    assert condition["star_refs"] == ["hour:hidden:壬"]
    # Keep the source and its inferred hour variant distinct; both remain unadjudicated.
    variant = build_candidate_selection(chart("戊戌 乙卯 丙午 己亥"))
    assert (
        path_by_id(variant, "seal_killer")["observed_conditions"][0]["star_refs"]
        == condition["star_refs"]
    )
    assert source["hour"] == ("乙", "亥")


def test_a_blade_outside_the_month_is_not_a_month_blade_class():
    selection = build_candidate_selection(chart("戊辰 甲寅 戊寅 戊午"))
    assert selection["selected_month"]["ten_god"] == "七杀"
    row = path_by_id(selection, "killer_blade")
    assert row["observed_conditions"][0]["positions"] == ["hour"]
    assert not {"blade_officer", "blade_killer"} & {r["id"] for r in selection["paths"]}


def test_source_caution_is_not_a_path_exclusion_or_an_event_forecast():
    source = FIXTURE.parent / "source-caution-correction-v3.json"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        source.with_suffix(".sha256").read_text().strip()
    )
    fixture = json.loads(source.read_text(encoding="utf-8"))
    for case in fixture["cases"]:
        row = path_by_id(
            build_candidate_selection(chart(" ".join(case["pillars"]))),
            case["expected_path"],
        )
        assert row["status"] == case["expected_status"]
        caution = next(
            c for c in row["source_cautions"] if c["id"] == case["source_caution_id"]
        )
        assert caution["status"] == case["expected_caution_status"]
        assert caution["effect"] == "source_caution_only"
        assert row["formation_status"] == "not_adjudicated"
        assert all(c["status"] == "unknown" for c in row["force_conditions"])


def test_gold_water_officer_requires_the_selected_text_observations_and_is_never_automatically_good_or_bad():
    good = build_candidate_selection(chart("戊申 甲子 庚午 丁丑"))
    assert path_by_id(good, "hurt_officer")["status"] == "requires_force_adjudication"
    # Internally coherent fictional pillars: 癸伤官 is now revealed beside 丁官.
    other = path_by_id(
        build_candidate_selection(chart("癸酉 甲子 庚午 丁丑")), "hurt_officer"
    )
    assert other["status"] == "requires_force_adjudication"
    assert (
        next(
            c
            for c in other["source_cautions"]
            if c["id"] == "officer_hurt_both_revealed"
        )["status"]
        == "matched"
    )
    assert other["formation_status"] == "not_adjudicated"


def test_gold_water_helpers_need_not_be_revealed_and_only_both_revealed_is_the_observed_objection():
    # Internally coherent fictional inputs, with no source outcome labels.
    row = path_by_id(
        build_candidate_selection(chart("壬申 壬子 庚午 丁丑")), "hurt_officer"
    )
    helper = next(
        c for c in row["observed_conditions"] if c["id"] == "wealth_or_seal_present"
    )
    assert helper["status"] == "matched"
    assert set(helper["star_refs"]) == {
        "year:hidden:戊",
        "day:hidden:己",
        "hour:hidden:己",
    }
    assert row["status"] == "requires_force_adjudication"
    single = path_by_id(
        build_candidate_selection(chart("癸酉 甲子 庚午 壬午")), "hurt_officer"
    )
    assert (
        next(
            c
            for c in single["source_cautions"]
            if c["id"] == "officer_hurt_both_revealed"
        )["status"]
        == "not_matched"
    )
    assert single["status"] == "requires_force_adjudication"
    assert all(c["status"] == "unknown" for c in single["force_conditions"])


@pytest.mark.parametrize("index", [0, 1])
def test_both_pdf85_examples_keep_wealth_as_a_bridge_without_erasing_hurt_or_selecting_a_winner(
    index,
):
    source = FIXTURE.with_name("pdf85-addendum.json")
    assert (
        hashlib.sha256(source.read_bytes()).hexdigest()
        == source.with_suffix(".sha256").read_text().strip()
    )
    case = json.loads(source.read_text())["cases"][index]
    pillars = chart(case["pillars"])
    before = copy.deepcopy(pillars)
    evidence = build_natal_evidence(pillars)
    selection = evidence["candidate_selection"]
    row = path_by_id(selection, case["expected_path"])
    assert row["status"] == "requires_force_adjudication"
    assert row["source_pdf_pages"] == [85]
    assert selection["method_id"] == "month_path_conditions_v4"
    assert pillars == before and evidence["ten_gods"]["伤官"]
    assert selection["chosen_path_id"] is None and case["expected_strength"] is None
    assert all(c["status"] == "unknown" for c in row["force_conditions"])
    if index == 0:
        assert {s["location"] for s in evidence["ten_gods"]["正财"]} == {"地支藏干"}
    else:
        assert selection["selected_month"]["ten_god"] == "正财"
        assert row["month_anchor_basis"] == ["original_main_qi"]


def test_arbitrary_legacy_priority_cannot_choose_the_source_path_or_promote_useful_elements(
    monkeypatch,
):
    pillars = chart("庚辰 戊子 壬寅 乙巳")
    before = BaZiRules.chart_useful_profile(pillars)
    monkeypatch.setattr(
        BaZiRules,
        "STRUCTURE_PRIORITIES",
        {key: -value for key, value in BaZiRules.STRUCTURE_PRIORITIES.items()},
    )
    after = BaZiRules.chart_useful_profile(pillars)
    assert before["dominant_structure"] == after["dominant_structure"]
    assert before["candidate_selection"] == after["candidate_selection"]
    for field in [
        "useful_elements",
        "avoid_elements",
        "conditional_elements",
        "neutral_elements",
    ]:
        assert before[field] == after[field]
    assert before["useful_elements"] == before["avoid_elements"] == []
    assert set(before["conditional_elements"]) == {"木", "火", "土", "金"}


def test_contract_rejects_unearned_force_formation_and_path_selection_but_allows_projection():
    selection = build_candidate_selection(chart("戊辰 甲寅 戊寅 戊午"))
    for patch in [
        {"chosen_path_id": "killer_blade"},
        {"adjudication_status": "accepted"},
    ]:
        with pytest.raises(ValidationError):
            CandidateSelection.model_validate({**selection, **patch})
    changed = copy.deepcopy(selection)
    changed["paths"][0]["force_conditions"][0]["status"] = "matched"
    with pytest.raises(ValidationError):
        CandidateSelection.model_validate(changed)
    changed = copy.deepcopy(selection)
    changed["paths"][0]["status"] = "requires_force_adjudication"
    with pytest.raises(ValidationError):
        CandidateSelection.model_validate(changed)
    for field in ["useful_elements", "avoid_elements", "useful_ten_gods"]:
        with pytest.raises(ValidationError):
            MonthStructureReference.model_validate({field: ["虚构用神"]})
    CandidateSelection.model_validate({"selected_month": {"branch": "寅"}})
    CandidateSelection.model_validate(
        {"paths": [{"observed_conditions": [{"status": "matched"}]}]}
    )
    for caution in [
        {"effect": "exclude_path"},
        {"status": "predicted_outcome"},
    ]:
        with pytest.raises(ValidationError):
            CandidateSelection.model_validate(
                {"paths": [{"source_cautions": [caution]}]}
            )


@pytest.mark.parametrize(
    "stem,branch", list(product("甲乙丙丁戊己庚辛壬癸", "子丑寅卯辰巳午未申酉戌亥"))
)
def test_all_stem_month_unit_inputs_preserve_unknown_force_and_have_no_chosen_path(
    stem, branch
):
    # Synthetic branch coverage; not independent, coherent birth charts or accuracy cases.
    pillars = chart(["庚辰", "戊" + branch, stem + "寅", "乙巳"])
    selection = build_candidate_selection(pillars)
    CandidateSelection.model_validate(selection)
    assert selection["chosen_path_id"] is None
    assert len({r["id"] for r in selection["paths"]}) == len(selection["paths"])
    assert all(r["month_anchor_basis"] for r in selection["paths"])
    assert all(r["formation_status"] == "not_adjudicated" for r in selection["paths"])


@pytest.mark.parametrize(
    "key", ["analyze_destiny", *["bazi_" + topic for topic in TOPICS]]
)
def test_published_candidate_views_are_same_on_actual_rest_native_mcp_and_cli(
    key, rest, tmp_path, capsys
):
    # analyze_destiny is the root calculation tool; the catalog key can differ.
    spec = next(s for s in SPECS.values() if s.tool_name == key)
    payload = inputs(spec)
    fields = suggested_fields(spec, view="candidate_selection")
    controls = {"fields": fields, "strict_fields": True, "include_snapshot_text": False}
    # The root analyze_destiny tool has MCP/CLI surfaces. Its REST wrapper is
    # bazi_birth, so compare that wrapper's actual selected business object.
    rest_spec = SPECS["bazi_birth"] if key == "analyze_destiny" else spec
    rest_controls = {
        **controls,
        "fields": (
            ["bazi_birth." + f for f in fields] if key == "analyze_destiny" else fields
        ),
    }
    response = rest.post(rest_spec.rest_path, json=payload, params=rest_controls)
    protocol = asyncio.run(native(spec, {**payload, **controls}))
    code, local = call_cli(
        spec,
        payload,
        tmp_path,
        capsys,
        flags=["--response-char-limit", "0", "--strict-fields", "--fields", *fields],
    )
    assert response.status_code == 200 and not protocol.is_error and code == 0
    rest_business = business(response.json())
    if key == "analyze_destiny":
        rest_business = rest_business["bazi_birth"]
    assert rest_business == business(protocol.structured_content) == business(local)
    Draft202012Validator(rest_spec.output_model.model_json_schema()).validate(
        response.json()
    )
    for result in [protocol.structured_content, local]:
        Draft202012Validator(spec.output_model.model_json_schema()).validate(result)
    for result in [rest_business, protocol.structured_content, local]:
        selection = result
        for part in fields[0].split("."):
            selection = selection[part]
        assert (
            selection["chosen_path_id"] is None
            and selection["adjudication_status"] == "not_adjudicated"
        )
        assert selection["source"]["source_sha256"] == REFERENCE["source_sha256"]
        assert selection["method_id"] == "month_path_conditions_v4"
