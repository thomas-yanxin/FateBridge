"""Audit frozen classical excerpts and derived Ziwei rule vectors."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fatebridge.core.metaphysics.ziwei import (
    build_ziwei_chart,
    build_ziwei_horoscope,
    build_ziwei_rules,
)
from fatebridge.core.ziwei.ziwei_tables import lookup_star_brightness
from scripts.ziwei.ziwei_conditional_inputs import (
    FIXTURES,
    ROOT,
    synthetic_birth_clock,
    synthetic_seed,
)


def audit_classical(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest = json.loads(
        (fixtures / "classical_manifest.json").read_text(encoding="utf-8")
    )
    for source in manifest["files"]:
        if (
            hashlib.sha256((fixtures / source["path"]).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError(f"Classical source checksum mismatch: {source['path']}")
        else:
            pass
    data = json.loads((fixtures / "classical_excerpt.json").read_text(encoding="utf-8"))
    checks = []

    def check(label: str, actual: Any, expected: Any) -> None:
        checks.append(
            {
                "case": label,
                "passed": actual == expected,
                "expected": expected,
                "actual": actual,
            }
        )

    profile = "quanshu_v2_excerpt"
    for stem, expected in data["sihua_by_stem"].items():
        rules = build_ziwei_rules(stem, rule_profile=profile)["focused_rules"]["sihua"]
        check(f"sihua/{stem}", [rules[k] for k in data["sihua_order"]], expected)
    for hour, expected in data["first_lunar_month_by_hour"].items():
        chart = build_ziwei_chart(
            synthetic_seed(1984, hour=hour), "男", rule_profile=profile
        )
        check(
            f"ming_shen/{hour}",
            [chart["ming_gong"]["branch"], chart["shen_gong"]["branch"]],
            expected,
        )
    for i, (stem, expected) in enumerate(data["yin_palace_by_stem"].items()):
        chart = build_ziwei_chart(synthetic_seed(1984 + i), "男", rule_profile=profile)
        check(f"yin_stem/{stem}", chart["ming_gong"]["ganzhi"], expected)
    for case in data["ziwei_positions"]:
        chart = build_ziwei_chart(
            synthetic_seed(case["lunar_year"], day=case["day"]),
            "男",
            rule_profile=profile,
        )
        palace = next(
            p
            for p in chart["palaces"]
            if any(s["name"] == "紫微" for s in p["stars_detail"])
        )
        check(
            f"ziwei/{case['ju']}/{case['day']}",
            [chart["wuxing_ju"]["number"], palace["ganzhi"][1]],
            [case["ju"], case["branch"]],
        )
    for day in (1, 15, 16, 30):
        chart = build_ziwei_chart(
            synthetic_seed(1984, day=day, leap=True), "男", rule_profile=profile
        )
        check(
            f"leap_month/{day}",
            [chart["ming_gong"]["branch"], chart["shen_gong"]["branch"]],
            ["卯", "卯"],
        )
    return {
        "status": "partial" if all(c["passed"] for c in checks) else "failed",
        "source": data["source"],
        "edition_status": data["edition_status"],
        "checked_vectors": len(checks),
        "failed_vectors": [c for c in checks if not c["passed"]],
        "unresolved_source_items": data["unresolved_source_items"],
        "whole_book_acceptance_passed": False,
    }


def audit_additional_classical(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest = json.loads(
        (fixtures / "additional_manifest.json").read_text(encoding="utf-8")
    )
    for source in manifest["files"]:
        if (
            hashlib.sha256((fixtures / source["path"]).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError("Additional classical source checksum mismatch")
        else:
            pass
    data = json.loads(
        (fixtures / "quanshu_additional_excerpts.json").read_text(encoding="utf-8")
    )
    names = dict(
        zip(
            "紫机日武同廉府月贪巨相梁杀破昌曲火铃羊陀禄",
            (
                "紫微",
                "天机",
                "太阳",
                "武曲",
                "天同",
                "廉贞",
                "天府",
                "太阴",
                "贪狼",
                "巨门",
                "天相",
                "天梁",
                "七杀",
                "破军",
                "文昌",
                "文曲",
                "火星",
                "铃星",
                "擎羊",
                "陀罗",
                "禄存",
            ),
        )
    )
    differences, checked = [], 0
    for branch, columns in data["brightness_rows"].items():
        for expected, glyphs in zip(data["brightness_heading"], columns):
            for glyph in glyphs:
                star = names[glyph]
                actual = lookup_star_brightness(
                    star, branch, rule_profile="quanshu_v2_excerpt"
                )
                checked += 1
                if actual != expected:
                    differences.append(
                        {
                            "star": star,
                            "branch": branch,
                            "expected": expected,
                            "actual": actual,
                        }
                    )
                else:
                    pass
    return {
        "status": "partial" if not differences else "failed",
        "brightness_cells_checked": checked,
        "differences": differences,
        "unresolved": data["unresolved"],
        "whole_book_acceptance_passed": False,
    }


def audit_depth_classical(fixtures: Path = FIXTURES) -> dict[str, Any]:
    manifest = json.loads(
        (fixtures / "depth_manifest.json").read_text(encoding="utf-8")
    )
    for entry in manifest["files"]:
        if (
            hashlib.sha256((fixtures / entry["path"]).read_bytes()).hexdigest()
            != entry["sha256"]
        ):
            raise ValueError("Depth classical source checksum mismatch")
        else:
            pass
    source = json.loads(
        (fixtures / "quanshu_v2_revision_1963110.json").read_text(encoding="utf-8")
    )
    page = next(iter(source["query"]["pages"].values()))
    revision = page["revisions"][0]
    if page["title"] != "紫微斗數全書/卷二" or revision["revid"] != 1963110:
        raise ValueError("Unexpected classical title/revision")
    else:
        pass
    original = revision["slots"]["main"]["*"]
    data = json.loads(
        (fixtures / "quanshu_depth_rules.json").read_text(encoding="utf-8")
    )
    failures = []

    def check(label: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            failures.append({"case": label, "expected": expected, "actual": actual})
        else:
            pass

    normalized = re.sub(r"\s+", "", original)
    for label, quote in data["excerpts"].items():
        check(f"source_quote/{label}", re.sub(r"\s+", "", quote) in normalized, True)
    stars = json.loads(
        (ROOT / "src/fatebridge/data/classical/ziwei-quanshu-v2-stars.json").read_text(
            encoding="utf-8"
        )
    )
    check(
        "symbolic_star_set",
        sorted(s["star"] for s in stars["entries"]),
        sorted(data["star_elements"]),
    )
    for item in stars["entries"]:
        check(f"source_quote/{item['star']}", item["quote"] in original, True)
        check(
            f"elements/{item['star']}",
            item["elements"],
            data["star_elements"][item["star"]],
        )
        # Parse only the literal opening element glyphs, independently from
        # the production property's data extraction and chart join.
        element_match = re.match(r"^.+?属([木火土金水]+)", item["quote"])
        check(
            f"literal_elements/{item['star']}",
            list(element_match[1]) if element_match else None,
            item["elements"],
        )

    profile = "quanshu_v2_excerpt"
    xun_order = ("甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅")
    joins = 0
    for index in range(60):
        chart = build_ziwei_chart(
            synthetic_seed(1984 + index), "男", rule_profile=profile
        )
        expected = data["void_pairs_by_xun"][xun_order[index // 10]]
        displayed = [
            p["ganzhi"][1]
            for p in chart["palaces"]
            if any(s["name"] == "旬空" for s in p["stars_detail"])
        ]
        check(f"void_pair/{1984 + index}", sorted(displayed), sorted(expected))
        check(
            f"void_metadata/{1984 + index}",
            chart["void_systems"]["xun"]["displayed_star_branches"],
            expected,
        )
        for item in chart["symbolic_properties"]["records"]:
            position = item["calculation_path"].split(".")
            palace = chart["palaces"][int(position[2])]
            actual = palace["stars_detail"][int(position[4])]
            check(
                f"symbolic_join/{index}/{item['star']}",
                [
                    item["star"],
                    item["natal_brightness"],
                    item["natal_mutagen"],
                    item["natal_palace_name"],
                    item["natal_branch"],
                ],
                [
                    actual["name"],
                    actual["brightness"],
                    actual["mutagen"],
                    palace["name"],
                    palace["ganzhi"][1],
                ],
            )
            joins += 1
    natal = build_ziwei_chart(synthetic_seed(1984), "男", rule_profile=profile)
    for offset, branch in enumerate("子丑寅卯辰巳午未申酉戌亥"):
        target = synthetic_seed(1996 + offset, month=6, day=15)
        horoscope = build_ziwei_horoscope(
            birth_seed=synthetic_birth_clock(int((natal)["lunar_date"]["year"])),
            chart=natal,
            gender="男",
            target_seed=target,
        )
        annual = next(s for s in horoscope["scopes"] if s["scope"] == "流年")
        actual = {
            s["star"]: s["branch"]
            for s in annual["flowing_stars"]
            if s["rule_id"] != "annual_lucun_yang_tuo"
        }
        check(f"annual/{branch}", actual, data["annual_by_year_branch"][branch])
        group = next(group for group in data["annual_sha_by_triad"] if branch in group)
        check(
            f"annual_sha/{branch}",
            annual["annual_three_sha"]["branches"],
            data["annual_sha_by_triad"][group],
        )
        check(
            f"annual_sha_unpaired/{branch}",
            annual["annual_three_sha"]["individual_name_positions"],
            None,
        )
    return {
        "status": "partial" if not failures else "failed",
        "source_revision": 1963110,
        "source_title_verified": True,
        "void_pairs_checked": 60,
        "annual_placements_checked": 72,
        "annual_sha_sets_checked": 12,
        "symbolic_source_records_checked": len(stars["entries"]),
        "symbolic_calculation_joins_checked": joins,
        "mismatches": failures,
        "whole_book_acceptance_passed": False,
        "initial_source_limits_as_frozen": manifest["limits"],
        "unresolved": [
            "Exact printed base of the pinned online transcription is not identified; selected Ming crosschecks are reported separately",
            "Full volume is frozen for review, not fully implemented or certified",
            "Ambiguous named placement and contradictory text remain unresolved",
        ],
    }
