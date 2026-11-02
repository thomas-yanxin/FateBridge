"""Six complete source parents, bounded edges and actual transport delivery."""

import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.heluo import yao_text
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.services.tool_catalog import CATALOG
from tests.heluo_ben22_revision_reference import (
    LITERAL,
    REVISION,
    SUPPORT,
    F,
    _before_records,
    assert_r96_source_addition,
    canonical,
    rebind_r96_ben6,
    rebind_r96_counts,
    rebind_r96_metadata,
    rebind_r96_record,
    rebind_r96_render_row,
)
from tests.heluo_current_source_reference import (
    advance_current_business,
    advance_current_record,
)
from tests.test_agentic_nested_outputs import SPECS, business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three
from tests.test_heluo_reading_delivery import (
    LOOKUP,
    assert_full_snapshot_notes,
    literal_notes,
)

rest = shared_rest
CASES = json.loads((F / "case-search/cases.json").read_bytes())["cases"]


@pytest.fixture(autouse=True)
def actual_calendar(monkeypatch):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)


def test_source_freezes_and_first_failures_are_retained_without_new_credit():
    freeze = json.loads((F / "reference-freeze.json").read_bytes())
    assert freeze["before_any_existing_test_or_auditor_edits"] is True
    assert (
        hashlib.sha256((F / "migration-reference.json").read_bytes()).hexdigest()
        == freeze["migration_reference_sha256"]
    )
    assert (
        hashlib.sha256((F / "reviewed-literals-v2.json").read_bytes()).hexdigest()
        == freeze["source_literal_sha256"]
    )
    support = json.loads((F / "reference-support-freeze.json").read_bytes())
    assert (
        hashlib.sha256((F / "support-reference.json").read_bytes()).hexdigest()
        == support["support_reference_sha256"]
    )
    adjudication = json.loads((F / "postcomparison-adjudication.json").read_bytes())
    assert (
        adjudication["first_candidate_rejected"]
        and adjudication["after_legacy_exposure"]
    )
    assert adjudication["first_existing_tests"] == {
        "total": 171,
        "passed": 163,
        "failed": 8,
        "skipped": 0,
    }
    assert (
        hashlib.sha256(
            gzip.decompress((F / "existing-first-results.xml.gz").read_bytes())
        ).hexdigest()
        == adjudication["first_test_results_sha256"]
    )
    assert (
        REVISION["new_independent_readers"]
        == REVISION["new_model_evaluations"]
        == REVISION["new_real_world_outcomes"]
        == 0
    )
    assert REVISION["goal_complete"] is False
    assert LITERAL["independent_review"] is False
    assert_r96_source_addition()


def test_primary_embedded_pixels_are_bound_to_the_reused_original_pdf():
    root = Path(__file__).parents[1]
    source = json.loads((F / "primary-source-pointer.json").read_bytes())
    assert (
        hashlib.sha256(
            (root / source["repository_relative_file"]).read_bytes()
        ).hexdigest()
        == source["sha256"]
    )
    native = json.loads((F / "native-manifest.json").read_bytes())
    assert native["source_pdf_sha256"] == source["sha256"]
    assert [r["pdf_page_one_based"] for r in native["records"]] == [170, 171, 172, 173]
    assert native["page170_overlap_pixels_exact_to_R91"] is True
    for row in native["records"]:
        assert row["resampling"] is row["OCR_used"] is False
        assert (
            hashlib.sha256((F / row["embedded_file"]).read_bytes()).hexdigest()
            == row["embedded_sha256"]
        )
        assert (
            hashlib.sha256((F / row["native_png"]).read_bytes()).hexdigest()
            == row["native_png_sha256"]
        )


@pytest.mark.parametrize("entry", LITERAL["entries"], ids=lambda e: str(e["line"]))
def test_all_six_headers_and_24_complete_parent_sections_remain_unselected(entry):
    line = entry["line"]
    t = yao_text("山火賁", line)
    assert t["yaoci"] == entry["yaoci"]
    assert t["detail"] == "".join(s["text"] for s in entry["sections"])
    assert t["commentary_sections"] == [
        dict(s, applicability=None) for s in entry["sections"]
    ]
    assert [s["section_id"] for s in t["commentary_sections"]] == [
        "opening",
        "xie",
        "buxie",
        "annual",
    ]
    assert t["commentary_branch_selection"]["selected_section_ids"] == []
    assert t["text_provenance"]["commentary_pdf_pages"] == entry["pdf_pages"]
    assert t["text_provenance"]["commentary_reading_notes"] == entry["reading_notes"]
    out = calculate_knowledge_read(domain="heluo", key=f"山火賁:{line}")
    assert out["reference_details"]["personal_applicability_assessed"] is False
    assert out["reference_details"]["record"] == t
    row = LOOKUP[("山火賁", line)]
    notes = row["header_notes"] + entry["reading_notes"]
    for surface in [
        "\n".join(out["lines"]),
        out["rendered_text"],
        out["snapshot_text"],
    ]:
        assert all(note in surface for note in notes)
    if line in [1, 2, 5]:
        assert "注文字形未决：" in "\n".join(out["lines"])
        assert any(
            "未決" in note or "疑讀" in note or "待獨立復核" in note
            for note in entry["reading_notes"]
        )


def test_withdrawn_own_reading_is_not_promoted_and_clear_inherited_errors_are_repaired():
    assert "暫時俯仰" in json.dumps(
        json.loads((F / "reviewed-source-first.json").read_bytes()), ensure_ascii=False
    )
    assert "掣肘俯仰" in yao_text("山火賁", 1)["detail"]
    assert "暫時俯仰" not in yao_text("山火賁", 1)["detail"]
    for line, right, wrong in [
        (1, "節躬厲行", "飾躬歷行"),
        (2, "輿脫輹", "輿脫輻"),
        (3, "道足以經時", "道是以經時"),
        (6, "隨時衣食", "隨時食衣"),
    ]:
        t = yao_text("山火賁", line)
        assert right in t["detail"] and wrong not in t["detail"]
        assert wrong in t["text_provenance"]["inherited_detail"]


def test_annual_dayu_reference_keeps_whole_parent_and_does_not_invent_a_line():
    t = yao_text("山火賁", 2)
    r = t["commentary_cross_references"][0]
    assert r["target_hexagram"] == "山天大畜" and r["target_line"] is None
    assert r["target_line_source_status"] == "not_printed"
    assert (
        r["source_section_id"] == "annual" and r["source_condition_label"] == "歲運逢之"
    )
    assert r["source_context_text"] == t["commentary_sections"][-1]["text"]
    assert (
        r["applicability"] is None
        and r["automatic_application"] is r["replaces_chart"] is False
    )
    assert r["target_lines"] == [1, 1, 1, 0, 0, 1]
    out = calculate_knowledge_read(domain="heluo", key="山火賁:2")
    notes = [s for s in out["lines"] if s.startswith("有条件引文说明：")]
    assert len(notes) == 1 and r["source_context_text"] in notes[0]
    assert "None" not in notes[0] and "不替代正式卦盘" in notes[0]


def test_all384_edges_keep_all_verdicts_and_other378_literal_bodies():
    old = _before_records()
    assert len(old) == 384
    for key, value in old.items():
        gua, pos = key.rsplit(":", 1)
        from tests.heluo_bo23_revision_reference import rebind_r101_record

        expected_r96 = rebind_r96_record(rebind_r96_metadata(value), key)
        expected = advance_current_record(rebind_r101_record(expected_r96, key), key)
        assert yao_text(gua, int(pos)) == expected
        assert expected["verdict"] == value["verdict"]
        if key not in REVISION["record_extensions"]:
            assert {k: v for k, v in value.items() if k != "text_provenance"} == {
                k: v for k, v in expected_r96.items() if k != "text_provenance"
            }


@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["line"]))
def test_six_synthetic_calculations_change_only_declared_source_objects(case):
    line = case["line"]
    before = json.loads((F / f"case-search/before-line-{line}.json").read_bytes())
    from tests.heluo_bo23_revision_reference import rebind_r101_business

    expected = advance_current_business(
        rebind_r101_business(rebind_r96_ben6(before, line), "ben6", line), "ben6", line
    )
    actual = build_heluo_result(**case["payload"])
    assert {k: v for k, v in actual.items() if k != "snapshot_text"} == {
        k: v for k, v in expected.items() if k != "snapshot_text"
    }
    assert actual["chart"][case["phase"]]["name"] == "山火賁"
    assert actual["chart"][case["phase"]]["yuan"] == line
    assert_full_snapshot_notes(actual["snapshot_text"], actual)
    if line == 2:
        assert (
            actual["chart"]["hou"]["name"] == "天山遯"
            and actual["chart"]["hou"]["yuan"] == 5
        )


@pytest.mark.parametrize("entry", LITERAL["entries"], ids=lambda e: str(e["line"]))
def test_actual_rest_mcp_cli_knowledge_delivers_literal_qualifications(
    entry, rest, tmp_path, capsys
):
    spec = next(s for s in CATALOG if s.key == "knowledge_read")
    response, code, cli, mcp = run_three(
        spec,
        {"domain": "heluo", "key": f"山火賁:{entry['line']}"},
        ["reference_details", "lines", "provenance", "snapshot_text"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outs = [response.json(), cli, mcp.structured_content]
    assert business(outs[0]) == business(outs[1]) == business(outs[2])
    for out in outs:
        assert out["reference_details"]["record"]["detail"] == "".join(
            s["text"] for s in entry["sections"]
        )
        assert out["reference_details"]["personal_applicability_assessed"] is False
        assert all(
            note in out["snapshot_text"]
            for note in LOOKUP[("山火賁", entry["line"])]["header_notes"]
            + entry["reading_notes"]
        )


@pytest.mark.parametrize("line", range(1, 7))
@pytest.mark.parametrize("kind", ["detail", "verdict", "repeated"])
def test_record_edges_reject_unbound_or_repeated_facts(line, kind):
    key = f"山火賁:{line}"
    value = rebind_r96_metadata(_before_records()[key])
    if kind == "repeated":
        value = rebind_r96_record(value, key)
    else:
        value[kind] += "篡改"
    with pytest.raises(AssertionError):
        rebind_r96_record(value, key)


@pytest.mark.parametrize("kind", ["number", "snapshot", "repeated"])
def test_synthetic_business_edge_rejects_numeric_and_snapshot_mutation(kind):
    value = json.loads((F / "case-search/before-line-2.json").read_bytes())
    if kind == "number":
        value["chart"]["tian"] += 1
    elif kind == "snapshot":
        value["snapshot_text"] += "篡改"
    else:
        value = rebind_r96_ben6(value, 2)
    with pytest.raises(AssertionError):
        rebind_r96_ben6(value, 2)


def test_metadata_edges_are_typed_and_do_not_rewrite_literals_or_calendar_numbers():
    for parent in ["text_provenance", "provenance"]:
        for key, (old, new) in REVISION[parent + "_pairs"].items():
            assert rebind_r96_metadata({key: old}, parent) == {key: new}
            for bad in [new, "篡改"]:
                with pytest.raises(AssertionError):
                    rebind_r96_metadata({key: bad}, parent)
    for key, (old, new) in REVISION["coverage_pairs"].items():
        assert rebind_r96_counts({"coverage": {key: old}}) == {"coverage": {key: new}}
        for bad in [new, float(old)]:
            with pytest.raises(AssertionError):
                rebind_r96_counts({"coverage": {key: bad}})
    old, new = REVISION["exact_metadata_footer_pairs"][0]
    for field in ["detail", "reading_notes", "chart", "number"]:
        value = {
            field: {
                "provenance": {"source_catalogue_version": 9},
                "coverage": {"header_collated": 126},
                "text": old,
            }
        }
        assert rebind_r96_metadata(value) == value and rebind_r96_counts(value) == value
    assert rebind_r96_metadata({"snapshot_text": "prefix " + old}) == {
        "snapshot_text": "prefix " + old
    }
    assert rebind_r96_metadata({"snapshot_text": old}) == {"snapshot_text": new}


@pytest.mark.parametrize("line", range(1, 7))
def test_render_source_edge_rejects_altered_geometry_and_repetition(line):
    edge = SUPPORT["render_edges"][f"山火賁:{line}"]
    assert rebind_r96_render_row(edge["before"]) == edge["after"]
    bad = copy.deepcopy(edge["before"])
    bad["lines"][0] = 1 - bad["lines"][0]
    for value in [bad, edge["after"]]:
        with pytest.raises(AssertionError):
            rebind_r96_render_row(value)
