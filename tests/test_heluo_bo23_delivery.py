"""Candidate delivery and complete old-text preservation, without new scores."""

import copy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo_texts
from fatebridge.core.heluo import yao_text
from fatebridge.core.numerology_knowledge import _catalogue, _source
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.services.tool_catalog import CATALOG
from tests.heluo_bo23_revision_reference import REFERENCE as R101_REFERENCE
from tests.heluo_current_source_reference import (
    CATALOGUE_VERSION,
    HEADER_COUNT,
    PENDING_COUNT,
    advance_current_record,
)
from tests.test_agentic_nested_outputs import business
from tests.test_agentic_nested_outputs import rest as shared_rest
from tests.test_heluo_poem_transports import run_three

rest = shared_rest
W = Path(__file__).parent / "fixtures/heluo_bo23_v1"
LITERAL = json.loads((W / "reviewed-literals-v2.json").read_text())
CALCULATION_CASES = json.loads((W / "case-search/cases.json").read_text())["cases"]


@pytest.mark.parametrize("case", CALCULATION_CASES, ids=lambda c: f"line{c['line']}")
def test_six_before_selected_calculations_keep_math_and_formal_houtian(
    case, monkeypatch
):
    from fatebridge.core.local_techniques.heluo import build_heluo_result

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    line = case["line"]
    before = json.loads((W / f"case-search/before-line-{line}.json").read_text())
    actual = build_heluo_result(**case["payload"])
    protocol = json.loads(
        (W / "correction-evidence/case-replay-protocol.json").read_text()
    )
    for field in protocol["whole_equal_top_level_fields"]:
        assert actual[field] == before[field], field
    assert actual["heluo_timing"].keys() == before["heluo_timing"].keys()
    for field in before["heluo_timing"]:
        if field != "selected_texts":
            assert actual["heluo_timing"][field] == before["heluo_timing"][field], field
    selected = next(
        s["text"]
        for s in actual["numerology_evidence"]["selected_texts"]
        if s["hexagram"] == "山地剝" and s["line"] == line
    )
    assert selected["yaoci"] == LITERAL["entries"][line - 1]["yaoci"]
    assert selected["commentary_branch_selection"]["selected_section_ids"] == []
    if line in [4, 6]:
        reference = selected["commentary_cross_references"][0]
        assert reference["applicability"] is None
        assert (
            reference["automatic_application"] is reference["replaces_chart"] is False
        )
        assert reference["target_line"] != actual["chart"]["hou"]["yuan"]
        assert reference["condition_text"] in heluo_texts.text_status_snapshot(selected)


@pytest.mark.parametrize("entry", LITERAL["entries"], ids=lambda e: str(e["line"]))
def test_actual_knowledge_read_keeps_all_editorial_conditions(entry):
    out = calculate_knowledge_read(domain="heluo", key=f"山地剝:{entry['line']}")
    assert out["reference_details"]["record"] == yao_text("山地剝", entry["line"])
    assert out["reference_details"]["personal_applicability_assessed"] is False
    for surface in [
        "\n".join(out["lines"]),
        out["rendered_text"],
        out["snapshot_text"],
    ]:
        assert all(note in surface for note in entry["reading_notes"])
    if entry["line"] in [4, 6]:
        ref = next(
            r
            for r in LITERAL["conditional_references"]
            if r["source_line"] == entry["line"]
        )
        lines = [s for s in out["lines"] if s.startswith("有条件引文说明：")]
        assert len(lines) == 1 and ref["condition_text"] in lines[0]
        assert ref["source_context_text"] in lines[0]
        assert "适用性未裁定" in lines[0] and "不替代正式卦盘" in lines[0]


def test_actual_catalogue_binds_two_new_sources_and_preserves_other15():
    old = json.loads(
        (
            W / "before/src/fatebridge/data/knowledge/numerology-sources-v1.json"
        ).read_text()
    )
    new = _catalogue()
    assert new["version"] == CATALOGUE_VERSION
    changed = [
        (a["domain"], a["key"])
        for a, b in zip(old["sources"], new["sources"])
        if a != b
    ]
    assert changed == [("heluo", "commentary_collation"), ("heluo", "yaoci_collation")]
    assert len(new["sources"]) == 17
    for row in new["sources"]:
        data, meta = _source(row["domain"], row["key"])
        assert meta["canonical_content_sha256"] == row["canonical_content_sha256"]
        assert (
            hashlib.sha256(
                json.dumps(
                    data,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            == row["canonical_content_sha256"]
        )
    assert heluo_texts.collation_summary()["collated_line_headers"] == HEADER_COUNT
    assert (
        heluo_texts.commentary_collation_summary()["collated_line_commentaries"]
        == HEADER_COUNT
    )
    assert heluo_texts.collation_summary()["pending_line_headers"] == PENDING_COUNT


def test_all384_old_poems_verdicts_and_other378_full_records_are_preserved():
    old = json.loads(
        gzip.decompress((W / "before-all384-records.json.gz").read_bytes())
    )
    assert len(old) == 384
    for key, before in old.items():
        gua, line = key.rsplit(":", 1)
        actual = yao_text(gua, int(line))
        assert (
            actual["shige"] == before["shige"]
            and actual["verdict"] == before["verdict"]
        )
        if gua != "山地剝":
            expected = copy.deepcopy(before)
            current = R101_REFERENCE["records"][key]["after"]
            for field in [
                "corpus_id",
                "header_content_sha256",
                "transcription_policy",
                "commentary_corpus_id",
                "commentary_sha256",
                "commentary_content_sha256",
                "commentary_transcription_policy",
            ]:
                if field in expected["text_provenance"]:
                    expected["text_provenance"][field] = current["text_provenance"][
                        field
                    ]
            assert current == expected, key
            assert actual == advance_current_record(current, key), key


@pytest.mark.parametrize("line", [4, 5, 6])
def test_actual_rest_cli_inprocess_mcp_deliver_the_same_new_source(
    line, rest, tmp_path, capsys
):
    spec = next(s for s in CATALOG if s.key == "knowledge_read")
    response, code, cli, mcp = run_three(
        spec,
        {"domain": "heluo", "key": f"山地剝:{line}"},
        ["reference_details", "lines", "provenance", "snapshot_text"],
        rest,
        tmp_path,
        capsys,
    )
    assert response.status_code == 200 and code == 0 and not mcp.is_error
    outputs = [response.json(), cli, mcp.structured_content]
    assert business(outputs[0]) == business(outputs[1]) == business(outputs[2])
    for out in outputs:
        record = out["reference_details"]["record"]
        assert record["yaoci"] == LITERAL["entries"][line - 1]["yaoci"]
        assert record["commentary_branch_selection"]["selected_section_ids"] == []
        if line in [4, 6]:
            ref = record["commentary_cross_references"][0]
            assert ref["applicability"] is None
            assert ref["automatic_application"] is ref["replaces_chart"] is False


def test_printed_target_status_keeps_the_leaf_condition_not_just_annual_parent():
    record = yao_text("山地剝", 6)
    reference = record["commentary_cross_references"][0]
    assert reference["condition_text"] == "數凶"
    assert reference["source_condition_label"] == "歲運逢之"
    assert reference["applicability"] is None
    assert "數凶" in heluo_texts.text_status_snapshot(record)


def test_two_source_attested_leaf_conditions_and_other382_statuses_exact():
    path = W / "renderer-before-all384.json.gz"
    identity = json.loads((W / "renderer-before-freeze.json").read_text())
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == identity["current_C3_renderer_384_stored_sha256"]
    )
    before = json.loads(gzip.decompress(path.read_bytes()))
    after = {
        key: heluo_texts.text_status_snapshot(
            yao_text(key.rsplit(":", 1)[0], int(key.rsplit(":", 1)[1]))
        )
        for key in before
    }
    from tests.heluo_current_source_reference import REFERENCE as current_reference

    assert after == current_reference["statuses_after"]
    assert R101_REFERENCE["statuses_after"] == current_reference["statuses_before"]
    # Keep the original two-condition renderer transition as its own fixed edge.
    after = R101_REFERENCE["statuses_after"]
    changed = [key for key in before if before[key] != after[key]]
    assert changed == ["地天泰:2", "山地剝:6"]
    facts = {"地天泰:2": "如不入局不得位", "山地剝:6": "數凶"}
    old_records = json.loads(
        gzip.decompress((W / "before-all384-records.json.gz").read_bytes())
    )
    assert (
        old_records["地天泰:2"]["commentary_cross_references"][0]["condition_text"]
        == facts["地天泰:2"]
    )
    for key, condition in facts.items():
        assert after[key] == before[key].replace(
            "歲運逢之段引", f"歲運逢之段的{condition}语境引"
        )
        gua, line = key.rsplit(":", 1)
        record = yao_text(gua, int(line))
        reference = record["commentary_cross_references"][0]
        assert reference["condition_text"] == condition
        assert reference["source_condition_label"] == "歲運逢之"
        assert reference["applicability"] is None
        assert (
            reference["automatic_application"] is reference["replaces_chart"] is False
        )
        assert record["commentary_branch_selection"]["selected_section_ids"] == []
