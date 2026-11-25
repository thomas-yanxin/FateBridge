"""Edition-specific readings, kept separate from the active calculation table."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any, Dict, List, cast


@lru_cache(maxsize=1)
def _ming_sihua_source() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-naj-ming-sihua.json")
            .read_text(encoding="utf-8")
        ),
    )


@lru_cache(maxsize=1)
def _ming_day_source() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-naj-ming-days.json")
            .read_text(encoding="utf-8")
        ),
    )


@lru_cache(maxsize=1)
def _ming_day_review() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-naj-ming-days-review-r22.json")
            .read_text(encoding="utf-8")
        ),
    )


@lru_cache(maxsize=1)
def _ming_targeted_day_review() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-naj-ming-targeted-review-r24.json")
            .read_text(encoding="utf-8")
        ),
    )


@lru_cache(maxsize=1)
def _ming_prerequisite_source() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-naj-ming-prerequisites.json")
            .read_text(encoding="utf-8")
        ),
    )


def ziwei_prerequisite_source_evidence(
    *,
    lunar_month: int,
    is_leap: bool,
    effective_month: int,
    hour_branch: str,
    year_stem: str,
    shen_branch: str,
    palaces: List[Dict[str, Any]],
    nayin: str,
    bureau: int,
) -> Dict[str, Any]:
    """Compare prerequisites with Ming prose without applying the compared rules.

    A matching day-table position cannot certify its upstream bureau. This
    comparison follows the source's own Ming/Shen -> palace stem -> element
    chain. Palace order/stems are also checked independently at actual branches.
    Exact Nayin names, civil dates and other monthly star rules are out of scope.
    """
    source = _ming_prerequisite_source()
    branches = list("寅卯辰巳午未申酉戌亥子丑")
    stems = list("甲乙丙丁戊己庚辛壬癸")
    if (
        not 1 <= lunar_month <= 12
        or hour_branch not in branches
        or year_stem not in stems
    ):
        raise ValueError("命身宫原文比较要求有效的农历月、时支与年干")
    wanted_month = lunar_month + int(is_leap)
    seed = next(
        r
        for r in source["ming_shen"]["first_month_by_hour"]
        if r["hour"] == hour_branch
    )

    def rotate(branch: str) -> str:
        ring = branches[branches.index(branch) :] + branches[: branches.index(branch)]
        return ring[(wanted_month - 1) % 12]

    wanted_ming, wanted_shen = rotate(seed["ming_branch"]), rotate(seed["shen_branch"])
    yin_stem = next(
        row["yin_stem"]
        for row in source["wuhu_dun"]["rows"]
        if year_stem in row["year_stems"]
    )
    stem_cycle = stems[stems.index(yin_stem) :] + stems[: stems.index(yin_stem)]
    ganzhi_by_branch = {
        branch: stem_cycle[i % 10] + branch for i, branch in enumerate(branches)
    }
    wanted_ganzhi = ganzhi_by_branch[wanted_ming]
    row = next(r for r in source["nayin"]["rows"] if wanted_ganzhi in r["ganzhi_pair"])
    wanted_element = row["element"]
    wanted = {
        "effective_month": wanted_month,
        "ming_branch": wanted_ming,
        "shen_branch": wanted_shen,
        "ming_ganzhi": wanted_ganzhi,
        "nayin_element": wanted_element,
        "ju_number": source["bureau_numbers"]["values"][wanted_element],
    }
    ming = next(p for p in palaces if p["name"] == "命宫")
    actual = {
        "effective_month": effective_month,
        "ming_branch": ming["ganzhi"][1],
        "shen_branch": shen_branch,
        "ming_ganzhi": ming["ganzhi"],
        "nayin_element": nayin[-1],
        "ju_number": bureau,
    }
    checks = {name: actual[name] == value for name, value in wanted.items()}
    actual_ming_index = branches.index(actual["ming_branch"])
    actual_by_branch = {p["ganzhi"][1]: p for p in palaces}
    checks["palace_names_given_actual_ming"] = len(actual_by_branch) == 12 and all(
        actual_by_branch[branches[(actual_ming_index - i) % 12]]["name"].removesuffix(
            "宫"
        )
        == name.removesuffix("宫")
        for i, name in enumerate(source["palace_order"]["modern_names"])
    )
    checks["palace_stems_by_absolute_branch"] = len(actual_by_branch) == 12 and all(
        actual_by_branch[b]["ganzhi"] == value for b, value in ganzhi_by_branch.items()
    )
    return {
        "method_id": source["id"],
        "version": source["version"],
        "source": source["source_url"],
        "printed_volume": source["printed_volume"],
        "source_frames": [73, 74],
        "scope": "prerequisites_from_supplied_lunar_month_hour_year_stem_only",
        "expected": wanted,
        "actual": actual,
        "checks": checks,
        "matches_source_chain": all(checks.values()),
        "source_nayin_name_reading": row["name_reading"],
        "source_nayin_name_reading_complete": row["name_reading_complete"],
        "nayin_name_comparison": "not_performed_element_and_bureau_only",
        "compared_rules_applied": False,
        "manual_reader_count": source["manual_reader_count"],
        "whole_book_conformance_claimed": False,
    }


def ziwei_day_source_evidence(
    *, bureau: int, lunar_day: int, actual_branch: str
) -> Dict[str, Any]:
    """Compare the computed 紫微 position with a separately transcribed source.

    Water-two day 21 is derived from the prose, not credited as a grid reading.
    Wood-three days 11 and 12 have no unique printed expectation; matching one
    candidate never resolves the conflict. Calendar and bureau are not certified.
    """
    if bureau not in range(2, 7) or lunar_day not in range(1, 31):
        raise ValueError("安紫微原文比较要求五行局 2..6、农历日 1..30")
    source = _ming_day_source()
    row = next(
        row
        for row in source["records"]
        if row["bureau"] == bureau and row["day"] == lunar_day
    )
    result = {
        "method_id": source["id"],
        "source": source["source_url"],
        "printed_volume": source["printed_volume"],
        "source_frame": row["frame"],
        "source_kind": row["source_kind"],
        "printed_day_labels": list(row["printed_labels"]),
        "source_candidates": [dict(candidate) for candidate in row["candidates"]],
        "expected_ziwei_branch": row["branch"],
        "actual_ziwei_branch": actual_branch,
        "matches_source_record": (
            row["branch"] == actual_branch if row["branch"] is not None else None
        ),
        "scope": "ziwei_position_given_bureau_and_lunar_day_only",
        "manual_reader_count": source["reader_count"],
    }
    if row["source_kind"] == "prose_derived_with_unresolved_grid_label":
        result["source_quote"] = row["source_quote"]
        result["derivation"] = row["derivation"]
        result["printed_label_unresolved"] = True
    elif row["branch"] is None:
        result["source_resolution"] = "No unique expectation; do not score as a match"
    review = _ming_day_review()
    reading = next(
        r for r in review["records"] if r["bureau"] == bureau and r["day"] == lunar_day
    )
    direct = list(reading["branches_from_direct_labels"])
    unresolved = list(reading.get("candidate_branches_from_unresolved_labels", []))
    result["independent_review"] = {
        "method_id": review["id"],
        "source_report_sha256": review["source_report_sha256"],
        "erratum_sha256": review["erratum_sha256"],
        "status": reading["status"],
        "direct_label_branches": direct,
        "unresolved_label_candidates": unresolved,
        "matches_unique_direct_branch": (
            actual_branch == direct[0] if len(direct) == 1 else None
        ),
        "agrees_with_selected_branch": (
            row["branch"] == direct[0]
            if len(direct) == 1 and row["branch"] is not None
            else None
        ),
        "unambiguous_after_rereading": len(direct) == 1 and not unresolved,
        "new_edition": False,
        "external_human_experts": 0,
        "whole_day_table_certified": False,
    }
    targeted = _ming_targeted_day_review()
    later = next(
        (
            r
            for r in targeted["records"]
            if r["bureau"] == bureau and r["day"] == lunar_day
        ),
        None,
    )
    if later is not None:
        branches = list(later["direct_label_branches"])
        result["targeted_rereading"] = {
            **{k: v for k, v in later.items() if k not in {"bureau", "day"}},
            "method_id": targeted["id"],
            "source_report_sha256": targeted["source_report_sha256"],
            "reviewed_input_count": targeted["reviewed_input_count"],
            "matches_unique_direct_branch": (
                actual_branch == branches[0] if len(branches) == 1 else None
            ),
            "unique_source_confirmation_supported": len(branches) == 1,
            "new_witness_count": 0,
            "external_human_experts": 0,
            "whole_day_table_certified": False,
        }
    return result


def sihua_source_comparison(
    selected_rules: Dict[str, Dict[str, str]],
    *,
    compared_assignments_applied: bool = False,
) -> Dict[str, Any]:
    """Compare all 40 cells and disclose an explicit table selection."""
    source = _ming_sihua_source()
    differences = []
    for row in source["rows"]:
        stem = row["stem"]
        for transformation, compared_star in row["assignments"].items():
            selected_star = selected_rules[stem][transformation]
            if selected_star != compared_star:
                differences.append(
                    {
                        "year_stem": stem,
                        "transformation": transformation,
                        "selected_star": selected_star,
                        "compared_star": compared_star,
                    }
                )
    if compared_assignments_applied and differences:
        raise ValueError("已选择明刊四化，但实际四化表与来源不符")
    return {
        "method_id": source["id"],
        "version": source["version"],
        "compared_source": source["source_url"],
        "source_title": source["title"],
        "printed_volume": source["printed_volume"],
        "scope": "natal_sihua_table_only",
        "source_cell_count": 40,
        "manual_reader_count": source["manual_reader_count"],
        "compared_assignments_applied": compared_assignments_applied,
        "whole_book_conformance_claimed": False,
        "differences": differences,
    }


def natal_sihua_source_comparison(
    palaces: List[Dict[str, Any]],
    *,
    year_stem: str,
    selected_sihua: Dict[str, str],
    compared_assignments_applied: bool = False,
) -> Dict[str, Any]:
    """Show where a differing natal table would assign a marker, not a new chart.

    Position paths point to existing stars. In particular the compared star's
    actual natal_mutagen remains the selected profile's value, often None.
    """
    source = _ming_sihua_source()
    row = next(row for row in source["rows"] if row["stem"] == year_stem)

    def position(name: str) -> Dict[str, Any]:
        matches = [
            (i, j, palace, star)
            for i, palace in enumerate(palaces)
            for j, star in enumerate(palace["stars_detail"])
            if star["name"] == name
        ]
        if len(matches) != 1:
            raise ValueError(f"四化版本比较要求唯一的本命星位：{name}")
        i, j, palace, star = matches[0]
        return {
            "natal_palace_name": palace["name"],
            "natal_branch": palace["ganzhi"][1],
            "natal_mutagen": star["mutagen"],
            "calculation_path": f"ziwei_birth.palaces.{i}.stars_detail.{j}",
        }

    differences = []
    for transformation, compared_star in row["assignments"].items():
        selected_star = selected_sihua[transformation]
        if selected_star != compared_star:
            differences.append(
                {
                    "transformation": transformation,
                    "selected_star": selected_star,
                    "compared_star": compared_star,
                    "selected_position": position(selected_star),
                    "compared_position": position(compared_star),
                }
            )
    if compared_assignments_applied and differences:
        raise ValueError("已选择明刊四化，但实际生年四化与来源不符")
    return {
        "method_id": source["id"],
        "compared_source": source["source_url"],
        "source_section": source["section"],
        "printed_volume": source["printed_volume"],
        "source_frame": row["frame"],
        "source_reading": row["reading"],
        "year_stem": year_stem,
        "scope": "natal_sihua_table_only_no_other_rules_applied",
        "source_agrees_on_this_stem": not differences,
        "compared_assignments_applied": compared_assignments_applied,
        "differences": differences,
    }
