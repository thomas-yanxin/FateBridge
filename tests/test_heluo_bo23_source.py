"""Fixed source requirements; run before adoption and retain every failure."""

import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core.heluo import gua_lines, lines_to_gua, yao_text

W = Path(__file__).parent / "fixtures/heluo_bo23_v1"
LITERAL = json.loads((W / "reviewed-literals-v2.json").read_text())


def test_source_first_draft_and_before_references_remain_frozen():
    assert (
        hashlib.sha256((W / "reviewed-literals-v2.json").read_bytes()).hexdigest()
        == "e9c6317eb3a4c30bbca3adc2112d1d38823f1e42fb1439cdb319ac02d81d80a6"
    )
    assert (
        hashlib.sha256((W / "reviewed-literals-v1.json").read_bytes()).hexdigest()
        == "bc0d4b85237500a45497726bccde76c2a975a65f1197256f5d0517873cee13f7"
    )
    assert (
        hashlib.sha256((W / "source-first-draft.json").read_bytes()).hexdigest()
        == "ab002dcab9db0eee95a07d553e0c3d8099375c69bb53167144feaaaaee846f46"
    )
    first = json.loads((W / "first-draft-seal.json").read_text())
    for name, sha in first["files"].items():
        assert hashlib.sha256((W / name).read_bytes()).hexdigest() == sha
    freeze = json.loads((W / "reviewed-reference-freeze.json").read_text())
    assert (
        hashlib.sha256((W / "reviewed-literals-v1.json").read_bytes()).hexdigest()
        == freeze["reviewed_literals_sha256"]
    )
    assert freeze["before_any_runtime_or_existing_test_edit"] is True
    assert LITERAL["independent_review"] is False


@pytest.mark.parametrize("entry", LITERAL["entries"], ids=lambda e: f"line{e['line']}")
def test_current_header_complete_parents_and_source_qualifications(entry):
    actual = yao_text("山地剝", entry["line"])
    assert actual["yaoci"] == entry["yaoci"]
    assert actual["detail"] == "".join(s["text"] for s in entry["sections"])
    assert actual["commentary_sections"] == [
        dict(s, applicability=None) for s in entry["sections"]
    ]
    assert (
        actual["text_provenance"]["commentary_reading_notes"] == entry["reading_notes"]
    )
    assert actual["commentary_branch_selection"]["selected_section_ids"] == []


@pytest.mark.parametrize(
    "reference",
    LITERAL["conditional_references"],
    ids=lambda r: f"line{r['source_line']}",
)
def test_explicit_printed_reference_retains_condition_and_does_not_replace_chart(
    reference,
):
    actual = yao_text("山地剝", reference["source_line"])
    rows = actual.get("commentary_cross_references", [])
    assert (
        len(rows) == 1
    ), "Printed conditional reference is missing from the structured result."
    row = rows[0]
    for k in [
        "condition_text",
        "source_quote",
        "target_hexagram",
        "target_line",
        "target_line_source_status",
        "source_context_text",
    ]:
        assert row[k] == reference[k]
    assert row["source_section_id"] == reference["section_id"]
    assert row["source_condition_label"] == reference["condition_label"]
    assert row["applicability"] is None
    assert row["automatic_application"] is row["replaces_chart"] is False


@pytest.mark.parametrize("line,target", [(4, "火地晉"), (6, "坤為地")])
def test_single_line_geometric_identity_is_separate_from_source_applicability(
    line, target
):
    before = gua_lines("艮", "坤")
    assert before == [0, 0, 0, 0, 0, 1]
    changed = before[:]
    changed[line - 1] = 1 - changed[line - 1]
    assert lines_to_gua(changed)["name"] == target


def test_bo5_retains_its_printed_traditional_wu_instead_of_copying_Bo3_form():
    assert "无咎" in yao_text("山地剝", 3)["yaoci"]
    assert "無不利" in yao_text("山地剝", 5)["yaoci"]
    assert "无不利" not in yao_text("山地剝", 5)["yaoci"]
