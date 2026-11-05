"""Independent branch walks for Ming cycle rules and gender invariants."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.ziwei_auxiliary import attach_natal_cycles
from fatebridge.core.ziwei_cycle_sources import cycle_source_evidence

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/data/ziwei_independent"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"


def walk(sequence: list[str], start: str, sign: int) -> dict[str, str]:
    result = {}
    pointer = BRANCHES.index(start)
    for label in sequence:
        result[BRANCHES[pointer]] = label
        pointer += sign
        if pointer == 12:
            pointer = 0
        if pointer == -1:
            pointer = 11
    return result


def audit_cycles(fixtures: Path = FIXTURES) -> dict[str, Any]:
    folder = fixtures / "naj_ming_cycles_v1"
    for e in json.loads((folder / "checksums.json").read_text())["files"]:
        if hashlib.sha256((folder / e["path"]).read_bytes()).hexdigest() != e["sha256"]:
            raise ValueError("Cycle source checksum mismatch: " + e["path"])
    source = json.loads((folder / "collation.json").read_text())
    production = json.loads(
        (ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-cycles.json").read_text()
    )
    expected_data = {
        k: v
        for k, v in source.items()
        if k not in ("title", "images", "image_conditions_url", "catalog_url")
    }
    mismatches: list[dict[str, Any]] = []
    if production != expected_data:
        mismatches.append(dict(case="production_source_data"))
    stats = {
        p: {
            system: dict(matches=0, differences=0, unresolved=0)
            for system in ("changsheng", "boshi")
        }
        for p in ("iztro_2_5_8", "quanshu_v2_excerpt")
    }
    cases = labels = invariant = unresolved = 0
    for profile in stats:
        for element, cs_start in source["changsheng"]["starts_by_element"].items():
            for stem, bs_start in source["lucun"]["starts_by_stem"].items():
                for gender in ("男", "女", "未知"):
                    known = gender != "未知"
                    yang_forward = (stem in "甲丙戊庚壬") == (gender == "男")
                    palace_rows = [dict(ganzhi="甲" + b) for b in BRANCHES]
                    rules = attach_natal_cycles(
                        palace_rows,
                        element=element,
                        year_stem=stem,
                        gender=gender,
                        rule_profile=profile,
                    )
                    evidence = cycle_source_evidence(
                        palace_rows,
                        rules,
                        element=element,
                        year_stem=stem,
                        gender=gender,
                        rule_profile=profile,
                    )
                    for prefix, sequence, start in (
                        (
                            "changsheng",
                            source["changsheng"]["sequence_modern"],
                            cs_start,
                        ),
                        ("boshi", source["boshi"]["sequence_modern"], bs_start),
                    ):
                        source_sign = (
                            (1 if gender == "男" else -1)
                            if prefix == "changsheng"
                            else (1 if yang_forward else -1)
                        )
                        maps = [
                            walk(sequence, start, s)
                            for s in ([source_sign] if known else [1, -1])
                        ]
                        actual_sign = (
                            source_sign
                            if prefix == "boshi" or profile == "quanshu_v2_excerpt"
                            else (1 if yang_forward else -1)
                        )
                        actual_map = walk(sequence, start, actual_sign)
                        for palace in palace_rows:
                            b = palace["ganzhi"][1]
                            candidates = list(dict.fromkeys(m[b] for m in maps))
                            expected = (
                                actual_map[b]
                                if known
                                else (candidates[0] if len(candidates) == 1 else None)
                            )
                            actual = palace[prefix + "12"]
                            row = evidence["positions"][prefix][b]
                            match = (
                                actual == candidates[0]
                                if len(candidates) == 1
                                else None
                            )
                            checks = (
                                actual == expected,
                                row["candidates"] == candidates,
                                row["actual"] == actual,
                                row["match"] == match,
                            )
                            if not all(checks):
                                mismatches.append(
                                    dict(
                                        case=f"{profile}/{element}/{stem}/{gender}/{prefix}/{b}",
                                        expected=expected,
                                        actual=actual,
                                    )
                                )
                            stats[profile][prefix][
                                (
                                    "unresolved"
                                    if match is None
                                    else ("matches" if match else "differences")
                                )
                            ] += 1
                            labels += 1
                            if not known:
                                invariant += int(expected is not None)
                                unresolved += int(expected is None)
                        if (
                            evidence[prefix]["source_start"] != start
                            or evidence[prefix]["actual_start_branches"] != [start]
                            or evidence[prefix]["reported_start"] != start
                            or evidence[prefix]["start_match"] is not True
                        ):
                            mismatches.append(
                                dict(
                                    case=f"start/{profile}/{element}/{stem}/{gender}/{prefix}"
                                )
                            )
                        expected_direction = (
                            ("顺行" if source_sign == 1 else "逆行") if known else None
                        )
                        if evidence[prefix]["source_direction"] != expected_direction:
                            mismatches.append(dict(case="source_direction"))
                        actual_direction = (
                            ("顺行" if actual_sign == 1 else "逆行") if known else None
                        )
                        if (
                            rules[prefix + "_direction"] != actual_direction
                            or evidence[prefix]["actual_direction"] != actual_direction
                        ):
                            mismatches.append(dict(case="actual_direction"))
                        if known and evidence[prefix]["direction_match"] != (
                            actual_direction == expected_direction
                        ):
                            mismatches.append(dict(case="direction_comparison"))
                        if not known and (
                            rules[prefix + "_direction"] is not None
                            or evidence[prefix]["direction_match"] is not None
                        ):
                            mismatches.append(
                                dict(case="unknown_cannot_certify_direction")
                            )
                    if not known:
                        invariants = {
                            key: {
                                p["ganzhi"][1]: p[key]
                                for p in palace_rows
                                if p[key] is not None
                            }
                            for key in ("changsheng12", "boshi12")
                        }
                        if (
                            rules["status"] != "partial_missing_gender"
                            or rules.get("gender_invariant_positions") != invariants
                        ):
                            mismatches.append(dict(case="unknown_invariant_receipt"))
                    cases += 1
    return {
        "method_id": source["id"],
        "source_start_rows": len(source["changsheng"]["starts_by_element"]),
        "source_sequence_labels": {"changsheng": 12, "boshi": 12},
        "lucun_stem_rows": 10,
        "conditional_input_cases": cases,
        "cycle_position_checks": labels,
        "unknown_gender_invariant_labels_checked": invariant,
        "unknown_gender_unresolved_slots": unresolved,
        "source_position_comparison": stats,
        "mismatches": mismatches,
        "manual_source_reader_count": source["manual_reader_count"],
        "calendar_and_bureau_derivation_certified": False,
        "whole_book_acceptance_passed": False,
        "scope": "Given bureau element and natal stem, compare literal cycles and retain only direction invariants without gender",
    }
