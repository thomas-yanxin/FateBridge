"""Named primary Najia assignment lists and actual-position source checks."""

import json
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.core.heluo_seasonal import SOURCE_SHA256
from fatebridge.utils.data import get_nayin
from fatebridge.utils.errors import NumerologySourceError

COLLATION_PATH = (
    Path(__file__).resolve().parents[1] / "data/heluo/najia-collation-v1.json"
)
RULESET_ID = "heluo_wenming_najia_sources_v1"


def _load_source() -> dict[str, Any]:
    raw = COLLATION_PATH.read_bytes()
    data: dict[str, Any] = json.loads(raw)
    pure = data["pure_tables"]
    anchors = data["hexagram_entries"]
    if (
        data["ruleset_id"] != RULESET_ID
        or data["source_pdf_sha256"] != SOURCE_SHA256
        or len(pure) != 8
        or len({p["trigram"] for p in pure}) != 8
        or len({tuple(p["bits"]) for p in pure}) != 8
        or len({p["gua"] for p in anchors}) != len(anchors)
        or len({tuple(p["lines"]) for p in anchors}) != len(anchors)
    ):
        raise ValueError("河洛纳甲来源表身份、纯卦覆盖或条目索引冲突。")
    for p in anchors:
        if (
            len(p["lines"]) != 6
            or any(type(bit) is not int or bit not in (0, 1) for bit in p["lines"])
            or type(p["page"]) is not int
            or p["page"] < 1
            or len(p["direct"]) != 6
            or len(p["borrowed"]) != 6
            or any(not isinstance(xs, list) for xs in p["borrowed"])
            or any(
                not isinstance(gz, str)
                or len(gz) != 2
                or get_nayin(gz[0], gz[1]) == "未知纳音"
                for gz in p["direct"] + [gz for xs in p["borrowed"] for gz in xs]
            )
        ):
            raise ValueError("河洛纳甲原页条目须有六个明确位置、页码与有效干支。")
    for p in pure:
        anchor = next((a for a in anchors if a["gua"] == p["gua"]), None)
        if (
            not isinstance(p["bits"], list)
            or len(p["bits"]) != 3
            or any(type(bit) is not int or bit not in (0, 1) for bit in p["bits"])
            or p["lines"] != p["bits"] * 2
            or anchor
            != {k: p[k] for k in ("gua", "page", "lines", "direct", "borrowed")}
        ):
            raise ValueError("河洛纯卦基础表与同一原页六项读数不一致。")
    # All constituent slots must also agree with the separately read composite
    # entries. This is source consistency, not 64 individually read entries.
    by_bits = {tuple(p["bits"]): p for p in pure}
    for anchor in anchors:
        for pos in range(1, 7):
            component = by_bits[
                tuple(anchor["lines"][:3] if pos <= 3 else anchor["lines"][3:])
            ]
            if (anchor["direct"][pos - 1], anchor["borrowed"][pos - 1]) != (
                component["direct"][pos - 1],
                component["borrowed"][pos - 1],
            ):
                raise ValueError(
                    "河洛所核复卦条目与纯卦内外位置读数冲突，不能自动取舍。"
                )
    data["loaded_sha256"] = sha256(raw).hexdigest()
    return data


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    try:
        return _load_source()
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_source_data") from exc


def collation_summary() -> dict[str, Any]:
    data = _source()
    pure, entries = data["pure_tables"], data["hexagram_entries"]
    return {
        "ruleset_id": RULESET_ID,
        "version": data["version"],
        "sha256": data["loaded_sha256"],
        "source_url": data["source_url"],
        "source_pdf_sha256": data["source_pdf_sha256"],
        "review_status": data["review_status"],
        "pure_trigram_tables": len(pure),
        "pure_table_assignment_slots": sum(len(p["direct"]) for p in pure),
        "pure_table_borrowed_slots": sum(len(xs) for p in pure for xs in p["borrowed"]),
        "directly_collated_hexagrams": len(entries),
        "other_hexagrams_not_individually_collated": 64 - len(entries),
        "direct_assignment_observations": sum(len(p["direct"]) for p in entries),
        "borrowed_assignment_observations": sum(
            len(xs) for p in entries for xs in p["borrowed"]
        ),
        "source_pdf_pages": [p["page"] for p in entries],
        "source_order_issues": deepcopy(data["order_issues"]),
        "unquantified_timing_najia_clauses": deepcopy(
            data["unquantified_timing_najia_clauses"]
        ),
        "complete_assessment": False,
        "scope": data["scope"],
    }


def annotate_positions(
    gua: str, lines: list[int], entries: list[dict[str, Any]]
) -> dict[str, Any]:
    """Check actual results against named source slots, without recomputing them."""
    data = _source()
    if (
        not isinstance(lines, list)
        or len(lines) != 6
        or any(type(bit) is not int or bit not in (0, 1) for bit in lines)
        or not isinstance(entries, list)
        or len(entries) != 6
        or any(not isinstance(e, dict) for e in entries)
        or [e.get("pos") for e in entries] != list(range(1, 7))
        or any(type(e["pos"]) is not int for e in entries)
    ):
        raise ValueError("河洛纳甲取证须有六个明确爻位及其实际计算结果。")
    by_bits = {tuple(p["bits"]): p for p in data["pure_tables"]}
    anchor = next((a for a in data["hexagram_entries"] if a["lines"] == lines), None)
    if anchor is not None and anchor["gua"] != gua:
        raise NumerologySourceError("hexagram_mismatch")
    result = deepcopy(entries)
    for e in result:
        pos = e["pos"]
        component = by_bits[tuple(lines[:3] if pos <= 3 else lines[3:])]
        if (
            e.get("trigram") != component["trigram"]
            or e.get("direct") != component["direct"][pos - 1]
            or e.get("borrowed") != component["borrowed"][pos - 1]
        ):
            raise NumerologySourceError("runtime_assignment_conflict")
        witness = anchor or component
        e["source"] = {
            "basis": "hexagram_entry" if anchor else "pure_trigram_rule",
            "source_hexagram": witness["gua"],
            "source_pdf_page": witness["page"],
            "source_assignment_index": pos,
        }
    return {
        "lines": result,
        "source_issues": deepcopy([i for i in data["order_issues"] if i["gua"] == gua]),
        "source_scope": "Actual positions checked against eight pure-table bases; individual composite-entry collation only where source.basis=hexagram_entry. List order in unresolved entries is not silently identified with line order.",
    }


def najia_snapshot(assessments: list[dict[str, Any]]) -> str:
    lines = ["[年命纳甲与来源]"]
    for row in assessments:
        phase = "先天" if row["phase"] == "xian" else "后天"
        if not row["matches"]:
            lines.append(
                f"{phase}·{row['gua']}：出生年{row['year_ganzhi']}未命中本阶段六爻正纳／借用。"
            )
        for match in row["matches"]:
            entry = row["lines"][match["pos"] - 1]
            source = entry["source"]
            basis = (
                "卦条目所列"
                if source["basis"] == "hexagram_entry"
                else "按纯卦内外位推演"
            )
            kind = "正纳" if match["kind"] == "direct" else "借用"
            lines.append(
                f"{phase}·{row['gua']}：出生年{row['year_ganzhi']}命中计算第{match['pos']}爻{kind}；{basis}，依据{source['source_hexagram']}，PDF第{source['source_pdf_page']}页。"
            )
        if row.get("source_issues"):
            lines.append(
                f"{phase}·{row['gua']}：两印本原文列举末两支顺序与计算爻序不同，成员相同；列举是否按爻位仍未决，不据此换位或称该卦逐爻已核。"
            )
    return "\n".join(lines)
