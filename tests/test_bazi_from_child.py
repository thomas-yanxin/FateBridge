"""From-child source conditions are not an ordinary weak-body classification."""

import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaError
from pydantic import ValidationError

from fatebridge.core.classical_from_child import (
    build_from_child_reference,
    from_child_snapshot_lines,
)
from fatebridge.core.elements import ElementAnalysis
from fatebridge.core.output_bazi_evidence import EvidenceStructureProfile
from fatebridge.core.output_from_child import FromChildReference
from fatebridge.core.rules import BaZiRules

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/bazi_from_child_v1"
REFERENCE = ROOT / "tests/fixtures/bazi_body_seal_v5_followup_v1/reference.json"
CASES = json.loads(REFERENCE.read_text())["cases"]


def pillars(values):
    return {k: tuple(v) for k, v in zip(("year", "month", "day", "hour"), values)}


@pytest.mark.parametrize("case", [c for c in CASES if c["chapter"] == "順局"])
def test_all_nine_exposed_source_routes_keep_their_visible_and_hidden_facts(case):
    p = pillars(case["pillars"])
    ref = build_from_child_reference(p)
    assert ref["ordinary_fuyi_requires_review"]
    assert ref["strength_requirement"] == "not_a_prerequisite"
    assert ref["formation_status"] == "not_adjudicated"
    assert ref["status"] == "requires_force_adjudication"
    assert all(r["id"] != "day.stem" for r in ref["occurrences"])
    assert ref["pending_conditions"]
    profile = BaZiRules.chart_useful_profile(p)
    assert not profile["useful_elements"] and not profile["avoid_elements"]
    assert profile["from_child_reference"] == ref
    assert from_child_snapshot_lines(profile)


def test_month_visible_output_is_not_erased_by_a_peer_principal_branch():
    p = pillars(["庚子", "庚辰", "戊申", "辛酉"])
    ref = build_from_child_reference(p)
    month = ref["observed_conditions"][0]
    assert month["occurrence_ids"] == ["month.stem"]
    branch_principal = next(
        r for r in ref["occurrences"] if r["id"] == "month.hidden.0"
    )
    assert branch_principal["stem"] == "戊" and branch_principal["role"] == "peer"
    profile = BaZiRules.chart_useful_profile(p)
    assert profile["metadata"]["baseline_useful_elements"] == ["土", "火"]
    baseline = next(r for r in profile["layers"] if r["source"] == "扶抑")
    assert baseline["useful_elements"] == ["土", "火"]
    assert baseline["status"] == "requires_structure_review"
    assert {"金", "水", "火", "土"} <= set(profile["conditional_elements"])
    direction = ref["conditional_direction"]["if_route_is_formed"]
    assert direction == {
        "useful_elements": ["金", "水"],
        "avoid_elements": ["火", "木"],
    }


def test_hidden_wealth_and_obstructions_survive_instead_of_becoming_absent():
    p = pillars(["己未", "丁丑", "丙戌", "戊戌"])
    ref = build_from_child_reference(p)
    wealth = ref["observed_conditions"][2]
    assert wealth["matched"] and "month.hidden.2" in wealth["occurrence_ids"]
    assert not any(
        r["role"] == "wealth" and r["location"] == "visible" for r in ref["occurrences"]
    )
    assert ref["hidden_obstructions"]
    hidden = {r["id"]: r for r in ref["occurrences"]}
    assert {hidden[i]["role"] for i in ref["hidden_obstructions"]} == {
        "seal",
        "officer",
    }
    assert ref["ordinary_fuyi_requires_review"]
    # A rooted peer and the day master's real 寅 root cannot alone exclude 從兒.
    strong_root = build_from_child_reference(pillars(["甲午", "丁丑", "甲午", "丙寅"]))
    assert strong_root["ordinary_fuyi_requires_review"]
    assert any(
        r["stem"] == "甲" and r["location"] == "hidden"
        for r in strong_root["occurrences"]
    )


@pytest.mark.parametrize(
    "values,status",
    [
        (["甲子", "庚辰", "戊申", "辛酉"], "observable_obstruction"),
        (["丙子", "庚辰", "戊申", "辛酉"], "observable_obstruction"),
        (["戊戌", "庚戌", "戊戌", "辛酉"], "observable_prerequisite_not_met"),
        (["甲子", "戊辰", "戊辰", "戊辰"], "observable_prerequisite_not_met"),
    ],
)
def test_visible_opposing_stars_missing_wealth_and_missing_month_anchor_are_retained(
    values, status
):
    ref = build_from_child_reference(pillars(values))
    assert ref["status"] == status
    assert not ref["ordinary_fuyi_requires_review"]
    assert ref["formation_status"] == "not_adjudicated"
    FromChildReference.model_validate(ref)


def test_current_strength_and_complete_profiles_match_before_repair_on273_inputs():
    protocol = json.loads((FIXTURE / "protocol.json").read_text())
    archive = FIXTURE / "before.json.gz"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == protocol["before_sha256"]
    records = json.loads(gzip.decompress(archive.read_bytes()))
    assert len(records) == protocol["known_inputs"] == 273
    manifest_path = (
        ROOT
        / "tests/fixtures/architecture_refactor_v1/fromchild273-before-manifest.json"
    )
    packed = manifest_path.read_bytes()
    assert (
        hashlib.sha256(packed).hexdigest()
        == "48b0a59141613ef8b5788d912e77245f0f1718b7e33da23f5e89effe74b6d558"
    )
    baseline = json.loads(packed)
    assert baseline["source_sha256"] == protocol["before_sha256"]
    assert len(baseline["rows"]) == len(records) == 273
    for row, expected in zip(records, baseline["rows"], strict=True):
        assert row["pillars"] == expected["pillars"]
        p = pillars(row["pillars"])
        analysis = ElementAnalysis.comprehensive_analysis(p)
        profile = BaZiRules.build_structure_profile(p, analysis)
        # Current v10 objects are compared to the actual pre-repair source,
        # including every profile field and every unrounded numeric leaf.
        for key, value in (("analysis", analysis), ("profile", profile)):
            encoded = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            assert hashlib.sha256(encoded).hexdigest() == expected[key + "_sha256"]


def test_structured_contract_keeps_projections_but_rejects_false_formation():
    ref = build_from_child_reference(pillars(["庚子", "庚辰", "戊申", "辛酉"]))
    schema = FromChildReference.model_json_schema()
    for payload in [
        ref,
        {"ordinary_fuyi_requires_review": True},
        {"formation_status": "not_adjudicated"},
    ]:
        FromChildReference.model_validate(payload)
        Draft202012Validator(schema).validate(payload)
    for bad in ["formed", "full_marks", "weak_body_proved"]:
        payload = {"formation_status": bad}
        with pytest.raises(ValidationError):
            FromChildReference.model_validate(payload)
        with pytest.raises(SchemaError):
            Draft202012Validator(schema).validate(payload)
    bad = deepcopy(ref)
    bad["visible_obstructions"] = ["month.stem"]
    with pytest.raises(ValidationError):
        FromChildReference.model_validate(bad)
    with pytest.raises(SchemaError):
        Draft202012Validator(schema).validate(bad)
    profile = BaZiRules.chart_useful_profile(pillars(["庚子", "庚辰", "戊申", "辛酉"]))
    EvidenceStructureProfile.model_validate(profile)
    Draft202012Validator(EvidenceStructureProfile.model_json_schema()).validate(profile)
