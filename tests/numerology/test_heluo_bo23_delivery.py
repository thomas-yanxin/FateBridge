"""Current selected source facts and all original public route inputs."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo_texts
from fatebridge.core.heluo import yao_text
from fatebridge.core.numerology_knowledge import _catalogue, _source
from fatebridge.services.knowledge import calculate_knowledge_read
from fatebridge.services.tool_catalog import CATALOG
from tests.evaluation.test_agentic_nested_outputs import business
from tests.evaluation.test_agentic_nested_outputs import rest as shared_rest
from tests.numerology.test_heluo_poem_transports import run_three
from tests.support.heluo_source_facts import (
    CATALOGUE_VERSION,
    HEADER_COUNT,
    PENDING_COUNT,
)

rest = shared_rest
W = Path(__file__).parents[1] / "fixtures/heluo_bo23_v1"
LITERAL = json.loads((W / "reviewed-literals-v2.json").read_text())
CALCULATION_CASES = json.loads(
    (Path(__file__).parents[1] / "data/heluo/bo_routes.json").read_text()
)["cases"]


@pytest.mark.parametrize("case", CALCULATION_CASES, ids=lambda c: f"line{c['line']}")
def test_six_original_routes_keep_source_scope_and_formal_houtian(case, monkeypatch):
    from fatebridge.core.local_techniques.heluo import build_heluo_result

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "auto")
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    line = case["line"]
    actual = build_heluo_result(**case["payload"])
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


def test_current_catalogue_binds_all_sources_to_actual_current_content():
    new = _catalogue()
    assert new["version"] == CATALOGUE_VERSION
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
