"""The selected printing's term gua and its distinct, conflicted hou scheme.

Named-term lookup does not turn nominal days into civil dates. Literal labels,
hexagram polarity and the six-day reconstruction remain separately available.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.core.heluo import yao_name
from fatebridge.core.heluo_hexagrams import _gua_tables, gua_lines
from fatebridge.utils.errors import NumerologySourceError

RULESET_ID = "heluo_wenming_jiehou_v1"
SOURCE_PATH = Path(__file__).resolve().parents[1] / "data/heluo/jiehou-v1.json"
SOURCE_SHA256 = "6bcf0814cad984d035b2df99e5ff2de0edcd7bfde7c930aca570da164d55c5d2"
ALIASES = {
    "谷雨": "穀雨",
    "小满": "小滿",
    "芒种": "芒種",
    "处暑": "處暑",
    "惊蛰": "驚蟄",
}
MODELS = ("continuous_yao_from_yi_four", "six_days_per_gua_caption_first")


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    try:
        raw = SOURCE_PATH.read_bytes()
        data: dict[str, Any] = json.loads(raw)
        if (
            sha256(raw).hexdigest() != SOURCE_SHA256
            or data["ruleset_id"] != RULESET_ID
            or data["version"] != "1.0.0"
            or len(data["term_rows"]) != 24
            or len(data["hou_rows"]) != 72
            or len(data["gua_order"]) != 60
            or len(set(data["gua_order"])) != 60
        ):
            raise ValueError("所选节候表的身份、字节或条目不一致。")
        # The digest fixes literal errors too; a convenient correction is a
        # different source/version, never an invisible rewrite of this one.
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_jiehou_source") from exc
    data["loaded_sha256"] = sha256(raw).hexdigest()
    return data


def _term(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("节候查表需要明确节气名，不能猜候或出生时间。")
    name = ALIASES.get(name, name)
    if name not in {row["term"] for row in _source()["term_rows"]}:
        raise ValueError("所选底本没有该节气名。")
    return name


def _form(gua: str, position: int) -> dict[str, Any]:
    pair = _gua_tables()[0][gua]
    lines = gua_lines(pair["up"], pair["low"])
    return dict(gua=gua, lines=lines, position=position, yao=yao_name(lines, position))


def term_assignment(name: str) -> dict[str, Any]:
    name = _term(name)
    row = next(r for r in _source()["term_rows"] if r["term"] == name)
    return {**deepcopy(row), **_form(row["gua"], row["position"])}


def literal_hou_table() -> list[dict[str, Any]]:
    result = []
    for row in _source()["hou_rows"]:
        position = 4 if row["raw_yao"] == "六四" else 1
        form = _form(row["gua"], position)
        result.append(
            dict(
                **deepcopy(row),
                printed_position=position,
                canonical_yao=form["yao"],
                yao_polarity_agrees=row["raw_yao"] == form["yao"],
            )
        )
    return result


def nominal_hou_day(day_offset: int, *, model: str) -> dict[str, Any]:
    """A rule reconstruction from winter/Yi-six-four, for nominal days0..359.

    The chosen60-gua order and one yao per day produce360 nominal slots. This
    does not resolve the printed caption/table conflicts or extra-ke mapping.
    """
    if type(day_offset) is not int or not 0 <= day_offset < 360:
        raise ValueError("候卦名义日序须明确为0至359的整数；不静默进年。")
    if not isinstance(model, str) or model not in MODELS:
        raise ValueError("须明确指定具名候卦重建模型；不按吻合程度暗选。")
    if model == "continuous_yao_from_yi_four":
        offset = (day_offset + 3) % 360
        gua_index, position = offset // 6, offset % 6 + 1
    else:
        gua_index = day_offset // 6
        position = ((day_offset + 3) % 6 + 1) if gua_index == 0 else day_offset % 6 + 1
    gua = _source()["gua_order"][gua_index]
    return dict(
        **_form(gua, position),
        model=model,
        day_offset=day_offset,
        origin="printed_winter_solstice_yi_six_four; no_civil_instant",
        basis="sixty_gua_order_and_one_yao_per_nominal_day_reconstruction",
        derived_only=True,
        physical_date_applied=False,
        extra_ke_applied=False,
    )


def caption_comparison(*, model: str) -> list[dict[str, Any]]:
    caption = _source()["caption"]
    result = []
    for offset, row in enumerate(caption["rows"]):
        derived = nominal_hou_day(offset, model=model)
        result.append(
            dict(
                printed=deepcopy(row),
                derived=derived,
                agrees=(row["gua"], row["position"])
                == (derived["gua"], derived["position"]),
            )
        )
    return result


def term_start_comparisons(*, model: str) -> list[dict[str, Any]]:
    """Compare a15-nominal-day reconstruction, without fixing table headings."""
    rows = literal_hou_table()
    return [
        dict(
            term=row["term"],
            printed_gua=row["gua"],
            printed_yao=row["raw_yao"],
            printed_position=row["printed_position"],
            derived=nominal_hou_day(index * 15, model=model),
            gua_agrees=row["gua"] == nominal_hou_day(index * 15, model=model)["gua"],
            position_agrees=row["printed_position"]
            == nominal_hou_day(index * 15, model=model)["position"],
            interpretation_of_heading_unresolved=True,
        )
        for index, row in enumerate(rows[::3])
    ]


def jiehou_evidence(solar: dict[str, Any]) -> dict[str, Any]:
    """Use the already-computed term label; select no physical hou or outcome."""
    source = _source()
    try:
        term = term_assignment(solar["term"])
        anchor_text = solar["anchor_utc"]
        anchor = datetime.fromisoformat(anchor_text)
        if (
            anchor.utcoffset() != timedelta(0)
            or solar["quarter"] != term["gua"][0]
            or solar["precision"]
            not in {"birth_instant", "date_midnight_approximation"}
        ):
            raise ValueError("节气标签、已算象限或瞬间来源不一致。")
    except (KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("runtime_heluo_jiehou_context_conflict") from exc
    rows = literal_hou_table()
    comparisons = []
    for model in MODELS:
        starts = term_start_comparisons(model=model)
        caption = caption_comparison(model=model)
        comparisons.append(
            dict(
                model=model,
                status="conditional_reconstruction; no_preferred_model",
                caption_comparison=caption,
                caption_difference_count=sum(not r["agrees"] for r in caption),
                term_start_position_difference_count=sum(
                    not r["position_agrees"] for r in starts
                ),
                term_start_gua_difference_count=sum(
                    not r["gua_agrees"] for r in starts
                ),
                selected_term_start_comparison=next(
                    r for r in starts if r["term"] == term["term"]
                ),
            )
        )
    return {
        **{
            k: deepcopy(source[k])
            for k in (
                "ruleset_id",
                "version",
                "source_title",
                "source_url",
                "source_pdf_sha256",
                "source_pdf_pages",
                "review_status",
                "loaded_sha256",
            )
        },
        "selection_basis": "already_computed_term_label; modern_calendar_convention",
        "upstream_term_label": solar["term"],
        "anchor_utc": anchor_text,
        "anchor_precision": solar["precision"],
        "selected_term_gua": term,
        "literal_hou_group": [r for r in rows if r["term"] == term["term"]],
        "selected_hou": None,
        "huagong_assessment": None,
        "counts": dict(
            term_rows=24,
            literal_hou_rows=72,
            distinct_hou_gua=60,
            nominal_gua_days=6,
            nominal_hou_days=5,
            nominal_term_line_days=15,
            nominal_quarter_days=90,
            nominal_year_days=360,
        ),
        "literal_yao_conflicts": [r for r in rows if not r["yao_polarity_agrees"]],
        "reconstruction_models": comparisons,
        "selected_reconstruction_model": None,
        "printed_total_yao_phrase": source["printed_total_yao_phrase"],
        "historical_term_instants_established": False,
        "hou_physical_date_mapping_complete": False,
        "interpretation_constraints": [
            "节卦为坎震离兑四正卦配节气爻序，候卦为另外六十卦的日序；不与本命卦、岁卦、八字月柱或另一卦气表互换。",
            "本次只按共享引擎已算节气名取节卦；十五／九十日是原文名义数，不将现代实际节气间隔截成固定天数。",
            "候卦原印爻名与卦形另列；连续爻序和首卦轮满六日两种重建分别对照交节点及示例，均为条件模型，不按吻合或有利结果选定。",
            "五日一候、六日一卦及寄刻到实际时刻的关系未完成；三项原列候卦不是三个已确定的五日区间，selected_hou保持null。",
            "定节候段的化工／得月语义和三百六十四爻、四爻生八节字面仍待解释，不自动据生时节卦授予化工或现实吉凶。",
        ],
    }


def attach_jiehou_evidence(evidence: dict[str, Any], jiehou: dict[str, Any]) -> None:
    evidence["rulesets"].append(
        {
            **{
                k: jiehou[k]
                for k in (
                    "ruleset_id",
                    "version",
                    "source_title",
                    "source_url",
                    "source_pdf_sha256",
                )
            },
            "source_status": jiehou["review_status"],
        }
    )
    evidence["rule_trace"].append(
        dict(
            rule_id=RULESET_ID,
            source_section="卷一定節候卦說／節卦／候卦定局",
            facts=deepcopy(jiehou),
        )
    )
    evidence["interpretation_constraints"].extend(jiehou["interpretation_constraints"])


def jiehou_snapshot(evidence: dict[str, Any]) -> str:
    term = evidence["selected_term_gua"]
    literals = "；".join(
        f"{r['gua']}原印{r['raw_yao']}" for r in evidence["literal_hou_group"]
    )
    return (
        f"[卷一节候背景]\n按本次节气{evidence['upstream_term_label']}查节卦：{term['gua']}，{term['yao']}。\n"
        f"候卦原列：{literals}。原印与卦形／日序的差异另列，未选实际候卦或裁定化工。"
    )
