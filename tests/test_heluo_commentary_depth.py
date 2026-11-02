"""Source excerpts, conditional text fidelity and unverified poem separation.

The reference was hand-read by the same reviewer, not an independent second
collation. Selection probes do not count as original historical horoscopes.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from fatebridge.core import heluo_texts
from fatebridge.core.heluo import _tiaowen, build_snapshot_text, yao_text
from fatebridge.core.heluo_texts import (
    COMMENTARY_PATH,
    commentary_collation_summary,
)
from fatebridge.core.heluo_timing import _selected_text
from fatebridge.core.local_techniques.heluo import build_heluo_result
from tests.heluo_ben22_revision_reference import CURRENT_HEADERS as R96_HEADERS
from tests.heluo_current_source_reference import (
    CURRENT_HEADERS,
    HEADER_COUNT,
    PENDING_COUNT,
)
from tests.heluo_guan_shi_revision_reference import NEW_HEADERS as R84_NEW_HEADERS
from tests.heluo_guan_shi_revision_reference import REVISION as R84_REVISION
from tests.heluo_shike_bi_revision_reference import CURRENT_HEADERS as R92_HEADERS
from tests.heluo_shike_bi_revision_reference import assert_r92_source_addition

ROOT = Path(__file__).parent / "fixtures/numerology_nlc_v1"
REFERENCE = json.loads((ROOT / "commentary-reference.json").read_text())
KEYS = [(g, p) for g in ("乾為天", "坤為地") for p in range(1, 7)]


@pytest.mark.parametrize("case", REFERENCE["cases"])
def test_source_excerpts_repair_recorded_inherited_errors(case):
    selected = yao_text(case["hexagram"], case["line"])
    for excerpt in case["source_excerpts"]:
        assert excerpt in selected["detail"]
    for wrong in case["inherited_errors"]:
        assert wrong not in selected["detail"]
        assert wrong in selected["text_provenance"]["inherited_detail"]
    assert selected["text_provenance"]["commentary_pdf_pages"] == case["pdf_pages"]


def test_identity_keeps_old_twelve_cases_and_six_reused_witnesses():
    summary = commentary_collation_summary()
    assert summary["sha256"] == hashlib.sha256(COMMENTARY_PATH.read_bytes()).hexdigest()
    assert summary["source_pdf_sha256"] == REFERENCE["source_pdf_sha256"]
    assert summary["collated_line_commentaries"] == HEADER_COUNT
    assert summary["pending_line_commentaries"] == PENDING_COUNT
    assert summary["total_line_commentaries"] == 384
    assert summary["collated_poems"] == 0
    assert "independent_second_review_pending" in summary["review_status"]
    assert {i["pdf_page"] for i in REFERENCE["images"]} == set(range(119, 125))
    for witness in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / witness["file"]).read_bytes()).hexdigest()
            == witness["sha256"]
        )


@pytest.mark.parametrize("gua,pos", KEYS)
def test_full_text_preserves_conditional_sections_and_does_not_select_them(gua, pos):
    selected = yao_text(gua, pos)
    sections = selected["commentary_sections"]
    ids = [s["section_id"] for s in sections]
    assert ids[:3] == ["opening", "xie", "buxie"] and ids[-1] == "annual"
    assert "".join(s["text"] for s in sections) == selected["detail"]
    assert all(s["applicability"] is None for s in sections)
    assert (
        next(s for s in sections if s["section_id"] == "xie")["condition_label"]
        == "葉者"
    )
    assert (
        next(s for s in sections if s["section_id"] == "buxie")["condition_label"]
        == "不葉者"
    )
    assert sections[-1]["condition_label"] == "歲運逢之"
    assert selected["commentary_branch_selection"]["status"] == "not_evaluated"
    assert selected["commentary_branch_selection"]["selected_section_ids"] == []
    assert selected["text_provenance"]["automatic_branch_selection"] is False


def test_secondary_conditions_stay_with_their_literal_context():
    kun = yao_text("坤為地", 1)["commentary_sections"]
    assert "蓋必生於陽月可也" in kun[1]["text"]
    assert "惟陰命則大興家業" in kun[-1]["text"]
    qian = yao_text("乾為天", 6)["commentary_sections"]
    assert qian[-2]["condition_label"] == "若是女命"
    assert qian[-2]["section_id"] == "female"
    assert qian[-2]["applicability"] is None


def test_kun_four_has_one_annual_branch_without_interleaved_duplicate():
    text = yao_text("坤為地", 4)["detail"]
    assert text.count("歲運逢之") == 1
    assert text.count("在庶俗則經營阻滯") == 1
    assert text.count("大凡宜謹固收斂") == 1
    assert text.index("在仕則") < text.index("在士則") < text.index("在庶俗則")


@pytest.mark.parametrize("gua,pos", KEYS)
def test_poem_and_verdict_never_inherit_commentary_source_approval(gua, pos):
    selected = yao_text(gua, pos)
    inherited = _tiaowen()[gua]["yao"][str(pos)]
    if gua in {"乾為天", "坤為地", "水雷屯"}:
        assert selected["text_provenance"]["inherited_shige"] == inherited["shige"]
        assert (
            selected["text_provenance"]["poem_source_pdf_sha256"]
            != selected["text_provenance"]["commentary_source_pdf_sha256"]
        )
    else:
        assert selected["shige"] == inherited["shige"]
    assert selected["verdict"] == inherited["verdict"]
    provenance = selected["text_provenance"]
    assert provenance["commentary_status"] == "source_commentary_visually_collated"
    assert provenance["poem_status"] == (
        "source_poems_visually_collated"
        if gua in {"乾為天", "坤為地", "水雷屯"}
        else "inherited_poem_source_unverified"
    )
    assert provenance["poem_presence_in_reviewed_sections"] is False
    assert (
        provenance["verdict_status"] == "inherited_summary_not_source_branch_judgment"
    )


def test_other_commentaries_still_pending_and_inherited_cache_unchanged():
    before = copy.deepcopy(_tiaowen())
    kun = yao_text("坤為地", 4)
    kun["commentary_sections"][1]["text"] = "污染"
    kun["text_provenance"]["commentary_pdf_pages"].append(999)
    kun["text_provenance"]["commentary_reading_notes"].append("污染")
    kun["commentary_branch_selection"]["selected_section_ids"].append("xie")
    clean = yao_text("坤為地", 4)
    assert "污染" not in str(clean)
    assert 999 not in clean["text_provenance"]["commentary_pdf_pages"]
    assert clean["commentary_branch_selection"]["selected_section_ids"] == []
    newly_collated = yao_text("水天需", 1)
    assert (
        newly_collated["text_provenance"]["commentary_status"]
        == "source_commentary_visually_collated"
    )
    original_control = yao_text("風地觀", 1)
    frozen = R84_REVISION["record_extensions"]["風地觀:1"]["fields"]
    assert original_control["detail"] == frozen["detail"]
    assert original_control["commentary_sections"] == frozen["commentary_sections"]
    assert (
        original_control["text_provenance"]["inherited_detail"]
        == before["風地觀"]["yao"]["1"]["detail"]
    )
    assert_r92_source_addition()
    assert R92_HEADERS["entries"][:120] == R84_NEW_HEADERS["entries"]
    from tests.heluo_bo23_revision_reference import CURRENT_HEADERS as R101_HEADERS

    assert R101_HEADERS["entries"][:132] == R96_HEADERS["entries"]
    assert CURRENT_HEADERS["entries"][:138] == R101_HEADERS["entries"]
    reviewed = {e["hexagram"] for e in CURRENT_HEADERS["entries"]}
    assert R96_HEADERS["entries"][:126] == R92_HEADERS["entries"]
    assert (
        len(reviewed) == HEADER_COUNT // 6
        and set(heluo_texts.COMMENTARY_HEXAGRAMS) == reviewed
    )
    assert len(_tiaowen()) == 64
    pending_count = 0
    for gua in _tiaowen():
        if gua in reviewed:
            continue
        for pos in range(1, 7):
            uncollated = yao_text(gua, pos)
            assert uncollated["text_provenance"]["commentary_status"].endswith(
                "pending"
            )
            assert "commentary_sections" not in uncollated
            assert (
                "poem_presence_in_reviewed_sections"
                not in uncollated["text_provenance"]
            )
            pending_count += 1
    assert pending_count == PENDING_COUNT
    assert before == _tiaowen()


def test_natal_and_timing_use_actual_line_while_preserving_branch_uncertainty():
    chart = {
        "tian": 1,
        "tianGua": "乾",
        "di": 2,
        "diGua": "坤",
        "xian": {"name": "坤為地", "lines": [0] * 6, "yuan": 4},
        "hou": {"name": "乾為天", "lines": [1] * 6, "yuan": 6},
    }
    snapshot = build_snapshot_text(chart, None, None)
    assert "常職而難於陞遷" in snapshot
    # Reading notes quote the rejected reading to explain the choice. The
    # complete used commentary must retain the source reading independently.
    used_commentary = yao_text("乾為天", 6)["detail"]
    assert used_commentary in snapshot
    assert "高而無名" in used_commentary and "高而無民" not in used_commentary
    assert "另据卷三PDF" in snapshot
    assert "象曰的具体来源未由诗诀底本核定" in snapshot
    assert "条件分支未自动选取" in snapshot
    selected = _selected_text(
        {"gua": "坤為地", "pos": 4, "changed_pos": 1, "lines": [0] * 6},
        "day_ordinal",
    )
    assert selected["heluo_commentary"] == yao_text("坤為地", 4)
    assert selected["heluo_commentary"] != yao_text("坤為地", 1)


def test_same_run_trace_matches_selected_text_source_and_snapshot():
    result = build_heluo_result(
        date="2000-03-08", time="09:33:00", gender="女", use_true_solar_time=False
    )
    evidence = result["numerology_evidence"]
    selected = evidence["selected_texts"][1]
    assert (selected["hexagram"], selected["line"]) == ("乾為天", 6)
    trace = next(
        t["facts"]
        for t in evidence["rule_trace"]
        if t["rule_id"] == "heluo_selected_line_collation_v1"
    )
    assert trace["commentary_sha256"] == evidence["commentary_collation"]["sha256"]
    assert trace["selections"][1]["corpus_key"] == selected["corpus_key"]
    assert trace["selections"][1]["commentary_pdf_pages"] == [121]
    assert selected["text"]["detail"] in result["snapshot_text"]
    assert (
        selected["text"]["text_provenance"]["commentary_sha256"]
        == trace["commentary_sha256"]
    )


@pytest.mark.parametrize("layer", ["header", "commentary"])
def test_provenance_hash_identifies_loaded_bytes_even_if_file_changes(
    layer, monkeypatch, tmp_path
):
    """A cached old reading must not borrow a newly edited file's hash."""
    path_name, loader, summary = (
        ("COLLATION_PATH", heluo_texts._collation, heluo_texts.collation_summary)
        if layer == "header"
        else (
            "COMMENTARY_PATH",
            heluo_texts._commentary_collation,
            heluo_texts.commentary_collation_summary,
        )
    )
    raw = getattr(heluo_texts, path_name).read_bytes()
    path = tmp_path / "collation.json"
    path.write_bytes(raw)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(heluo_texts, path_name, path)
            loader.cache_clear()
            first = summary()["sha256"]
            original = yao_text("乾為天", 1)
            changed = json.loads(raw)
            if layer == "header":
                changed["entries"][0]["yaoci"] = "已替換的新文件"
            else:
                changed["entries"][0]["sections"][0]["text"] = "已替換的新文件"
            path.write_text(json.dumps(changed, ensure_ascii=False))
            assert hashlib.sha256(path.read_bytes()).hexdigest() != first
            assert summary()["sha256"] == first == hashlib.sha256(raw).hexdigest()
            assert yao_text("乾為天", 1) == original
    finally:
        loader.cache_clear()
