"""Trace the named Jian four/eight-body paragraph without conflating body kinds."""

import json
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.utils.errors import NumerologySourceError

SOURCE_PATH = Path(__file__).resolve().parents[1] / "data/heluo/body-structure-v1.json"
RULESET_ID = "heluo_wenming_jian_structure_v1"
# All positions refer to the original phase, bottom to top. These are
# permutations/selections: no operation changes any line's polarity.
OPERATORS = (
    ("lower", (1, 2, 3)),
    ("upper", (4, 5, 6)),
    ("lower_reversed", (3, 2, 1)),
    ("upper_reversed", (6, 5, 4)),
    ("upper_nuclear", (3, 4, 5)),
    ("lower_nuclear", (2, 3, 4)),
    ("third_to_top", (1, 2, 4, 5, 6, 3)),
    ("reverse_then_third_to_top", (6, 5, 3, 2, 1, 4)),
)


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    try:
        raw = SOURCE_PATH.read_bytes()
        data: dict[str, Any] = json.loads(raw)
        if (
            data["ruleset_id"] != RULESET_ID
            or data["source_case_gua"] != "風山漸"
            or data["source_case_names"]
            != ["艮", "巽", "震", "兌", "離", "坎", "天地否", "地天泰"]
            or data["source_case_reversed_name"] != "雷澤歸妹"
            or data["five_ming_symbol_readings"]
            != {
                "金": "庚辛申酉",
                "木": "甲乙寅卯",
                "水": "壬癸亥子",
                "火": "丙丁巳午",
                "土": "戊己辰戌丑未",
            }
            or not isinstance(data["wording_variants"], list)
            or len(data["wording_variants"]) != 1
            or data["wording_variants"][0]["primary_reading"] != "以八體言之"
            or data["wording_variants"][0]["counterpart_reading"] != "以八卦言之"
        ):
            raise ValueError("卦体原例来源身份不一致。")
        for key in (
            "version",
            "source_url",
            "source_pdf_sha256",
            "review_status",
            "scope",
        ):
            if not isinstance(data[key], str) or not data[key].strip():
                raise ValueError("卦体原例来源元数据缺失。")
        if data["source_pdf_pages"] != [75, 76, 77, 78] or data[
            "calculation_source_pdf_pages"
        ] != [77, 78]:
            raise ValueError("卦体原例原页范围不一致。")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_body_structure_source_data") from exc
    data["loaded_sha256"] = sha256(raw).hexdigest()
    return data


def _name(bits: list[int]) -> str:
    # The existing shared six-line decoder remains the single naming source.
    # Import only on use, after heluo has initialized its lookup functions.
    from fatebridge.core.heluo_hexagrams import _trigram_of, lines_to_gua

    return _trigram_of(bits) if len(bits) == 3 else lines_to_gua(bits)["name"]


def body_structure(chart: dict[str, Any]) -> dict[str, Any]:
    source = _source()
    phases = []
    for phase in ("xian", "hou"):
        original = chart[phase]
        bits = original["lines"]
        if (
            not isinstance(bits, list)
            or len(bits) != 6
            or any(type(b) is not int or b not in (0, 1) for b in bits)
            or _name(bits) != original["name"]
        ):
            raise ValueError("卦体结构需要同阶段一致的卦名与六个整数阴阳爻。")
        literal_case = original["name"] == source["source_case_gua"]
        records = []
        for kind, positions in OPERATORS:
            selected = [bits[p - 1] for p in positions]
            records.append(
                {
                    "kind": kind,
                    "arity": len(positions),
                    "original_positions": list(positions),
                    "lines": selected,
                    "name": _name(selected),
                }
            )
        reversed_bits = bits[::-1]
        reversed_name = _name(reversed_bits)
        phases.append(
            {
                "phase": phase,
                "gua": original["name"],
                "input_lines": bits[:],
                "records": records,
                "record_count": 8,
                "whole_reversal": {
                    "original_positions": [6, 5, 4, 3, 2, 1],
                    "lines": reversed_bits,
                    "name": reversed_name,
                },
                "literal_case_match": literal_case,
                "literal_names_reproduced": (
                    [r["name"] for r in records] == source["source_case_names"]
                    and reversed_name == source["source_case_reversed_name"]
                    if literal_case
                    else None
                ),
                "source_application": (
                    "named_jian_paragraph"
                    if literal_case
                    else "permutation_derivation; not_this_hexagrams_literal_source_example"
                ),
            }
        )
    return {
        "ruleset_id": RULESET_ID,
        "version": source["version"],
        "source_url": source["source_url"],
        "source_pdf_sha256": source["source_pdf_sha256"],
        "source_pdf_pages": source["source_pdf_pages"][:],
        "calculation_source_pdf_pages": source["calculation_source_pdf_pages"][:],
        "collation_sha256": source["loaded_sha256"],
        "review_status": source["review_status"],
        "wording_variants": deepcopy(source["wording_variants"]),
        "phases": phases,
        "five_ming_terminology": {
            "symbol_readings": deepcopy(source["five_ming_symbol_readings"]),
            "source_pdf_pages": [75, 76],
            "selected_pillar": None,
            "nayin_substituted": False,
            "scope": "literal_symbol_lists_only; no_global_person_element_selection",
        },
        "scope": source["scope"],
        "complete_futi_assessment": False,
        "complete_assessment": False,
        "constraints": [
            "八条记录包括六个三爻体和两个六爻卦，数量不等于八个不同互体。",
            "三爻倒序、全卦倒序和抽出第三爻移至最上位分别记录；移爻不翻转阴阳，也不是后天换卦。",
            "渐卦段明确的伏震、伏兑不升级为全书伏体的统一定义；其他卦仅为本组算子的明确推演。",
            "五命段另列庚辛申酉等干支；未选定所用柱，不用年纳音或日干自动代替该段全部术语。",
            "本结构层不改变年纳音关系、元气或化工取体，不独自裁定得体、合理、葉否或现实结果。",
        ],
    }


def structure_snapshot(evidence: dict[str, Any]) -> str:
    lines = ["[卦体结构·渐卦原例取法]"]
    for row in evidence["phases"]:
        phase = "先天" if row["phase"] == "xian" else "后天"
        names = "、".join(r["name"] for r in row["records"])
        basis = "所核渐卦原例" if row["literal_case_match"] else "所列算子推演"
        lines.append(
            f"{phase}·{row['gua']}：{names}；全卦倒序为{row['whole_reversal']['name']}。依据：{basis}。"
        )
    lines.append(
        "八条记录含三爻体与六爻卦，不能当作八个互体合并纳音；完整伏体、得体与葉否未裁定。"
    )
    return "\n".join(lines)
