"""All source readings survive profile selection and actual month evaluation."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import heluo_months as months
from fatebridge.core.heluo import MONTH_GUA, judge
from fatebridge.core.output_numerology import HeluoMonthAffinity
from fatebridge.core.requests.divination import HeluoRequest
from fatebridge.utils.errors import NumerologySourceError
from tests.test_heluo_month_depth import chart_for
from tests.test_heluo_najia_depth import PILLARS

ROOT = Path(__file__).parent / "fixtures/heluo_month_profiles_v1"
FRONT = json.loads((ROOT / "front-table-reference.json").read_bytes())
INTRO = {
    r["gua"]: r
    for r in json.loads((ROOT / "intro-reference.json").read_bytes())["assigned_months"]
}
DIFFERENCES = json.loads((ROOT / "first-comparison.json").read_bytes())["differences"]


def test_preproduction_reference_identity_and_failed_hypothesis_are_preserved():
    manifest = json.loads((ROOT / "manifest.json").read_bytes())
    assert manifest["production_changes_started"] is False
    for name, digest in manifest["images_and_references"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
    hypothesis = json.loads((ROOT / "shi-hypothesis-results.json").read_bytes())
    assert len(hypothesis["all64"]) == 64
    assert (hypothesis["front_failures"], hypothesis["intro_failures"]) == (5, 1)
    assert hypothesis["static_month_hypothesis_verified"] is False
    assert manifest["independent_second_reviews"] == 0


@pytest.mark.parametrize("source", FRONT["assigned_months"], ids=lambda r: r["gua"])
def test_every_month_of_every_source_hexagram_in_both_profiles(source):
    gua = source["gua"]
    chart = chart_for(gua)
    intro = INTRO.get(gua)
    for method, selected in [
        ("intro_preferred_v1", intro or source),
        ("volume_one_table_v1", source),
    ]:
        for number, branch in enumerate(months.MONTH_BRANCHES, 1):
            result = months.month_affinity(
                chart, branch, MONTH_GUA, assignment_method=method
            )
            HeluoMonthAffinity.model_validate(result)
            assert result["assignment_method"] == method
            assert (
                result["explicit_assigned_months"],
                result["volume_one_explicit_months"],
            ) == (63, 64)
            assert len(result["source_assignment_conflicts"]) == 5
            assert result["complete_assessment"] is False
            expected_matches = [
                number == intro["month"] if intro else None,
                number == source["month"],
            ]
            consensus = (
                expected_matches[0]
                if intro and len(set(expected_matches)) == 1
                else None
            )
            assert result["source_consensus_match"] is consensus
            for phase in result["phases"]:
                assert phase["assigned_month_number"] == selected["month"]
                assert phase["assigned_month_match"] is (number == selected["month"])
                assert phase["source_pdf_page"] == selected["page"]
                assert [
                    r["month_label_match"] for r in phase["source_readings"]
                ] == expected_matches
                assert phase["source_readings"][1]["literal"] == source["literal"]
                assert phase["source_consensus_match"] is consensus
                assert phase["source_months_agree"] is (
                    intro["month"] == source["month"] if intro else None
                )


@pytest.mark.parametrize("row", DIFFERENCES, ids=lambda r: r["gua"])
def test_source_choice_changes_computation_without_resolving_the_book(row):
    chart = chart_for(row["gua"])
    for m, expected_intro, expected_table in [
        (row["intro_month"], True, False),
        (row["front_month"], False, True),
    ]:
        branch = months.MONTH_BRANCHES[m - 1]
        intro = judge(chart, PILLARS, branch)
        table = judge(
            chart, PILLARS, branch, month_assignment_method="volume_one_table_v1"
        )
        assert intro["deTime"] is expected_intro
        assert table["deTime"] is expected_table
        assert intro["month_affinity"]["source_consensus_match"] is None
        assert table["month_affinity"]["source_consensus_match"] is None
        assert (
            intro["month_affinity"]["source_assignment_conflicts"]
            == table["month_affinity"]["source_assignment_conflicts"]
        )
        assert {
            k: v for k, v in intro.items() if k not in {"deTime", "month_affinity"}
        } == {k: v for k, v in table.items() if k not in {"deTime", "month_affinity"}}


def test_wuwang_has_direct_table_evidence_and_an_unstated_intro_month():
    result = months.month_affinity(chart_for("天雷無妄"), "酉", MONTH_GUA)
    assert result["source_consensus_match"] is None
    for p in result["phases"]:
        assert p["assigned_month_match"] is True
        assert p["source_pdf_page"] == 18
        assert p["selected_month_source"] == "volume_one_table"
        a, b = p["source_readings"]
        assert a["month_number"] is a["month_label_match"] is None
        assert (a["source_pdf_page"], a["status"]) == (177, "month_not_explicit")
        assert (b["month_number"], b["source_pdf_page"]) == (8, 18)
    assert any("五世" in s for s in result["unresolved"])


def test_phase_consensus_or_does_not_treat_unknown_as_false_or_hide_positive():
    chart = chart_for("火澤睽")
    chart["hou"] = chart_for("火天大有")["hou"]
    assert (
        months.month_affinity(chart, "卯", MONTH_GUA)["source_consensus_match"] is None
    )
    assert (
        months.month_affinity(chart, "寅", MONTH_GUA)["source_consensus_match"] is True
    )
    assert (
        months.month_affinity(chart, "午", MONTH_GUA)["source_consensus_match"] is False
    )


@pytest.mark.parametrize("method", [None, "", "best", 1, True])
def test_unknown_profile_is_rejected_at_request_and_domain(method):
    payload = dict(
        date="2000-02-10",
        time="12:00",
        gender="男",
        use_true_solar_time=False,
        month_assignment_method=method,
    )
    with pytest.raises(ValidationError):
        HeluoRequest.model_validate(payload)
    with pytest.raises(ValueError):
        months.month_affinity(
            chart_for("乾為天"), "巳", MONTH_GUA, assignment_method=method
        )


@pytest.mark.parametrize(
    "file_attr,cache,key",
    [
        ("COLLATION_PATH", "_collation", "assigned_months"),
        ("FRONT_TABLE_PATH", "_front_table", "assigned_months"),
        ("COLLATION_PATH", "_collation", "natal_najia_clauses"),
        ("COLLATION_PATH", "_collation", "review_status"),
    ],
)
def test_fact_edits_cannot_retain_valid_source_identity(
    monkeypatch, tmp_path, file_attr, cache, key
):
    data = json.loads(getattr(months, file_attr).read_bytes())
    if key == "assigned_months":
        data[key][0]["month"] = 3
    elif key == "natal_najia_clauses":
        data[key][0]["literal"] += "篡改"
    else:
        data[key] = "independently_confirmed"
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(data, ensure_ascii=False))
    getattr(months, cache).cache_clear()
    try:
        monkeypatch.setattr(months, file_attr, path)
        with pytest.raises(NumerologySourceError):
            months.month_affinity(chart_for("乾為天"), "巳", MONTH_GUA)
    finally:
        getattr(months, cache).cache_clear()


def test_front_profile_consumes_its_source_instead_of_an_unused_legacy_table():
    bad = copy.deepcopy(MONTH_GUA)
    bad["卯"].remove("睽")
    with pytest.raises(NumerologySourceError):
        months.month_affinity(chart_for("火澤睽"), "辰", bad)
    result = months.month_affinity(
        chart_for("火澤睽"), "辰", bad, assignment_method="volume_one_table_v1"
    )
    assert all(p["assigned_month_match"] is True for p in result["phases"])


@pytest.mark.parametrize(
    "file_attr,cache",
    [("COLLATION_PATH", "_collation"), ("FRONT_TABLE_PATH", "_front_table")],
)
@pytest.mark.parametrize("invalid", [None, [], "not-a-source", 1])
def test_non_object_source_is_a_source_error(
    monkeypatch, tmp_path, file_attr, cache, invalid
):
    p = tmp_path / "non-object.json"
    p.write_text(json.dumps(invalid))
    getattr(months, cache).cache_clear()
    try:
        monkeypatch.setattr(months, file_attr, p)
        with pytest.raises(NumerologySourceError):
            months.month_affinity(chart_for("乾為天"), "巳", MONTH_GUA)
    finally:
        getattr(months, cache).cache_clear()


def test_main_auditor_keeps_literal_conflicts_separate_from_engineering_checks():
    from scripts.audit_numerology import month_source_profile_checks

    result = month_source_profile_checks()
    assert result["engine_profile_checks_passed"] is True
    assert result["engine_profile_checks"] == 3072
    assert len(result["all64_source_rows"]) == 64
    assert len(result["source_consistency_failures"]) == 5
    assert result["source_consistency_passed"] is False
    assert result["authority_system"] is False
