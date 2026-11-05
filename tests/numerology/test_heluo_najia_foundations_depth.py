"""Eight primary base tables, five reused composite entries and actual source scope."""

import hashlib
import itertools
import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import heluo, heluo_najia
from fatebridge.core.heluo import hexagram_najia, judge, lines_to_gua
from fatebridge.core.output_numerology import HeluoNajiaCollation, HeluoNajiaLine
from fatebridge.utils.errors import NumerologySourceError
from tests.numerology.test_heluo_month_depth import chart_for
from tests.numerology.test_heluo_najia_depth import PILLARS

ROOT = Path(__file__).parents[1] / "fixtures/heluo_najia_foundations_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text())


def test_named_witnesses_and_no_inflated_independent_counts():
    assert REFERENCE["source_pdf_sha256"] == heluo_najia.SOURCE_SHA256
    for image in REFERENCE["images"]:
        assert (
            hashlib.sha256((ROOT / image["file"]).read_bytes()).hexdigest()
            == image["sha256"]
        )
    m = REFERENCE["najda_manifest"]
    assert hashlib.sha256((ROOT / m["file"]).read_bytes()).hexdigest() == m["sha256"]
    manifest = json.loads((ROOT / m["file"]).read_text())
    assert manifest["@id"] == m["url"] and manifest["label"] == "河洛理数　巻２下"
    assert len(REFERENCE["new_hexagram_entries"]) == 5
    assert REFERENCE["new_direct_assignment_observations"] == 30
    assert REFERENCE["new_borrowed_assignment_observations"] == 0
    assert REFERENCE["new_primary_source_images"] == 1
    for key in (
        "new_independent_reviews",
        "new_classical_birth_examples",
        "new_calendar_instants",
        "new_real_world_outcomes",
    ):
        assert REFERENCE[key] == 0


@pytest.mark.parametrize("case", REFERENCE["hexagram_entries"], ids=lambda c: c["gua"])
def test_thirteen_printed_assignment_lists(case):
    rows = hexagram_najia(case["lines"])
    assert [r["direct"] for r in rows] == case["direct"]
    assert [r["borrowed"] for r in rows] == case["borrowed"]
    annotated = heluo_najia.annotate_positions(case["gua"], case["lines"], rows)
    assert all(e["source"]["basis"] == "hexagram_entry" for e in annotated["lines"])
    assert all(
        e["source"]["source_pdf_page"] == case["page"] for e in annotated["lines"]
    )
    assert [e["source"]["source_assignment_index"] for e in annotated["lines"]] == list(
        range(1, 7)
    )


@pytest.mark.parametrize("bits", list(itertools.product((0, 1), repeat=6)))
def test_composite_application_to_all_hexagrams_is_counted_as_derived(bits):
    lines = list(bits)
    gua = lines_to_gua(lines)["name"]
    bases = {tuple(p["bits"]): p for p in REFERENCE["pure_tables"]}
    anchor = next(
        (p for p in REFERENCE["hexagram_entries"] if p["lines"] == lines), None
    )
    raw = hexagram_najia(lines)
    before = deepcopy(raw)
    result = heluo_najia.annotate_positions(gua, lines, raw)
    assert raw == before
    for pos, e in enumerate(result["lines"], 1):
        base = bases[tuple(lines[:3] if pos <= 3 else lines[3:])]
        assert e["direct"] == base["direct"][pos - 1]
        assert e["borrowed"] == base["borrowed"][pos - 1]
        source = e["source"]
        assert source["basis"] == ("hexagram_entry" if anchor else "pure_trigram_rule")
        assert source["source_hexagram"] == (anchor or base)["gua"]
        assert source["source_pdf_page"] == (anchor or base)["page"]


def test_distinct_base_slots_and_repeated_entry_observations_are_separate():
    summary = heluo_najia.collation_summary()
    assert summary["pure_trigram_tables"] == 8
    assert summary["pure_table_assignment_slots"] == 48
    assert summary["pure_table_borrowed_slots"] == 12
    assert summary["directly_collated_hexagrams"] == 13
    assert summary["other_hexagrams_not_individually_collated"] == 51
    assert summary["direct_assignment_observations"] == 78
    assert summary["borrowed_assignment_observations"] == 18
    assert summary["complete_assessment"] is False
    assert summary["review_status"].endswith("independent_second_review_pending")
    assert (
        summary["sha256"]
        == hashlib.sha256(heluo_najia.COLLATION_PATH.read_bytes()).hexdigest()
    )
    HeluoNajiaCollation.model_validate(summary)


@pytest.mark.parametrize(
    "gua,year,pos,kind,source_gua,page,basis",
    [
        ("風雷益", "庚寅", 2, "direct", "震為雷", 240, "pure_trigram_rule"),
        ("雷水解", "庚申", 5, "direct", "震為雷", 240, "pure_trigram_rule"),
        ("地雷復", "乙丑", 4, "borrowed", "坤為地", 122, "pure_trigram_rule"),
        ("艮為山", "丙寅", 6, "direct", "艮為山", 243, "hexagram_entry"),
        ("澤水困", "戊午", 3, "direct", "坎為水", 187, "pure_trigram_rule"),
    ],
)
def test_actual_year_match_uses_its_own_source_position(
    gua, year, pos, kind, source_gua, page, basis
):
    out = judge(chart_for(gua), {**PILLARS, "year": year}, "卯")
    for row in out["najia"]:
        assert row["matches"] == [{"pos": pos, "kind": kind}]
        assert row["lines"][pos - 1]["source"] == dict(
            basis=basis,
            source_hexagram=source_gua,
            source_pdf_page=page,
            source_assignment_index=pos,
        )


def test_jie_has_two_same_order_printings_without_reordered_computation_or_source_certification():
    chart = chart_for("雷水解")
    out = judge(chart, {**PILLARS, "year": "庚申"}, "卯")
    row = out["najia"][0]
    issue = row["source_issues"][0]
    assert len(issue["witnesses"]) == 2
    assert issue["literal_najia_list"] == [
        "戊寅",
        "戊辰",
        "戊午",
        "庚午",
        "庚戌",
        "庚申",
    ]
    assert issue["rule_derived_positional_list"] == [e["direct"] for e in row["lines"]]
    assert issue["literal_najia_list"] != issue["rule_derived_positional_list"]
    assert set(issue["literal_najia_list"]) == set(
        issue["rule_derived_positional_list"]
    )
    assert issue["ordinal_list_semantics_resolved"] is False
    assert all(e["source"]["basis"] == "pure_trigram_rule" for e in row["lines"])
    text = heluo_najia.najia_snapshot(out["najia"])
    assert "计算第5爻正纳" in text and "两印本原文列举末两支顺序" in text
    assert "按纯卦内外位推演" in text


def test_source_readers_and_phase_lists_are_detached():
    rows = hexagram_najia([0, 1, 0, 1, 0, 0])
    out = heluo_najia.annotate_positions("雷水解", [0, 1, 0, 1, 0, 0], rows)
    out["lines"][0]["borrowed"].append("调用方写入")
    out["source_issues"][0]["witnesses"].clear()
    summary = heluo_najia.collation_summary()
    summary["source_order_issues"][0]["witnesses"].clear()
    assert rows[0]["borrowed"] == []
    assert (
        len(heluo_najia.collation_summary()["source_order_issues"][0]["witnesses"]) == 2
    )
    assert (
        len(
            heluo_najia.annotate_positions("雷水解", [0, 1, 0, 1, 0, 0], rows)[
                "source_issues"
            ][0]["witnesses"]
        )
        == 2
    )


def test_wrong_runtime_assignment_is_rejected_instead_of_retaining_source_claim(
    monkeypatch,
):
    bad = deepcopy(heluo.NAJIA)
    bad["艮"][-1] = "丙寅"
    monkeypatch.setattr(heluo, "NAJIA", bad)
    with pytest.raises(NumerologySourceError, match="实际正纳／借用.*原页"):
        judge(chart_for("艮為山"), {**PILLARS, "year": "丙寅"}, "卯")


@pytest.mark.parametrize(
    "key",
    [
        "identity",
        "duplicate_bits",
        "wrong_pure_slot",
        "wrong_composite_slot",
        "invalid_ganzhi",
    ],
)
def test_incoherent_source_basis_does_not_load(key, monkeypatch, tmp_path):
    data = json.loads(heluo_najia.COLLATION_PATH.read_text())
    if key == "identity":
        data["source_pdf_sha256"] = "0" * 64
    elif key == "duplicate_bits":
        data["pure_tables"][1]["bits"] = data["pure_tables"][0]["bits"][:]
    elif key == "wrong_pure_slot":
        data["pure_tables"][0]["direct"][0] = "甲寅"
    elif key == "wrong_composite_slot":
        next(a for a in data["hexagram_entries"] if a["gua"] == "水雷屯")["direct"][
            0
        ] = "庚寅"
    else:
        data["hexagram_entries"][0]["direct"][0] = "甲丑"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(data))
    heluo_najia._source.cache_clear()
    try:
        monkeypatch.setattr(heluo_najia, "COLLATION_PATH", p)
        with pytest.raises(NumerologySourceError) as caught:
            heluo_najia._source()
        assert caught.value.reason == "invalid_source_data"
    finally:
        heluo_najia._source.cache_clear()


@pytest.mark.parametrize(
    "payload",
    [
        {"source": {"source_assignment_index": True}},
        {"source": {"source_assignment_index": 7}},
        {"source": {"basis": "complete_book_certified"}},
    ],
)
def test_typed_source_facts_reject_invented_values(payload):
    with pytest.raises(ValidationError):
        HeluoNajiaLine.model_validate(payload)


def test_complete_assessment_cannot_be_inferred_from_full_base_coverage():
    with pytest.raises(ValidationError):
        HeluoNajiaCollation.model_validate(
            {"pure_trigram_tables": 8, "complete_assessment": True}
        )


@pytest.mark.parametrize(
    "clause", REFERENCE["new_month_najia_clauses"], ids=lambda c: c["gua"]
)
def test_four_new_month_and_najia_phrases_keep_actual_facts_and_unresolved_connector(
    clause,
):
    from fatebridge.core.heluo_months import MONTH_BRANCHES

    base = next(p for p in REFERENCE["pure_tables"] if p["gua"] == clause["gua"])
    outside = next(m for m in range(1, 13) if m not in clause["month_numbers"])
    for month, label_match in [(clause["month_numbers"][0], True), (outside, False)]:
        result = judge(
            chart_for(clause["gua"]),
            {**PILLARS, "year": base["direct"][0]},
            MONTH_BRANCHES[month - 1],
        )
        assert result["month_affinity"]["registered_natal_najia_clauses"] == 13
        for phase in result["month_affinity"]["phases"]:
            actual = phase["natal_najia_clause"]
            assert (
                actual["rule_id"],
                actual["literal"],
                actual["source_pdf_page"],
            ) == (clause["id"], clause["literal"], clause["page"])
            assert actual["month_label_match"] is label_match
            assert actual["najia"]["present"] is True
            assert actual["najia"]["matches"] == [{"pos": 1, "kind": "direct"}]
            assert actual["match"] is None


def test_kan_timeliness_phrase_does_not_become_an_invented_fixed_month():
    summary = heluo_najia.collation_summary()
    nuance = summary["unquantified_timing_najia_clauses"][0]
    assert nuance["gua"] == "坎為水" and nuance["page"] == 187
    assert nuance["literal"] == "生於及時與納甲者" and nuance["month_numbers"] is None
    result = judge(chart_for("坎為水"), {**PILLARS, "year": "戊寅"}, "亥")
    assert result["deTime"] is True
    assert all(
        p["natal_najia_clause"] is None for p in result["month_affinity"]["phases"]
    )


def test_month_cache_hash_and_data_version_identify_loaded_bytes(monkeypatch, tmp_path):
    from fatebridge.core import heluo_months

    original = heluo_months.COLLATION_PATH.read_bytes()
    path = tmp_path / "month.json"
    path.write_bytes(original)
    heluo_months._collation.cache_clear()
    try:
        monkeypatch.setattr(heluo_months, "COLLATION_PATH", path)
        before = heluo_months.month_affinity(chart_for("乾為天"), "巳", heluo.MONTH_GUA)
        changed = json.loads(original)
        changed["version"] = "test-next"
        changed["scope"] = "Synthetic revision for loaded-byte identity test."
        path.write_text(json.dumps(changed, ensure_ascii=False))
        cached = heluo_months.month_affinity(chart_for("乾為天"), "巳", heluo.MONTH_GUA)
        assert cached["scope"] == before["scope"]
        assert (
            cached["collation_sha256"]
            == before["collation_sha256"]
            == hashlib.sha256(original).hexdigest()
        )
        assert cached["collation_version"] == json.loads(original)["version"]
        heluo_months._collation.cache_clear()
        reloaded = heluo_months.month_affinity(
            chart_for("乾為天"), "巳", heluo.MONTH_GUA
        )
        assert (
            reloaded["collation_sha256"]
            == hashlib.sha256(path.read_bytes()).hexdigest()
        )
        assert (
            reloaded["collation_version"] == "test-next"
            and reloaded["scope"] == changed["scope"]
        )
    finally:
        heluo_months._collation.cache_clear()
