"""Compare natal placements and transformations with selected Ming witnesses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.ziwei import build_ziwei_chart, build_ziwei_rules
from scripts.ziwei.ziwei_conditional_inputs import FIXTURES, ROOT, synthetic_seed


def audit_ming_scan(fixtures: Path = FIXTURES) -> dict[str, Any]:
    root = fixtures / "naj_ming"
    checksums = json.loads((root / "checksums.json").read_text(encoding="utf-8"))
    for entry in checksums["files"]:
        if (
            hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest()
            != entry["sha256"]
        ):
            raise ValueError("Ming scan source checksum mismatch")
        else:
            pass
    source = json.loads((root / "collation.json").read_text(encoding="utf-8"))
    failures = []
    checks = 0
    for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
        for stem, expected in source["nobles"]["expected_by_stem"].items():
            index = "甲乙丙丁戊己庚辛壬癸".index(stem)
            chart = build_ziwei_chart(
                synthetic_seed(1984 + index), "男", rule_profile=profile
            )
            actual = [
                next(
                    p["ganzhi"][1]
                    for p in chart["palaces"]
                    if any(s["name"] == name for s in p["stars_detail"])
                )
                for name in ("天魁", "天钺")
            ]
            if actual != expected:
                failures.append(
                    dict(
                        case=f"nobles/{profile}/{stem}",
                        expected=expected,
                        actual=actual,
                    )
                )
            else:
                pass
            checks += 2
    xun_order = ("甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅")
    for index in range(60):
        chart = build_ziwei_chart(
            synthetic_seed(1984 + index), "男", rule_profile="quanshu_v2_excerpt"
        )
        expected = source["void_pairs"]["expected_by_xun"][xun_order[index // 10]]
        actual = chart["void_systems"]["xun"]["displayed_star_branches"]
        if actual != expected:
            failures.append(
                dict(case=f"scan_void/{index}", expected=expected, actual=actual)
            )
        else:
            pass
    production = json.loads(
        (ROOT / "src/fatebridge/data/classical/ziwei-quanshu-v2-stars.json").read_text(
            encoding="utf-8"
        )
    )
    actual_elements = {row["star"]: row["elements"] for row in production["entries"]}
    if actual_elements != source["elements"]["expected"]:
        failures.append(
            dict(
                case="scan_elements",
                expected=source["elements"]["expected"],
                actual=actual_elements,
            )
        )
    else:
        pass
    return {
        "status": "partial" if not failures else "failed",
        "catalog_uri": source["catalog_uri"],
        "reference_code": source["reference_code"],
        "scan_frames_frozen": len(source["images"]),
        "manual_scan_reader_count": 1,
        "noble_placement_checks": checks,
        "independent_noble_source_cells": 20,
        "void_pairs_checked": 60,
        "independent_void_source_pairs": 6,
        "element_records_checked": 16,
        "pinned_transcription_differences": source["nobles"][
            "pinned_transcription_differences"
        ],
        "body_master_unresolved": source["body_master"],
        "printed_volume": source["printed_volume_for_placement_sections"],
        "transcription_volume": source["transcription_volume_for_same_sections"],
        "mismatches": failures,
        "whole_book_acceptance_passed": False,
        "unresolved": source["unresolved"],
    }


def audit_ming_anxing(fixtures: Path = FIXTURES) -> dict[str, Any]:
    """Literal print readings; edition differences never count as conformity."""
    root = fixtures / "naj_ming_anxing_v1"
    manifest = json.loads((root / "checksums.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        if (
            hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest()
            != entry["sha256"]
        ):
            raise ValueError("Ming Anxing source checksum mismatch")
        else:
            pass
    source = json.loads((root / "collation.json").read_text(encoding="utf-8"))
    # Independently expand the frozen printed abbreviations, not engine output.
    names = dict(
        zip(
            "廉破武陽日機梁紫月同昌巨貪弼曲相府陰",
            [
                "廉贞",
                "破军",
                "武曲",
                "太阳",
                "太阳",
                "天机",
                "天梁",
                "紫微",
                "太阴",
                "天同",
                "文昌",
                "巨门",
                "贪狼",
                "右弼",
                "文曲",
                "天相",
                "天府",
                "太阴",
            ],
        )
    )
    expected = {
        row["stem"]: dict(
            zip(source["sihua"]["order"], [names[a] for a in row["star_abbreviations"]])
        )
        for row in source["sihua"]["rows"]
    }
    production = json.loads(
        (ROOT / "src/fatebridge/data/classical/ziwei-naj-ming-sihua.json").read_text(
            encoding="utf-8"
        )
    )
    actual = {row["stem"]: row["assignments"] for row in production["rows"]}
    mismatches = []
    if actual != expected:
        mismatches.append(
            dict(case="literal_sihua_table", expected=expected, actual=actual)
        )
    else:
        pass
    readings = [
        (row["stem"], row["frame"], row["reading"]) for row in production["rows"]
    ]
    source_readings = [
        (row["stem"], row["frame"], row["reading"]) for row in source["sihua"]["rows"]
    ]
    if readings != source_readings:
        mismatches.append(
            dict(
                case="literal_sihua_readings", expected=source_readings, actual=readings
            )
        )
    else:
        pass
    edition_differences = {}
    joined_positions = 0
    for profile in ("iztro_2_5_8", "quanshu_v2_excerpt"):
        selected = build_ziwei_rules(rule_profile=profile)["rule_catalogue"][
            "sihua_by_year_stem"
        ]
        differences = []
        for i, stem in enumerate("甲乙丙丁戊己庚辛壬癸"):
            chart = build_ziwei_chart(
                synthetic_seed(1984 + i), "男", rule_profile=profile
            )
            comparison = chart["sihua_source_comparison"]
            stem_differences = []
            for change, source_star in expected[stem].items():
                if selected[stem][change] != source_star:
                    stem_differences.append(
                        dict(
                            transformation=change,
                            selected_star=selected[stem][change],
                            compared_star=source_star,
                        )
                    )
                    differences.append(
                        dict(
                            year_stem=stem,
                            transformation=change,
                            selected_star=selected[stem][change],
                            compared_star=source_star,
                        )
                    )
                else:
                    pass
            reported_stem_differences = [
                {
                    key: difference[key]
                    for key in ("transformation", "selected_star", "compared_star")
                }
                for difference in comparison["differences"]
            ]
            if reported_stem_differences != stem_differences:
                mismatches.append(
                    dict(
                        case=f"natal_edition_report/{profile}/{stem}",
                        actual=reported_stem_differences,
                        expected=stem_differences,
                    )
                )
            else:
                pass
            for difference in comparison["differences"]:
                for kind in ("selected", "compared"):
                    pos = difference[f"{kind}_position"]
                    parts = pos["calculation_path"].split(".")
                    palace = chart["palaces"][int(parts[2])]
                    star = palace["stars_detail"][int(parts[4])]
                    got = [
                        star["name"],
                        star["mutagen"],
                        palace["name"],
                        palace["ganzhi"][1],
                    ]
                    wanted = [
                        difference[f"{kind}_star"],
                        pos["natal_mutagen"],
                        pos["natal_palace_name"],
                        pos["natal_branch"],
                    ]
                    if got != wanted:
                        mismatches.append(
                            dict(
                                case=f"source_position/{profile}/{stem}/{kind}",
                                actual=got,
                                expected=wanted,
                            )
                        )
                    else:
                        pass
                    joined_positions += 1
            if comparison["compared_assignments_applied"]:
                mismatches.append(dict(case=f"variant_applied/{profile}/{stem}"))
            else:
                pass
        reported = build_ziwei_rules(rule_profile=profile)["rule_catalogue"][
            "sihua_source_comparison"
        ]["differences"]
        if reported != differences:
            mismatches.append(
                dict(
                    case=f"edition_report/{profile}",
                    actual=reported,
                    expected=differences,
                )
            )
        else:
            pass
        edition_differences[profile] = differences

    # Find synthetic inputs with each bureau; only star placement conditioned on
    # the resolved bureau is audited here, not the bureau calculation itself.
    seeds: dict[int, MetaphysicsSeed] = {}
    for year in range(1984, 1989):
        for month in range(1, 13):
            seed = synthetic_seed(year, month=month)
            chart = build_ziwei_chart(seed, "男")
            seeds.setdefault(chart["wuxing_ju"]["number"], seed)

    def star_branch(chart: dict[str, Any], name: str) -> str:
        return str(
            next(
                p["ganzhi"][1]
                for p in chart["palaces"]
                if any(s["name"] == name for s in p["stars_detail"])
            )
        )

    for anchor in source["ziwei_anchor_cells"]:
        base = seeds[anchor["bureau"]]
        lunar = base.calendar_context["lunar_calendar"]
        seed = synthetic_seed(lunar["year"], month=lunar["month"], day=anchor["day"])
        anchor_branch = star_branch(build_ziwei_chart(seed, "男"), "紫微")
        if anchor_branch != anchor["branch"]:
            mismatches.append(
                dict(
                    case=f"ziwei_anchor/{anchor['bureau']}/{anchor['day']}",
                    actual=anchor_branch,
                    expected=anchor["branch"],
                )
            )
        else:
            pass
    reflections = {}
    for day in range(1, 31):
        base = seeds[2].calendar_context["lunar_calendar"]
        chart = build_ziwei_chart(
            synthetic_seed(base["year"], month=base["month"], day=day), "男"
        )
        reflections[star_branch(chart, "紫微")] = star_branch(chart, "天府")
    expected_reflections = source["tianfu_reflection"]["expected_by_ziwei_branch"]
    if reflections != expected_reflections:
        mismatches.append(
            dict(
                case="tianfu_diagram", actual=reflections, expected=expected_reflections
            )
        )
    else:
        pass
    return {
        "status": "partial" if not mismatches else "failed",
        "source": source["item_url"],
        "scan_frames_frozen": len({image["frame"] for image in source["images"]}),
        "image_files_frozen": len(source["images"]),
        "manual_scan_reader_count": source["reader_count"],
        "independent_sihua_source_cells": sum(len(r) for r in expected.values()),
        "sihua_position_joins_checked": joined_positions,
        "edition_differences": edition_differences,
        "current_profiles_conform_to_ming_sihua": not any(edition_differences.values()),
        "comparison_context": "base_profiles_with_default_sihua_source_rule_profile",
        "ziwei_anchor_cells_checked": len(source["ziwei_anchor_cells"]),
        "tianfu_reflection_cells_checked": len(expected_reflections),
        "mismatches": mismatches,
        "whole_book_acceptance_passed": False,
        "limits": source["limits"],
    }
