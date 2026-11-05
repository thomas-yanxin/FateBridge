"""Primary labels, nominal reconstructions and modern term names stay distinct."""

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import heluo_jiehou as jh
from fatebridge.core.heluo import solar_term
from fatebridge.core.heluo_hexagrams import _gua_tables
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.output_heluo_jiehou import (
    HeluoJiehouEvidence,
    JiehouLiteral,
    JiehouNominalDay,
)
from fatebridge.utils.errors import NumerologySourceError

ROOT = Path(__file__).parent / "fixtures/heluo_jiehou_v1"
REF = json.loads((ROOT / "reference.json").read_text())
MODEL_REF = json.loads((ROOT / "nominal-models.json").read_text())
CONTINUOUS = "continuous_yao_from_yi_four"


def evidence(term="冬至", quarter="坎"):
    # A synthetic, already-computed context, not a new astronomical reference.
    return jh.jiehou_evidence(
        dict(
            term=term,
            quarter=quarter,
            anchor_utc="2026-12-22T00:00:00+00:00",
            precision="birth_instant",
        )
    )


def test_source_witnesses_and_reading_limits():
    for w in REF["images"]:
        assert (
            hashlib.sha256((ROOT / w["file"]).read_bytes()).hexdigest() == w["sha256"]
        )
    assert [w["pdf_page"] for w in REF["images"]] == [41, 42, 43, 44]
    assert (
        REF["new_classical_horoscopes"]
        == REF["new_calendar_instants"]
        == REF["independent_second_reviews"]
        == 0
    )
    assert REF["printed_total_yao_phrase"] in jh._source()["printed_total_yao_phrase"]
    assert "三百六十四" in evidence()["printed_total_yao_phrase"]


@pytest.mark.parametrize("expected", REF["term_rows"])
def test_all_twenty_four_direct_term_assignments(expected):
    row = jh.term_assignment(expected["term"])
    assert {k: row[k] for k in expected} == expected
    bits = {
        "坎為水": [0, 1, 0, 0, 1, 0],
        "震為雷": [1, 0, 0, 1, 0, 0],
        "離為火": [1, 0, 1, 1, 0, 1],
        "兌為澤": [1, 1, 0, 1, 1, 0],
    }
    assert row["lines"] == bits[row["gua"]]


@pytest.mark.parametrize("simple,traditional", list(jh.ALIASES.items()))
def test_named_aliases_preserve_the_same_primary_row(simple, traditional):
    assert jh.term_assignment(simple) == jh.term_assignment(traditional)


@pytest.mark.parametrize("name", [None, True, 0, "", "初候", "春分后五日"])
def test_no_fuzzy_term_or_imputed_hou(name):
    with pytest.raises(ValueError):
        jh.term_assignment(name)


@pytest.mark.parametrize("expected", REF["hou_rows"])
def test_all_seventy_two_literal_labels_are_preserved(expected):
    row = next(
        r
        for r in jh.literal_hou_table()
        if (r["term"], r["entry_in_group"])
        == (expected["term"], expected["entry_in_group"])
    )
    assert {k: row[k] for k in expected} == expected
    JiehouLiteral.model_validate(row)


def test_four_polarity_differences_are_not_corrected_into_agreement():
    bad = [r for r in jh.literal_hou_table() if not r["yao_polarity_agrees"]]
    actual = [
        dict(
            term=r["term"],
            entry_in_group=r["entry_in_group"],
            gua=r["gua"],
            raw=r["raw_yao"],
            canonical=r["canonical_yao"],
        )
        for r in bad
    ]
    assert actual == REF["expected_yao_polarity_conflicts"]
    for row in bad:
        with pytest.raises(ValidationError):
            JiehouLiteral.model_validate({**row, "yao_polarity_agrees": True})


def test_sixty_order_is_all_gua_except_the_four_term_bases():
    order = jh._source()["gua_order"]
    assert order == REF["gua_order"] and len(order) == len(set(order)) == 60
    assert set(order) == set(_gua_tables()[0]) - {
        "坎為水",
        "震為雷",
        "離為火",
        "兌為澤",
    }
    assert Counter(r["gua"] for r in jh.literal_hou_table()) != Counter(order)


@pytest.mark.parametrize("row", REF["nominal_day_probes"])
def test_independent_manual_nominal_slots(row):
    actual = jh.nominal_hou_day(row["offset"], model=CONTINUOUS)
    assert (actual["gua"], actual["position"]) == (row["gua"], row["pos"])
    assert actual["derived_only"] is True
    assert actual["physical_date_applied"] is actual["extra_ke_applied"] is False
    JiehouNominalDay.model_validate(actual)


def test_nominal_cycle_has_360_slots_and_does_not_become_365_civil_days():
    rows = [jh.nominal_hou_day(n, model=CONTINUOUS) for n in range(360)]
    assert set(Counter(r["gua"] for r in rows).values()) == {6}
    assert Counter(r["position"] for r in rows) == {n: 60 for n in range(1, 7)}
    assert rows[0]["gua"] == rows[-1]["gua"] == "山雷頤"
    assert (rows[0]["position"], rows[-1]["position"]) == (4, 3)


@pytest.mark.parametrize("offset", [True, False, -1, 360, 365, 0.0, "0", None])
def test_no_silent_year_wrap_or_coercion(offset):
    with pytest.raises(ValueError):
        jh.nominal_hou_day(offset, model=CONTINUOUS)


@pytest.mark.parametrize("probe", MODEL_REF["probes"])
def test_two_explicit_models_keep_distinct_independent_manual_slots(probe):
    for model, key in zip(MODEL_REF["models"], ("continuous", "caption_first")):
        actual = jh.nominal_hou_day(probe["offset"], model=model)
        assert (actual["gua"], actual["position"]) == (
            probe[key]["gua"],
            probe[key]["pos"],
        )
        assert actual["model"] == model


def test_no_implicit_or_favorable_model_selection():
    with pytest.raises(TypeError):
        jh.nominal_hou_day(3)
    for model in (None, True, "best_fit", ""):
        with pytest.raises(ValueError):
            jh.nominal_hou_day(3, model=model)
    p = evidence()
    assert p["selected_reconstruction_model"] is None
    for m in p["reconstruction_models"]:
        expected = MODEL_REF["expected_counts"][m["model"]]
        assert m["caption_difference_count"] == expected["caption_differences"]
        assert (
            m["term_start_position_difference_count"]
            == expected["term_position_differences"]
        )
        assert m["term_start_gua_difference_count"] == expected["term_gua_differences"]
    p["selected_reconstruction_model"] = "six_days_per_gua_caption_first"
    with pytest.raises(ValidationError):
        HeluoJiehouEvidence.model_validate(p)


def test_printed_caption_conflicts_remain_in_the_actual_comparison():
    rows = jh.caption_comparison(model=CONTINUOUS)
    assert [r["printed"] for r in rows] == REF["caption"]["rows"]
    assert [r["derived"]["gua"] for r in rows] == REF["caption"][
        "derived_six_day_rule_names"
    ]
    assert [r["printed"]["day_label"] for r in rows if not r["agrees"]] == [23, 24, 25]
    assert [r["printed"]["position"] for r in rows] == [4, 5, 6, 1, 2, 3]
    assert all(r["printed"]["gua"] == "山雷頤" for r in rows)


def test_fifteen_day_projection_does_not_rewrite_eleven_printed_positions():
    rows = jh.term_start_comparisons(model=CONTINUOUS)
    expected = [
        "大寒",
        "雨水",
        "春分",
        "穀雨",
        "小滿",
        "夏至",
        "大暑",
        "處暑",
        "秋分",
        "霜降",
        "小雪",
    ]
    assert [r["term"] for r in rows if not r["position_agrees"]] == expected
    assert [
        (r["term"], r["printed_gua"], r["derived"]["gua"])
        for r in rows
        if not r["gua_agrees"]
    ] == [("大雪", "坤為地", "火水未濟")]
    assert all(r["interpretation_of_heading_unresolved"] is True for r in rows)
    assert all(r["derived"]["position"] == 4 for r in rows if not r["position_agrees"])


@pytest.mark.parametrize(
    "patch",
    [
        {"selected_hou": {}},
        {"huagong_assessment": True},
        {"historical_term_instants_established": True},
        {"historical_term_instants_established": 0},
        {"hou_physical_date_mapping_complete": 0},
        {"upstream_term_label": "夏至"},
        {"counts": {"nominal_gua_days": 6.0}},
        {"counts": {"nominal_gua_days": True}},
    ],
)
def test_typed_evidence_rejects_promoting_reconstruction_or_changing_context(patch):
    p = evidence()
    p.update(patch)
    with pytest.raises(ValidationError):
        HeluoJiehouEvidence.model_validate(p)


def test_typed_views_allow_only_the_known_partial_facts():
    HeluoJiehouEvidence.model_validate(dict(selected_term_gua=dict(position=2)))
    p = evidence()
    HeluoJiehouEvidence.model_validate(p)
    p["reconstruction_models"][0]["caption_comparison"][3]["agrees"] = True
    with pytest.raises(ValidationError):
        HeluoJiehouEvidence.model_validate(p)


@pytest.mark.parametrize(
    "patch",
    [
        dict(term="无此节"),
        dict(quarter="震"),
        dict(anchor_utc="2026-01-01T12:00:00"),
        dict(anchor_utc="2026-01-01T12:00:00+08:00"),
        dict(precision="guessed"),
    ],
)
def test_inconsistent_computed_context_is_an_internal_source_fault(patch):
    context = dict(
        term="冬至",
        quarter="坎",
        anchor_utc="2026-12-22T00:00:00+00:00",
        precision="birth_instant",
    )
    context.update(patch)
    with pytest.raises(NumerologySourceError) as error:
        jh.jiehou_evidence(context)
    assert error.value.reason == "runtime_heluo_jiehou_context_conflict"


def test_same_run_trace_snapshot_and_returned_rows_are_detached():
    r = build_heluo_result(
        date="2026-01-06", time="12:00", gender="男", use_true_solar_time=False
    )
    p = r["jiehou_evidence"]
    trace = next(
        t["facts"]
        for t in r["numerology_evidence"]["rule_trace"]
        if t["rule_id"] == jh.RULESET_ID
    )
    assert p == trace and p["upstream_term_label"] == r["solar_term"]["term"]
    assert p["anchor_utc"] == r["solar_term"]["anchor_utc"]
    assert p["selected_hou"] is p["huagong_assessment"] is None
    assert "火澤睽原印初六" in r["snapshot_text"]
    p["literal_hou_group"][2]["raw_yao"] = "初九"
    assert trace["literal_hou_group"][2]["raw_yao"] == "初六"
    assert jh.literal_hou_table()[5]["raw_yao"] == "初六"


def test_every_hko_2026_term_brackets_the_named_term_gua_without_fixed_fifteen_days():
    refs = json.loads((ROOT.parent / "calendar_hko_v1/reference.json").read_text())
    cases = [c for c in refs["cases"] if c["year"] == 2026]
    assert len(cases) == 24
    terms = [row["term"] for row in REF["term_rows"]]
    for case in cases:
        name = jh.ALIASES.get(case["term"], case["term"])
        index = terms.index(name)
        moment = datetime.fromisoformat(case["at"])
        for delta, expected in [
            (-2, REF["term_rows"][(index - 1) % 24]),
            (2, REF["term_rows"][index]),
        ]:
            at = moment + timedelta(minutes=delta)
            st = solar_term(at.year, at.month, at.day, "+00:00", birth_datetime=at)
            p = jh.jiehou_evidence(st)
            assert {k: p["selected_term_gua"][k] for k in expected} == expected
            assert (
                p["selected_hou"] is None
                and p["hou_physical_date_mapping_complete"] is False
            )


@pytest.mark.parametrize("fault", ["missing", "literal_correction", "identity"])
def test_source_digest_blocks_unversioned_literal_corrections(
    fault, tmp_path, monkeypatch
):
    p = tmp_path / "source.json"
    if fault != "missing":
        data = json.loads(jh.SOURCE_PATH.read_text())
        if fault == "literal_correction":
            data["hou_rows"][5]["raw_yao"] = "初九"
        else:
            data["ruleset_id"] = "another_printing"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    jh._source.cache_clear()
    try:
        monkeypatch.setattr(jh, "SOURCE_PATH", p)
        with pytest.raises(NumerologySourceError) as error:
            jh.literal_hou_table()
        assert error.value.reason == "invalid_heluo_jiehou_source"
    finally:
        jh._source.cache_clear()


def test_audit_rejects_selecting_the_caption_fitting_model(monkeypatch):
    from scripts import audit_numerology as audit

    original = jh.jiehou_evidence

    def fitted(context):
        p = original(context)
        p["selected_reconstruction_model"] = "six_days_per_gua_caption_first"
        return p

    monkeypatch.setattr(jh, "jiehou_evidence", fitted)
    result = audit.jiehou_source_checks()
    assert not result["checks_passed"]
    assert {"kind": "heluo_jiehou_unestablished_model_or_date"} in result["failures"]


def test_audit_rejects_erasing_literal_polarity_differences(monkeypatch):
    from scripts import audit_numerology as audit

    original = jh.literal_hou_table

    def corrected():
        rows = original()
        for row in rows:
            row["raw_yao"] = row["canonical_yao"]
            row["yao_polarity_agrees"] = True
        return rows

    monkeypatch.setattr(jh, "literal_hou_table", corrected)
    result = audit.jiehou_source_checks()
    assert not result["checks_passed"]
    assert {"kind": "heluo_jiehou_literal_polarity_differences"} in result["failures"]


def test_audit_rejects_omitting_the_model_with_caption_differences(monkeypatch):
    from scripts import audit_numerology as audit

    original = jh.jiehou_evidence

    def omitted(context):
        p = original(context)
        p["reconstruction_models"] = p["reconstruction_models"][1:]
        return p

    monkeypatch.setattr(jh, "jiehou_evidence", omitted)
    result = audit.jiehou_source_checks()
    assert not result["checks_passed"]
    assert {"kind": "heluo_jiehou_model_coverage"} in result["failures"]


@pytest.mark.parametrize(
    "fault", ["duplicated", "mixed_start", "wrong_term", "partial_wrong_position"]
)
def test_typed_models_preserve_model_coverage_and_term_context(fault):
    p = evidence()
    if fault == "duplicated":
        p["reconstruction_models"] = [p["reconstruction_models"][1]] * 2
    elif fault == "mixed_start":
        p["reconstruction_models"][0]["selected_term_start_comparison"] = p[
            "reconstruction_models"
        ][1]["selected_term_start_comparison"]
    elif fault == "wrong_term":
        p["reconstruction_models"][0]["selected_term_start_comparison"]["term"] = "夏至"
    else:
        p = dict(upstream_term_label="小寒", selected_term_gua=dict(position=3))
    with pytest.raises(ValidationError):
        HeluoJiehouEvidence.model_validate(p)
