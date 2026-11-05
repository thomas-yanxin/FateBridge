"""Special-day source readings must not silently replace or complete each other."""

import json
from pathlib import Path

import pytest

from fatebridge.core.sukuyo import SU27_ORDER, calendar_mansion, day_evidence
from fatebridge.core.sukuyo_special_days import source_bundle, special_day_evidence
from fatebridge.services.tool_catalog import CATALOG
from fatebridge.validation.sukuyo import required_quote_paths

PRIMARY = json.loads(
    (Path(__file__).parents[1] / "data/sukuyo-special-days-primary.json").read_text()
)
ALIASES = str.maketrans("虛婁畢參張軫", "虚娄毕参张轸")


def reference_evidence(mansion, weekday, candidates=()):
    return special_day_evidence(
        mansion, weekday, candidates, weekday_basis="modern_utc_plus08_civil_midnight"
    )


def comparison(result, witness):
    return next(w for w in result["comparisons"] if w["witness"] == witness)


def test_all_84_slots_have_source_clauses_and_substantive_apparatus():
    bundle = source_bundle()
    assert bundle["source_sha256"] == PRIMARY["source_sha256"]
    assert sum(len(w["rows"]) for w in bundle["witnesses"]) == 84
    apparatus = {a["id"]: a["text"] for a in PRIMARY["apparatus"]}
    for witness in bundle["witnesses"]:
        for row in witness["rows"]:
            source = next(
                p
                for p in PRIMARY["paragraphs"]
                if p["volume"] == witness["volume"] and p["label"] == row["label"]
            )
            assert row["locator"] == source["locator"]
            assert row["source_clause"] in source["text"]
            assert (
                row["source_main_literal"]
                == PRIMARY["expected_main_tables"][witness["volume"]][row["label"]][
                    row["source_main_weekday_index"]
                ]
            )
            for app in row["apparatus"]:
                assert app["literal"] == apparatus[app["id"]]
            if (
                row["literal_mansion"] != row["source_main_literal"]
                or row["weekday_index"] != row["source_main_weekday_index"]
            ):
                assert row["apparatus"] and not row["source_clause_is_witness_reading"]
    for rule in bundle["activity_rules"]:
        label = "甘露" if rule["selectors"] == ["甘露"] else "罗刹"
        source = next(
            p
            for p in PRIMARY["paragraphs"]
            if p["volume"] == rule["volume"] and p["label"] == label
        )
        assert all(excerpt in source["text"] for excerpt in rule["source_excerpts"])


def test_all_756_mansion_weekday_witness_cells_against_primary_tables():
    # The four manually transcribed tables in the primary fixture supply the
    # oracle, including the unresolved main-text 冒 and 底. No runtime output
    # or the new production table is used to generate expected labels.
    checked = 0
    for name in SU27_ORDER:
        for weekday in range(7):
            result = reference_evidence(name, weekday)
            for witness in [result["primary"], *result["comparisons"]]:
                tables = (
                    PRIMARY["expected_main_tables"]
                    if witness["edition"] == "taisho"
                    else PRIMARY["expected_ming_tables"]
                )
                table = tables[witness["volume"]]
                expected = [
                    label
                    for label, sequence in table.items()
                    if sequence[weekday].translate(ALIASES) == name
                ]
                assert witness["matched_labels"] == expected, (
                    name,
                    weekday,
                    witness["witness"],
                )
                unresolved = any(
                    sequence[weekday].translate(ALIASES) not in SU27_ORDER
                    for sequence in table.values()
                )
                assert witness["labels_complete_for_selected_day"] is (not unresolved)
                if witness["witness"] != "upper_taisho":
                    assert witness["disagrees_with_primary"] is (
                        None
                        if unresolved
                        else expected != result["primary"]["matched_labels"]
                    )
                checked += 1
    assert checked == 756


def test_ming_alternatives_do_not_change_the_selected_main_text():
    tail = reference_evidence("尾", 2)
    well = reference_evidence("井", 2)
    assert tail["primary"]["matched_labels"] == ["甘露"]
    assert comparison(tail, "upper_ming_apparatus")["matched_labels"] == []
    assert well["primary"]["matched_labels"] == []
    assert comparison(well, "upper_ming_apparatus")["matched_labels"] == ["甘露"]
    # Ming reconstructions differ between volumes too; never form a hybrid.
    assert comparison(well, "lower_ming_apparatus")["matched_labels"] == []
    for name, weekday in [("女", 1), ("昴", 2), ("壁", 3)]:
        result = reference_evidence(name, weekday)
        assert result["primary"]["matched_labels"] == []
        assert comparison(result, "upper_ming_apparatus")["matched_labels"] == [
            "金刚峰"
        ]
    # The weekday changes belong to the original clause that moves, not to
    # the old occupant of the destination weekday slot.
    for name, day, clause, source_day, app in [
        ("昴", 2, "昴宿水直", 3, "0392040"),
        ("壁", 3, "壁宿火直", 2, "0392039"),
    ]:
        row = comparison(reference_evidence(name, day), "upper_ming_apparatus")[
            "matched_rows"
        ][0]
        assert row["source_clause"] == clause
        assert row["source_main_weekday_index"] == source_day
        assert row["apparatus"][0]["id"] == app


@pytest.mark.parametrize("name,weekday,literal", [("胃", 0, "冒"), ("氐", 4, "底")])
def test_lower_unidentified_literals_are_not_silently_normalized(
    name, weekday, literal
):
    result = reference_evidence(name, weekday)
    lower = comparison(result, "lower_taisho")
    assert result["primary"]["matched_labels"] == ["罗刹"]
    assert lower["matched_labels"] == [] and lower["disagrees_with_primary"] is None
    assert lower["unresolved_rows"][0]["literal_mansion"] == literal
    assert lower["unresolved_rows"][0]["mansion"] is None
    assert comparison(result, "lower_ming_apparatus")["matched_labels"] == ["罗刹"]
    assert not comparison(result, "lower_ming_apparatus")["applied_to_primary"]


def test_ganlu_learning_requires_religious_scope_and_retains_each_volume():
    context = calendar_mansion("2025-04-15")
    assert context["natal_su27"] == "尾"
    generic = day_evidence(context, activity="study")
    skill = day_evidence(context, activity="study", activity_details=["skill_learning"])
    religious = day_evidence(
        context, activity="study", activity_details=["religious_learning"]
    )
    ids = {
        "t1299_special_upper_ganlu_learning_v1",
        "t1299_special_lower_ganlu_learning_v1",
    }
    for result in [generic, skill]:
        assert not ids.intersection(
            r["rule_id"] for r in result["activity_assessment"]["matched_rules"]
        )
        assert ids <= {
            r["rule_id"] for r in result["activity_assessment"]["conditional_rules"]
        }
    matched = [
        r
        for r in religious["activity_assessment"]["matched_rules"]
        if r["rule_id"] in ids
    ]
    assert len(matched) == 2 and {r["source_witness"] for r in matched} == {
        "upper_taisho",
        "lower_taisho",
    }
    assert all(
        r["detail_match"]["satisfied_details"] == ["religious_learning"]
        for r in matched
    )


def test_unknown_lower_source_caution_remains_pending_even_with_a_favorable_clause():
    # Sunday with 轸 matches known 甘露, but lower 冒 remains unresolved.
    result = day_evidence(
        calendar_mansion("2025-09-21"),
        activity="study",
        activity_details=["religious_learning"],
    )
    assert result["day_mansion"] == "轸"
    pending = next(
        r
        for r in result["activity_assessment"]["conditional_rules"]
        if r["rule_id"] == "t1299_special_lower_rasetsu_v1"
    )
    assert pending["requires_textual_review"] and not pending["applied_to_aggregate"]
    assert result["activity_assessment"]["unresolved_source_rules_present"]
    assert "冒" in pending["topic_condition"]
    assert "不把未匹配当作无此特殊日" in result["reading_text"]
    assert "月亮合宿" in result["reading_text"]
    assert not result["special_day_evidence"]["physical_lunar_conjunction_evaluated"]


def test_partial_mansion_candidates_never_become_selected_special_days():
    result = reference_evidence(None, 1, ["毕", "心"])
    assert result["primary"]["matched_labels"] == []
    assert not result["primary"]["labels_complete_for_selected_day"]
    assert result["candidate_primary"] == [
        {"mansion": "毕", "matched_labels": ["甘露"], "applied_to_primary": False},
        {"mansion": "心", "matched_labels": ["金刚峰"], "applied_to_primary": False},
    ]
    context = calendar_mansion("2024-08-04", calendar_profile="hinoo_t1299_host27")
    day = day_evidence(
        context, activity="study", activity_details=["religious_learning"]
    )
    assert day["special_day_labels"] == []
    assert not any(
        r["layer"] == "lower_special_day"
        for r in day["activity_assessment"]["matched_rules"]
    )


def test_schema_context_and_return_isolation_preserve_source_comparison():
    for invalid in [-1, 7, True, 2.0]:
        with pytest.raises(ValueError):
            reference_evidence("尾", invalid)
    with pytest.raises(ValueError):
        reference_evidence("牛", 0)
    result = reference_evidence("尾", 2)
    result["primary"]["matched_rows"][0]["literal_mansion"] = "井"
    assert (
        reference_evidence("尾", 2)["primary"]["matched_rows"][0]["literal_mansion"]
        == "尾"
    )
    assert "sukuyo.special_day_evidence" in required_quote_paths("activity")
    spec = next(s for s in CATALOG if s.key == "suzhan")
    defs = spec.output_model.model_json_schema()["$defs"]
    assert "special_day_evidence" in defs["SukuyoDay"]["properties"]
    assert "unresolved_rows" in defs["SukuyoSpecialWitness"]["properties"]
    assert (
        "unresolved_source_rules_present"
        in defs["SukuyoActivityAssessment"]["properties"]
    )
