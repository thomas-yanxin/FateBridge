"""Primary authored examples, honest time ambiguity, and narrow name equivalence."""

import copy
import json
import shutil
from datetime import date

import pytest

from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.services.metaphysics import _build_analysis_seed
from scripts.audit_liuren_tanyuan_cases import (
    ALIAS_CORPUS,
    CORPUS,
    PROFILE,
    alias_reference,
    board_facts,
    calendar_comparison,
    canonical_gods,
    expected_facts,
    reference,
    sha,
    title_names,
)

DATA = reference()


def seed_for(ref, sample):
    solar = date.fromisoformat(ref["solar_date"])
    minute = sample["minute_of_day"]
    return _build_analysis_seed(
        analysis_year=solar.year,
        analysis_month=solar.month,
        analysis_day=solar.day,
        analysis_hour=minute // 60,
        analysis_minute=minute % 60,
        analysis_timezone="+08:00",
        use_true_solar_time=False,
    )


def test_complete_section_and_calendar_cohort_are_not_selected_by_result():
    cases = DATA["readings"]["cases"]
    refs = DATA["reference"]["cases"]
    assert [c["id"] for c in cases] == [f"C{i:02}" for i in range(1, 9)]
    assert sum(len(r["samples"]) for r in refs) == 960
    assert [r["solar_date"] for r in refs] == [
        "1909-09-01",
        "1910-01-01",
        "1910-01-23",
        "1910-01-25",
        "1910-10-27",
        "1910-11-28",
        "1910-12-22",
        "1911-01-03",
    ]
    assert DATA["reference"]["historical_instant_certified"] is False
    assert DATA["protocol"]["new_empirical_events"] == 0
    assert DATA["protocol"]["new_llm_processes"] == 0


@pytest.mark.parametrize("index", range(8))
def test_authored_chart_and_title_with_explicit_book_profile(index):
    alias_reference()
    case, ref = DATA["readings"]["cases"][index], DATA["reference"]["cases"][index]
    sample = ref["samples"][0]
    seed = seed_for(ref, sample)
    board = build_liureng_board(seed, guiren_profile=PROFILE)
    assert all(calendar_comparison(seed, board, ref, sample).values())
    actual = board_facts(board, "".join(seed.pillars["day"]))
    expected = expected_facts(case)
    assert canonical_gods(actual) == canonical_gods(expected)
    # Preserve the literal disagreement, even when the explicit alias explains it.
    assert (actual == expected) is (index < 5)
    assert case["printed_title"] in title_names(board)
    unresolved = board["day_placement_patterns"]["evaluations"][-2:]
    assert [r["matched"] for r in unresolved] == [None, None]
    if case["id"] == "C03":
        assert "D08" in board["day_placement_patterns"]["matched_ids"]


def test_zi_hour_preserves_both_civil_segments_and_changed_chart():
    ref = DATA["reference"]["cases"][1]
    samples = ref["samples"]
    assert [s["minute_of_day"] for s in samples] == list(range(60)) + list(
        range(1380, 1440)
    )
    assert sum(s["printed_day_agrees"] for s in samples) == 60
    early, late = seed_for(ref, samples[0]), seed_for(ref, samples[60])
    assert early.pillars["day"] == ("丙", "寅")
    assert late.pillars["day"] == ("丁", "卯")
    assert (
        build_liureng_board(early, guiren_profile=PROFILE)["three_transmissions"]
        != build_liureng_board(late, guiren_profile=PROFILE)["three_transmissions"]
    )


@pytest.mark.parametrize(
    "field", ["lunar", "day", "hour", "month_branch", "month_general"]
)
def test_independent_calendar_binding_detects_wrong_producer_field(field):
    ref = DATA["reference"]["cases"][0]
    sample = ref["samples"][0]
    seed = seed_for(ref, sample)
    board = build_liureng_board(seed, guiren_profile=PROFILE)
    if field == "lunar":
        seed.calendar_context["lunar_calendar"]["day"] += 1
    elif field == "day":
        seed.pillars["day"] = ("乙", "丑")
    elif field == "hour":
        seed.pillars["hour"] = ("甲", "子")
    elif field == "month_branch":
        seed.pillars["month"] = ("甲", "寅")
    else:
        board["month_general"]["branch"] = "子"
    assert calendar_comparison(seed, board, ref, sample)[field] is False


def test_alias_cannot_hide_wrong_branch_wrong_god_or_missing_fact():
    expected = expected_facts(DATA["readings"]["cases"][5])
    for field, replacement in (
        ("transmission_branches", ["子", "未", "丑"]),
        ("transmission_gods", ["天后", "朱雀", "太常"]),
        ("lessons_upper_lower", ["申丁", "未未", "酉酉", "酉酉"]),
        ("lesson_gods", ["朱雀", "朱雀", "贵人"]),
    ):
        fault = copy.deepcopy(expected)
        fault[field] = replacement
        assert canonical_gods(fault) != canonical_gods(expected)
    assert expected["transmission_gods"][0] == "天乙"
    assert canonical_gods(expected)["transmission_gods"][0] == "贵人"
    assert expected["transmission_gods"][0] == "天乙"


@pytest.mark.parametrize("fault", ["bytes", "coordinated_rehash", "extra", "missing"])
def test_original_reference_and_case_inventory_are_immutable(tmp_path, fault):
    folder = tmp_path / "cases"
    shutil.copytree(CORPUS, folder)
    path = folder / "readings.json"
    if fault in ("bytes", "coordinated_rehash"):
        path.write_text(path.read_text() + " ")
        if fault == "coordinated_rehash":
            freeze = json.loads((folder / "freeze.json").read_text())
            freeze["files"][path.name] = sha(path)
            (folder / "freeze.json").write_text(json.dumps(freeze))
    elif fault == "extra":
        (folder / "exclude-failed-case.json").write_text("{}")
    else:
        path.unlink()
    with pytest.raises(ValueError, match="Frozen authored-case"):
        reference(folder)


def test_post_audit_alias_review_cannot_be_expanded(tmp_path):
    folder = tmp_path / "aliases"
    shutil.copytree(ALIAS_CORPUS, folder)
    path = folder / "review.json"
    review = json.loads(path.read_text())
    review["aliases"]["天后"] = "贵人"
    path.write_text(json.dumps(review, ensure_ascii=False))
    with pytest.raises(ValueError, match="Frozen alias review"):
        alias_reference(folder)
