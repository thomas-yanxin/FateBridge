"""Source-backed month/year and hour/day stem links, not calendar boundaries."""

import json
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.utils.errors import NumerologySourceError

RULESET_ID = "heluo_volume7_pillar_links_v1"
SOURCE_PATH = (
    Path(__file__).resolve().parents[1] / "data/numerology/pillar-links-v1.json"
)
GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
CYCLE = {GAN[i % 10] + ZHI[i % 12] for i in range(60)}
LINK_HEADS = {
    "month": ("丙寅", "戊寅", "庚寅", "壬寅", "甲寅") * 2,
    "hour": ("甲子", "丙子", "戊子", "庚子", "壬子") * 2,
}
LINK_GROUPS = ("甲己", "乙庚", "丙辛", "丁壬", "戊癸") * 2


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    try:
        raw = SOURCE_PATH.read_bytes()
        data: dict[str, Any] = json.loads(raw)
        expected_groups = ["甲己", "乙庚", "丙辛", "丁壬", "戊癸"]
        if (
            data["ruleset_id"] != RULESET_ID
            or data["month_branch_order"] != "寅卯辰巳午未申酉戌亥子丑"
            or data["hour_branch_order"] != ZHI
            or [r["basis_stems"] for r in data["month_heads"]] != expected_groups
            or [r["basis_stems"] for r in data["hour_heads"]] != expected_groups
            or [r["head"] for r in data["month_heads"]]
            != ["丙寅", "戊寅", "庚寅", "壬寅", "甲寅"]
            or [r["head"] for r in data["hour_heads"]]
            != ["甲子", "丙子", "戊子", "庚子", "壬子"]
        ):
            raise ValueError("卷七起月起时原句与所选表不一致。")
        for key in (
            "version",
            "source_title",
            "source_url",
            "source_pdf_sha256",
            "review_status",
            "authorship_status",
            "scope",
        ):
            if not isinstance(data[key], str) or not data[key].strip():
                raise ValueError("卷七起月起时来源元数据缺失。")
        if data["source_pdf_pages"] != [108]:
            raise ValueError("卷七原页不一致。")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_pillar_link_source_data") from exc
    data["loaded_sha256"] = sha256(raw).hexdigest()
    return data


def pillar_link_evidence(pillars: dict[str, str]) -> dict[str, Any]:
    if not isinstance(pillars, dict) or any(
        not isinstance(pillars.get(k), str) or pillars[k] not in CYCLE
        for k in ("year", "month", "day", "hour")
    ):
        raise ValueError("干支衔接核对需要四个有效六十甲子。")
    source = _source()
    rows = []
    for target, basis in (("month", "year"), ("hour", "day")):
        basis_stem = pillars[basis][0]
        head = next(
            r for r in source[target + "_heads"] if basis_stem in r["basis_stems"]
        )
        branch = pillars[target][1]
        step = source[target + "_branch_order"].index(branch)
        expected = GAN[(GAN.index(head["head"][0]) + step) % 10] + branch
        rows.append(
            {
                "target": target,
                "basis": basis,
                "basis_pillar": pillars[basis],
                "basis_stem": basis_stem,
                "source_stem_group": head["basis_stems"],
                "head_pillar": head["head"],
                "branch_step": step,
                "actual_pillar": pillars[target],
                "expected_pillar": expected,
                "matches": pillars[target] == expected,
            }
        )
    return {
        "ruleset_id": RULESET_ID,
        "version": source["version"],
        "source_title": source["source_title"],
        "source_url": source["source_url"],
        "source_pdf_sha256": source["source_pdf_sha256"],
        "source_pdf_pages": source["source_pdf_pages"][:],
        "review_status": source["review_status"],
        "authorship_status": source["authorship_status"],
        "collation_sha256": source["loaded_sha256"],
        "pillars": dict(pillars),
        "links": rows,
        "all_links_match": all(r["matches"] for r in rows),
        "basis_policy": "actual_selected_year_and_day_pillars; no_civil_year_or_unrolled_day_substitution",
        "scope": source["scope"],
        "complete_calendar_assessment": False,
        "constraint": "本段只核已选年干起月干、日干起时干及支序衔接；不据此证明原典年界、月界、子时换日、历史钟制或全历法准确。",
    }


def require_pillar_links(pillars: dict[str, str]) -> dict[str, Any]:
    evidence = pillar_link_evidence(pillars)
    for row in evidence["links"]:
        if not row["matches"]:
            label = "月柱与年干" if row["target"] == "month" else "时柱与日干"
            raise ValueError(
                f"{label}衔接不一致：所给{row['actual_pillar']}，按卷七附法应为{row['expected_pillar']}。"
            )
    return evidence


def verified_computed_pillars(pillars: dict[str, str]) -> dict[str, Any]:
    """A disagreement in internally computed pillars is not the user's input fault."""
    try:
        return require_pillar_links(pillars)
    except ValueError as exc:
        raise NumerologySourceError("runtime_pillar_link_conflict") from exc


def attach_pillar_links(evidence: dict[str, Any], links: dict[str, Any]) -> None:
    evidence["pillar_links"] = deepcopy(links)
    evidence["rulesets"].append(
        {
            k: links[k]
            for k in (
                "ruleset_id",
                "version",
                "source_title",
                "source_url",
                "source_pdf_sha256",
                "authorship_status",
            )
        }
    )
    evidence["rulesets"][-1]["source_status"] = links["review_status"]
    evidence["rule_trace"].append(
        {
            "rule_id": RULESET_ID,
            "source_section": "卷七附法年上起月、日上起时；非原典历法边界认证",
            "facts": deepcopy(links),
        }
    )
    evidence["interpretation_constraints"].append(links["constraint"])


def pillar_link_snapshot(evidence: dict[str, Any]) -> str:
    lines = ["[四柱干支衔接·卷七附法]"]
    for row in evidence["links"]:
        target = "月柱" if row["target"] == "month" else "时柱"
        basis = "年柱" if row["basis"] == "year" else "所用日柱"
        lines.append(
            f"{basis}{row['basis_pillar']}，{row['source_stem_group']}组从{row['head_pillar']}顺行{row['branch_step']}步；{target}{row['actual_pillar']}，原句式{'匹配' if row['matches'] else '不匹配'}。"
        )
    lines.append(evidence["constraint"])
    return "\n".join(lines)
