"""Two source diagrams add narrow evidence without upgrading old failures."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fatebridge.application.execution import execute_tool
from fatebridge.core.human_design_cross_coverage import expanded_cross_audit
from fatebridge.core.human_design_primary_diagrams import (
    diagram_reference,
    primary_diagram_evidence,
)
from fatebridge.core.human_design_source_variants import source_variant_audit
from fatebridge.services.replay_metadata import digest
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.human_design import verify_human_design_reading
from scripts.check_human_design_primary_diagrams import (
    extract_diagram,
    frozen_observation_check,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = next(s for s in CATALOG if s.key == "human_design")
PLAN_PATH = ROOT / "tests/fixtures/human-design-primary-diagrams-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
COHORT = json.loads(
    (ROOT / "tests/fixtures/human-design-official-cross-charts.json").read_text()
)


def rehash(value):
    value["run_metadata"]["business_output_sha256"] = digest(
        {k: v for k, v in value.items() if k != "run_metadata"}
    )
    return value


def test_preregistered_diagrams_pages_and_all_original_failures_remain():
    assert (
        hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest()
        == "a160cb5c68081be11c6f799cc9f4d1aadbb410808019915beec300893d2b3adf"
    )
    catalog = (
        ROOT / "src/fatebridge/data/human_design/primary-diagrams-2008-reference.json"
    )
    assert hashlib.sha256(catalog.read_bytes()).hexdigest() == PLAN["catalog_sha256"]
    rows = diagram_reference()["observations"]
    assert [
        (r["quarter"], r["pdf_page_one_based"], r["printed_page"], r["gates"])
        for r in rows
    ] == [(2, 105, 95, [16, 9, 63, 64]), (4, 93, 83, [9, 16, 64, 63])]
    assert all(
        r["section_profile"] == "5/1"
        and r["transcription_proofed"] is False
        and r["publisher_master_authenticated"] is False
        and r["publisher_erratum"] is False
        for r in rows
    )
    original = source_variant_audit()
    expanded = expanded_cross_audit()
    assert original["observed_label_count"] == 19
    assert original["literal_name_matches"] == 4
    assert expanded["observations_checked"] == 193
    assert expanded["literal_name_matches"] == 107
    assert (
        original["all_disagreements_resolved"]
        is expanded["all_disagreements_resolved"]
        is False
    )
    assert [
        (r["gate"], r["line"], r["printed_width_arcseconds"])
        for r in original["line_width_disagreements"]
    ] == [(29, 1, 2775), (29, 2, 3975)]
    assert (
        frozen_observation_check()["status"]
        == "bounded_two_unproofed_diagram_facts_matched"
    )


@pytest.mark.parametrize("angle", ["right", "juxtaposition"])
@pytest.mark.parametrize("gates", [[16, 9, 63, 64], [9, 16, 64, 63]])
def test_no_matching_by_single_gate_or_name_when_angle_is_wrong(angle, gates):
    result = primary_diagram_evidence(
        {
            "incarnation_cross": {
                "gates": gates,
                "angle": angle,
                "name": "IDENTIFICATION",
            }
        }
    )
    assert result["status"] == "not_observed_in_two_diagrams"
    assert result["observations"] == []


@pytest.mark.parametrize(
    "gates", [[16, 6, 63, 64], [16, 9, 64, 63], [9, 16, 63, 64], [1, 2, 7, 13]]
)
def test_ordered_four_gates_required_without_aliases_or_silent_correction(gates):
    result = primary_diagram_evidence(
        {
            "incarnation_cross": {
                "gates": gates,
                "angle": "left",
                "name": "IDENTIFICATION",
            }
        }
    )
    assert result["observations"] == []


@pytest.fixture(scope="module", params=list(PLAN["expected_matches"]))
def complete(request):
    case = next(c for c in COHORT["cases"] if c["id"] == request.param)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SE_EPHE_PATH", str(ROOT / "ephe"))
        patch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
        return execute_tool(SPEC, SPEC.request_model(**case["birth_input"]))


def test_same_quartet_witness_and_complete_additional_statement(complete):
    proof = complete["source_consistency"]["primary_transcript_diagrams"]
    assert proof["status"] == "observed_same_ordered_quartet_and_angle"
    assert len(proof["observations"]) == 1
    assert proof["observations"][0]["gates"] == complete["incarnation_cross"]["gates"]
    assert proof["primary_2001_name"] == complete["incarnation_cross"]["name"]
    assert (
        proof["publisher_erratum_obtained"]
        is proof["full_source_acceptance_passed"]
        is False
    )
    statements = complete["interpretation"]["statements"]
    assert len(statements) == 11
    assert statements[-1]["id"] == "primary_transcript_diagram"
    assert "未经校对" in statements[-1]["text"] and "5/1" in statements[-1]["text"]
    checked = verify_human_design_reading(complete)
    assert checked["status"] == "verified_fixed_template_reading", checked
    assert checked["checked_statement_count"] == 11


@pytest.mark.parametrize("case", PLAN["rejection_probes"])
def test_all_rehashed_diagram_and_qualification_mutations_are_rejected(complete, case):
    value = deepcopy(complete)
    proof = value["source_consistency"]["primary_transcript_diagrams"]
    row = proof["observations"][0]
    if case == "changed_pdf_hash":
        row["pdf_sha256"] = "0" * 64
    elif case == "changed_pdf_page":
        row["pdf_page_one_based"] += 1
    elif case == "changed_printed_page":
        row["printed_page"] += 1
    elif case == "changed_gate_order":
        row["gates"][0], row["gates"][1] = row["gates"][1], row["gates"][0]
    elif case == "changed_diagram_name":
        row["display_identifier"] = "Identification 3"
    elif case == "unproofed_promoted_to_proofed":
        proof["transcription_proofed"] = True
    elif case == "publisher_master_promoted_to_authenticated":
        proof["publisher_master_authenticated"] = True
    elif case == "publisher_erratum_invented":
        proof["publisher_erratum_obtained"] = True
    elif case == "all_disagreements_marked_resolved":
        proof["all_source_disagreements_resolved"] = True
    elif case == "missing_source_diagram_statement":
        value["interpretation"]["statements"].pop()
    else:
        raise AssertionError(case)
    assert verify_human_design_reading(rehash(value))["status"] == "rejected"


def test_evidence_cannot_mutate_the_cached_source_catalog(complete):
    expected = deepcopy(diagram_reference())
    proof = primary_diagram_evidence(complete)
    proof["observations"][0]["gates"][0] = 60
    assert diagram_reference() == expected


def _minimal_pdf_xml():
    def line(text, y=100):
        return (
            '<line yMin="100" yMax="115">'
            + "".join(
                f'<word xMin="90" yMin="{y}">{word}</word>' for word in text.split()
            )
            + "</line>"
        )

    numbers = "".join(
        f'<word xMin="{x}" yMin="{y}">{number}</word>'
        for x, y, number in [
            (450, 98, 16),
            (450, 112, 9),
            (494, 98, 63),
            (494, 112, 64),
        ]
    )
    return (
        '<html xmlns="http://www.w3.org/1999/xhtml"><page width="612" height="792">'
        + line("The Left Angle Cross of Identification 1")
        + numbers
        + line("This transcription has not been proofed.", 750)
        + '<word xMin="300" yMin="760">95</word></page></html>'
    )


def test_extraction_uses_page_coordinates_and_preserves_the_printed_pair_order():
    actual = extract_diagram(_minimal_pdf_xml(), "Identification 1")
    assert actual == {
        "display_identifier": "Identification 1",
        "gates": [16, 9, 63, 64],
        "printed_page": 95,
        "transcription_proofed": False,
    }


@pytest.mark.parametrize(
    "mutation",
    ["notice", "duplicate_heading", "extra_number", "wrong_row", "missing_footer"],
)
def test_source_parser_rejects_ambiguous_or_unqualified_observations(mutation):
    value = _minimal_pdf_xml()
    if mutation == "notice":
        value = value.replace("proofed.", "unverified.")
    elif mutation == "duplicate_heading":
        line = value[value.index("<line") : value.index("</line>") + 7]
        value = value.replace("</page>", line + "</page>")
    elif mutation == "extra_number":
        value = value.replace("</page>", '<word xMin="500" yMin="110">7</word></page>')
    elif mutation == "wrong_row":
        value = value.replace('xMin="494" yMin="112"', 'xMin="494" yMin="119"')
    elif mutation == "missing_footer":
        value = value.replace('yMin="760"', 'yMin="700"')
    with pytest.raises(ValueError):
        extract_diagram(value, "Identification 1")
