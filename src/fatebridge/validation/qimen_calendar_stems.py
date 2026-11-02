"""Separate printed stem examples from modern civil-lunar calendar checks."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.qimen import _qimen_build_palaces, _qimen_zhifu_zhishi
from fatebridge.core.qimen_calendar_stems import match_calendar_stems
from fatebridge.services.metaphysics import calculate_qimen_analysis


def audit_calendar_stems(directory: Path) -> dict[str, Any]:
    reference = json.loads((directory / "sources-and-anchors.json").read_text())
    cases = reference["classical_cases"]
    if len(cases) != 2 or {c["id"] for c in cases} != {
        "vol2-year-xin-yang5-guiyou",
        "vol2-month-ji-yang8-dingmao",
    }:
        raise ValueError("须保留岁格与月朔格两条独立印例")
    dates = {c["date"] for c in reference["calendar_cases"]}
    if (
        len(reference["calendar_cases"]) != 15
        or len(dates) != 15
        or {d[:7] for d in dates if d.startswith("2026")}
        != {f"2026-{m:02d}" for m in range(1, 13)}
        or not {"2025-06-25", "2025-07-25", "2024-02-10"} <= dates
    ):
        raise ValueError("须保留十二个2026月初、平闰六月及月朔甲的十五项参考")
    required_files = {
        "hko-lunar-2024.pdf",
        "hko-lunar-2025.pdf",
        "hko-lunar-2026.pdf",
        "../qimen_classical_v5/siku-pages-29-31-32.pdf",
        "../qimen-calendar-hko-2026.json",
    }
    if (
        len(reference["source_files"]) != len(required_files)
        or {s["file"] for s in reference["source_files"]} != required_files
    ):
        raise ValueError("须保留完整岁月格来源文件清单")
    for entry in reference["source_files"]:
        path = (directory / entry["file"]).resolve()
        if not path.is_relative_to(directory.resolve().parent):
            raise ValueError("岁月格参考路径越界")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("岁月格参考文件指纹不一致")
    disagreements, observations = [], []
    for case in cases:
        text = f'{case["dun"]}{"一二三四五六七八九"[case["ju"]-1]}局上元'
        leader = _qimen_zhifu_zhishi(case["hour"], text, dun_type=case["dun"])
        board = {
            "palaces": _qimen_build_palaces(
                time_ganzhi=case["hour"],
                ju_text=text,
                dun_type=case["dun"],
                current_term="立春",
            )
        }
        contexts = {
            role: {"status": "source_not_supplied"}
            for role in ("year", "lunar_month_start")
        }
        contexts[case["role"]] = {
            "status": "literal_stem_resolved",
            "ganzhi": case["source_ganzhi"],
            "effective_stem": case["literal_stem"],
            "calendar_basis": "printed_literal_stem_only_no_historical_date_reconstruction",
        }
        patterns = match_calendar_stems(
            board,
            contexts,
            leader=leader,
            source="https://ourartnet.com/King_James/Hushulei/047.pdf",
        )
        palaces = [
            p["trigram"]
            for p in board["palaces"]
            if any(
                m["palace"] == p["name"] and m["rule_id"] == case["rule_id"]
                for m in patterns
            )
        ]
        row = {
            "case_id": case["id"],
            "expected": [case["palace"]],
            "actual": palaces,
            "scope": "printed_literal_stem_palace_only",
        }
        observations.append(row)
        if palaces != [case["palace"]]:
            disagreements.append(row)
    for case in reference["calendar_cases"]:
        at = datetime.fromisoformat(case["date"])
        result = calculate_qimen_analysis(
            analysis_year=at.year,
            analysis_month=at.month,
            analysis_day=at.day,
            analysis_hour=12,
            analysis_timezone="Asia/Hong_Kong",
            use_true_solar_time=False,
        )
        anchor = result["qimen"]["stem_context"]["lunar_month_start"]
        actual = {
            key: anchor[key]
            for key in (
                "anchor_date",
                "calendar_year",
                "lunar_month",
                "is_leap_month",
                "ganzhi",
            )
        }
        expected = {
            "anchor_date": case["date"],
            "calendar_year": case["lunar_year"],
            "lunar_month": case["lunar_month"],
            "is_leap_month": case["is_leap_month"],
            "ganzhi": case["anchor_ganzhi"],
        }
        if actual != expected:
            disagreements.append(
                {
                    "case_id": case["date"],
                    "expected": expected,
                    "actual": actual,
                    "scope": "modern_hko_date_with_derived_ganzhi",
                }
            )
    return {
        "printed_literal_stem_examples": 2,
        "printed_observations": observations,
        "calendar_reference_count": 15,
        "calendar_ganzhi_precision": "derived_from_independent_day_anchor_not_individually_published",
        "disagreements": disagreements,
        "historical_example_dates_reconstructed": False,
        "year_boundary_policy_certified": False,
        "jia_substitution_certified": False,
        "whole_book_conformance_established": False,
        "real_world_efficacy": "not_tested",
    }
