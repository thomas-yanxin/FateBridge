"""Subtype definitions, retained source disagreements and temporal precision."""

import importlib.util
import json
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from fatebridge.core.almanac import get_solar_terms_for_year
from fatebridge.core.metaphysics.liureng import build_liureng_board
from fatebridge.services.metaphysics import (
    calculate_jinkou_analysis,
    calculate_liureng_gods,
)
from tests.ren.test_ren_classical_depth import AUDIT as V1

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "audit_ren_rules", ROOT / "scripts/ren/audit_ren_rules.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def board(day, upper):
    branches = "子丑寅卯辰巳午未申酉戌亥"
    houses = dict(zip("甲乙丙丁戊己庚辛壬癸", "寅辰巳未巳未申戌亥丑"))
    offset = (branches.index(upper) - branches.index(houses[day[0]])) % 12
    return build_liureng_board(
        V1.make_seed(dict(day=day, hour="子")), month_general_override=branches[offset]
    )


@pytest.mark.parametrize(
    "day,upper,labels",
    [
        ("甲子", "巳", ["始入"]),
        ("甲子", "丑", ["比用"]),
        ("丙寅", "子", ["知一"]),
        ("乙丑", "辰", ["杜传", "始入"]),
        ("癸丑", "丑", ["不虞", "元首"]),
        ("丁卯", "未", ["杜传"]),
        ("辛未", "辰", ["无亲", "井栏射"]),
        ("辛未", "丑", ["别责"]),
        ("甲申", "申", ["无依", "重审"]),
        ("己未", "酉", ["八专", "独足"]),
        ("丙辰", "子", ["比用"]),
        ("戊辰", "戌", ["重审"]),
    ],
)
def test_named_subtypes_follow_explicit_source_rules_and_selected_scan(
    day, upper, labels
):
    result = board(day, upper)
    assert result["classification"]["labels"] == labels
    assert (
        next(
            t["result"]
            for t in result["rule_trace"]
            if t["rule_id"] == "liuren.named_subtypes"
        )
        == result["classification"]
    )


def test_subtype_count_keeps_duplicate_lessons_even_when_selection_deduplicates():
    result = board("甲子", "辰")
    assert result["classification"]["lower_thief_lessons"] == [1, 4]
    assert result["classification"]["upper_killer_lessons"] == []
    assert result["classification"]["labels"] == ["重审"]
    assert result["meta"]["selected_lesson_index"] == 1


@pytest.mark.parametrize(
    "day,upper,annotation,page",
    [
        ("丁卯", "申", "涉害", 48),
        ("戊辰", "未", "重审", 49),
        ("戊申", "卯", "元首", 59),
    ],
)
def test_known_source_annotations_are_visible_without_overriding_the_calculation(
    day, upper, annotation, page
):
    result = board(day, upper)
    detail = result["classification"]
    assert detail["source_note"]["annotation"] == annotation
    assert detail["source_note"]["original_pdf_page"] == page
    assert (
        detail["source_note"]["source_sha256"]
        == AUDIT.load_reference()["naming"]["original_sha256"]
    )
    assert detail["labels"] != [annotation]
    assert f"影印表注{annotation}" in detail["basis"]


def test_full_label_comparison_keeps_raw_errors_and_unresolved_annotations():
    report = AUDIT.audit()
    assert report["implemented_rule_checks_passed"]
    names = report["names"]
    assert names["case_count"] == 720
    assert names["raw_exact_matches"] == 715
    assert names["after_selected_scan_collation_exact_matches"] == 717
    assert len(names["scan_corrections"]) == 2
    assert len(names["remaining_literal_mismatches"]) == 3
    assert any(
        c["relationship"] == "calculated_subtype_of_broad_source_name"
        for c in names["remaining_literal_mismatches"]
    )
    assert not names["literal_name_conformance_passed"]
    assert report["branch_sequences"] == {"case_count": 720, "failures": []}
    assert len(report["qi_checks"]) == 46
    assert len(report["hko_calendar"]) == 96
    assert len(report["month_general_boundary_probes"]) == 144
    assert all(
        c["matched"]
        for c in report["qi_checks"]
        + report["hko_calendar"]
        + report["month_general_boundary_probes"]
    )
    assert not report["goal_complete"]
    assert not report["classical_acceptance_passed"]
    assert any(r["status"] == "unverified" for r in report["requirement_inventory"])


def test_progressing_month_qi_is_not_the_seasonal_five_state_label():
    result = V1.observe_jinkou(
        dict(day="甲子", hour="子", ground="子", general="卯", month="寅")
    )
    general = next(row for row in result["rows"] if row["label"] == "将神")
    assert general["seasonal_power"] == "旺"
    assert result["qi_evidence"]["month_qi_label"] == "进气相"
    assert result["qi_evidence"]["month_offset"] == 1
    assert (
        next(
            t["result"]
            for t in result["rule_trace"]
            if t["rule_id"] == "jinkou.month_day_qi"
        )
        == result["qi_evidence"]
    )


def test_day_support_uses_day_branch_and_does_not_invent_a_daily_five_state():
    result = V1.observe_jinkou(
        dict(day="甲申", hour="子", ground="子", general="亥", month="寅")
    )
    qi = result["qi_evidence"]
    assert qi["day_element"] == "金"  # 申, not 甲木.
    assert qi["day_generates_general"] is True
    assert qi["month_qi_label"] is None
    assert qi["month_qi_status"] == "not_classified_by_excerpt"
    assert "日下五态" in qi["scope"]
    assert "day_power" not in result


@pytest.mark.parametrize(
    "calculate", [calculate_liureng_gods, calculate_jinkou_analysis]
)
def test_supplied_seconds_survive_one_minute_zhongqi_transition(calculate):
    term = next(
        t for t in get_solar_terms_for_year(2026, "Asia/Shanghai") if t.name == "雨水"
    )
    before = term.moment.replace(microsecond=0) - timedelta(seconds=1)
    after = term.moment.replace(microsecond=0) + timedelta(seconds=1)
    assert before.minute == after.minute
    observed = []
    for moment in (before, after):
        result = calculate(
            analysis_year=moment.year,
            analysis_month=moment.month,
            analysis_day=moment.day,
            analysis_hour=moment.hour,
            analysis_minute=moment.minute,
            analysis_second=moment.second,
            analysis_timezone="Asia/Shanghai",
            use_true_solar_time=False,
        )
        observed.append(result["liureng"]["month_general"]["branch"])
        assert result["analysis_context"]["input_datetime"].endswith(
            f":{moment.second:02d}"
        )
    assert observed == ["子", "亥"]
    # This is a precision/plumbing probe around the provider's own crossing.
    # Independent astronomical comparisons are the published HKO minutes above.


@pytest.mark.parametrize("name", ["naming.json", "qi.json", "source-pages.pdf"])
def test_new_reference_cannot_silently_drift(tmp_path, name):
    target = tmp_path / "reference"
    shutil.copytree(AUDIT.CORPUS, target)
    p = target / name
    p.write_bytes(p.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="Reference changed"):
        AUDIT.load_reference(target)


def test_older_reference_layers_are_unchanged():
    original = V1.load_frozen_corpus()
    assert len(original["cases"]["unresolved"]) == 2
    raw = json.loads(
        (ROOT / "tests/fixtures/ren_depth_v2/tanyuan-table.json").read_text()
    )
    assert (
        next(c for c in raw["cases"] if c["day"] == "丙辰" and c["gan_upper"] == "子")[
            "style"
        ]
        == "重审"
    )
