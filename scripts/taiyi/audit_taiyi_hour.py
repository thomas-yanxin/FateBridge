"""Audit the complete Key hour example and separate calendar-unit conflicts."""

from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.taiyi_gates import (
    attach_gate_board,
    key_hour_gate_cycle,
)
from fatebridge.core.metaphysics.taiyi_hour import KEY_HOUR_PROFILE
from fatebridge.core.metaphysics.taiyi_year import BRANCHES, assemble_board, cyclic_core

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/taiyi_jinjing_v6"
FIELDS = {
    "accumulation",
    "kook_number",
    "taiyi_number",
    "wenchang_palace",
    "jishen",
    "heshen",
    "shiji",
    "main_count",
    "main_general",
    "main_vice_general",
    "guest_count",
    "guest_general",
    "guest_vice_general",
    "dingmu",
    "set_count",
    "set_general",
    "set_vice_general",
    "duty_gate",
    "unit_in_gate",
    "menju_jiangfa",
}
UNIT_REQUIREMENTS = {
    "year_equals_24_terms_under_uniform_day_divisor",
    "lunation_integral_equals_mean_lunation_under_uniform_day_divisor",
    "quotation_year_numeral_equals_this_facsimile",
}


def worked_board(case: dict[str, Any]) -> dict[str, Any]:
    inputs = case["input"]
    count = (inputs["day_number"] - 1) * 12 + inputs["hour_number"]
    core = cyclic_core(count, yin=inputs["yin"])
    core.update(ruler_branch=BRANCHES[inputs["hour_number"] - 1], ruler_label="时支")
    core["heshen"] = BRANCHES[(1 - BRANCHES.index(core["ruler_branch"])) % 12]
    board: dict[str, Any] = assemble_board(core)
    board.update(
        calendar_rules={"hour_profile": KEY_HOUR_PROFILE},
        rotation="逆布" if inputs["yin"] else "顺布",
    )
    attach_gate_board(board, "hour")
    return board


def audit(corpus: Path = CORPUS) -> dict[str, Any]:
    path = corpus / "manifest.json"
    manifest = json.loads(path.read_text())
    mandatory = {
        "hour-worked.json",
        "calendar-units.json",
        "door-sequences.json",
        "key-page44.jpg",
        "key-page45.jpg",
        "key-page46.jpg",
        "tongzong-page18.jpg",
        "qian-excerpt.txt",
    }
    if not mandatory <= {s["file"] for s in manifest["source_files"]}:
        raise ValueError("完整时计例、未决课语和历法冲突来源不得删除")
    for item in manifest["source_files"] + manifest["prior_source_references"]:
        if (
            hashlib.sha256((corpus / item["file"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError("时计冻结来源指纹不符：" + item["file"])
    case = json.loads((corpus / "hour-worked.json").read_text())
    if set(case["expected"]) != FIELDS:
        raise ValueError("完整课例须保留20项，包括尚未裁定的门具语")
    board = worked_board(case)
    actual = {
        **board["core_board"],
        "wenchang_palace": board["wenchang_palace"],
        **{k: board["gates"]["counter"][k] for k in ("duty_gate", "unit_in_gate")},
        "menju_jiangfa": board["condition_assessment"]["menju_jiangfa"],
    }
    differences, unknown = [], []
    for field, expected in case["expected"].items():
        row = {
            "field": field,
            "source_value": expected,
            "computed_value": actual[field],
        }
        if actual[field] is None:
            unknown.append(row)
        elif actual[field] != expected:
            differences.append(row)
    sequences = json.loads((corpus / "door-sequences.json").read_text())["cases"]
    if len(sequences) != 8 or {(c["yin"], c["accumulation"]) for c in sequences} != {
        (y, a) for y in (False, True) for a in (1, 31, 61, 91)
    }:
        raise ValueError("阴阳四门须保留两遁各四项")
    sequence_differences = [
        {
            **c,
            "computed_value": key_hour_gate_cycle(c["accumulation"], c["yin"])[
                "duty_gate"
            ],
        }
        for c in sequences
        if key_hour_gate_cycle(c["accumulation"], c["yin"])["duty_gate"]
        != c["duty_gate"]
    ]
    units = json.loads((corpus / "calendar-units.json").read_text())
    if set(units["requirements"]) != UNIT_REQUIREMENTS:
        raise ValueError("历法量纲及引文异数三项检查不得删除")
    book = {k: Fraction(v) for k, v in units["book"].items()}
    qian = {k: Fraction(v) for k, v in units["qian"].items()}
    pairs = [
        (
            "year_equals_24_terms_under_uniform_day_divisor",
            book["year_integral"] / book["day_divisor"],
            24
            * (
                book["mean_term_days"]
                + book["mean_term_fraction"] / book["day_divisor"]
            ),
            "days",
        ),
        (
            "lunation_integral_equals_mean_lunation_under_uniform_day_divisor",
            book["lunation_integral"] / book["day_divisor"],
            book["mean_lunation_days"]
            + book["mean_lunation_fraction"] / book["day_divisor"],
            "days",
        ),
        (
            "quotation_year_numeral_equals_this_facsimile",
            book["year_integral"],
            qian["year_integral"],
            "original_fraction_units",
        ),
    ]
    unit_checks = [
        {
            "id": key,
            "left": str(left),
            "right": str(right),
            "unit": unit,
            "difference": str(left - right),
            "equal": left == right,
            "status": (
                "consistent"
                if left == right
                else (
                    "uniform_unit_hypothesis_rejected"
                    if "uniform_day_divisor" in key
                    else "quotation_numeral_difference_unresolved"
                )
            ),
        }
        for key, left, right, unit in pairs
    ]
    # Qian explicitly distinguishes the 10,000-denominator term/lunation
    # constants. These exact relations reject the uniform-unit hypothesis;
    # failed hypothesis checks are not two independent errors in the book.
    # Neither reading changes either source's printed numerals.
    alternative = {
        "source": "钱氏原跋指出气朔二策用万分日法；本项是明示异单位解释，不是改本图数字",
        "term_equals_year_divided_by_24": book["year_integral"]
        / book["day_divisor"]
        / 24
        == book["mean_term_days"]
        + book["mean_term_fraction"] / qian["qishuo_day_divisor"],
        "mean_lunation_equals_lunation_integral": book["lunation_integral"]
        / book["day_divisor"]
        == book["mean_lunation_days"]
        + book["mean_lunation_fraction"] / qian["qishuo_day_divisor"],
        "applied_to_public_calendar": False,
    }
    short = cyclic_core(case["shortcut_counter"], yin=case["input"]["yin"])
    return {
        "completion_claim": False,
        "corpus_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "hour_example": {
            "required_fields": 20,
            "evaluated_fields": 20 - len(unknown),
            "matching_fields": 20 - len(unknown) - len(differences),
            "disagreements": differences,
            "unadjudicated": unknown,
            "actual": {k: actual[k] for k in case["expected"]},
        },
        "four_gate_sequences": {
            "required_fields": 8,
            "matching_fields": 8 - len(sequence_differences),
            "disagreements": sequence_differences,
            "oracle_kind": "two_transcribed_rule_sequences_not_historical_cases",
        },
        "shortcut_scope_check": {
            "oracle_kind": "scope_guard_not_an_independent_case",
            "source_scope": case["shortcut_scope"],
            "same_taiyi_palace": short["taiyi_number"] == actual["taiyi_number"],
            "full_counter_wenchang": actual["wenchang_palace"],
            "shortcut_as_full_counter_wenchang": short["wenchang_palace"],
            "complete_counter_replacement_valid": False,
        },
        "calendar_units": {
            "checks": unit_checks,
            "qian_distinct_unit_reading": alternative,
            "diagnostic_scope": "前两项否定统一分母假设，不计作原书两项计算错误；第三项保留引文与本图岁实异数。不是三个古历时刻验收样本。",
            "dimension_interpretation": "mixed_units_supported_by_primary_commentary_and_exact_relations",
            "unresolved_source_questions": [
                "quotation_year_numeral_equals_this_facsimile"
            ],
            "policy": units["policy"],
            "source_consistency_passed": all(r["equal"] for r in unit_checks),
        },
        "hour_example_acceptance_passed": not differences and not unknown,
        "whole_book_conformance": "not_established",
        "calendar_adapter_validated_for_ancient_dates": False,
        "real_world_efficacy": "not_tested",
        "implementation_sha256": {
            n: hashlib.sha256(
                (ROOT / "src/fatebridge/core/metaphysics" / n).read_bytes()
            ).hexdigest()
            for n in (
                "taiyi_hour.py",
                "taiyi_periods.py",
                "taiyi_gates.py",
                "taiyi_year.py",
            )
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")
    return (
        0
        if report["hour_example_acceptance_passed"]
        and not report["four_gate_sequences"]["disagreements"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
