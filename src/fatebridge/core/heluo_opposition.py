"""Born-year Yuanqi opposition with the printed absence premise preserved."""

import json
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any

from fatebridge.core.heluo_body import BODY_POSITIONS
from fatebridge.utils.errors import NumerologySourceError

SOURCE_PATH = (
    Path(__file__).resolve().parents[1] / "data/heluo/yuanqi-opposition-v1.json"
)
RULESET_ID = "heluo_wenming_yuanqi_opposition_v1"
CONTENT_SHA256 = "b2e3fb847000313ea44615fbca38117cfce093964cb09156741f06cf3fc640c5"


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    try:
        raw = SOURCE_PATH.read_bytes()
        data: dict[str, Any] = json.loads(raw)
        canonical = json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        if sha256(canonical).hexdigest() != CONTENT_SHA256:
            raise ValueError("元气相反来源版本内容不符。")
    except (OSError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_heluo_opposition_source") from exc
    data["loaded_sha256"] = sha256(raw).hexdigest()
    return data


def _conflict() -> None:
    raise NumerologySourceError("runtime_heluo_yuanqi_context_conflict")


def opposition_evidence(
    year_ganzhi: str,
    bodies: list[dict[str, Any]],
    yuan: dict[str, str],
    fan: dict[str, str],
) -> dict[str, Any]:
    """Check actual candidates and bodies, then evaluate each phase separately.

    A target's presence is a fact, not the absence-plus-opposite condition. Direct
    bodies alone are a labelled comparison; they never replace the named scope.
    The source's Qian example is a generalization premise, not eight birth cases.
    """
    from fatebridge.core.heluo_hexagrams import (
        GAN,
        ZHI,
        _trigram_of,
        gua_lines,
        lines_to_gua,
    )

    source = _source()
    cycle = {GAN[i % 10] + ZHI[i % 12] for i in range(60)}
    if not isinstance(year_ganzhi, str) or year_ganzhi not in cycle:
        _conflict()
    targets = {}
    for kind, symbol in zip(("tian", "di"), year_ganzhi):
        mapping = next(r for r in source["mappings"] if symbol in r["symbols"])
        targets[kind] = mapping
    if yuan != {k: r["yuan"] for k, r in targets.items()} or fan != {
        k: r["fan"] for k, r in targets.items()
    }:
        _conflict()
    if not isinstance(bodies, list) or len(bodies) != 8:
        _conflict()
    phases = []
    try:
        for phase in ("xian", "hou"):
            rows = [r for r in bodies if r["phase"] == phase]
            kinds = [kind for kind, _ in BODY_POSITIONS]
            if len(rows) != 4 or [r["kind"] for r in rows] != kinds:
                _conflict()
            by_kind = {r["kind"]: r for r in rows}
            bits = gua_lines(by_kind["upper"]["trigram"], by_kind["lower"]["trigram"])
            name = lines_to_gua(bits)["name"]
            for row, (kind, positions) in zip(rows, BODY_POSITIONS):
                if (
                    row["body_id"] != f"{phase}.{kind}"
                    or row["gua"] != name
                    or row["line_positions"] != positions
                    or any(type(p) is not int for p in row["line_positions"])
                    or row["trigram"] != _trigram_of([bits[p - 1] for p in positions])
                ):
                    _conflict()
            conditions = []
            for kind, mapping in targets.items():
                original = [
                    r["body_id"] for r in rows if r["trigram"] == mapping["yuan"]
                ]
                opposite = [
                    r["body_id"] for r in rows if r["trigram"] == mapping["fan"]
                ]
                direct = {r["body_id"] for r in rows if r["kind"] in {"lower", "upper"}}
                conditions.append(
                    {
                        "kind": kind,
                        "yuan_trigram": mapping["yuan"],
                        "fan_trigram": mapping["fan"],
                        "yuan_body_ids": original,
                        "fan_body_ids": opposite,
                        "yuan_absent": not original,
                        "fan_present": bool(opposite),
                        "condition_match": not original and bool(opposite),
                        "direct_only_condition_match": not direct.intersection(original)
                        and bool(direct.intersection(opposite)),
                        "rescue_match": None,
                    }
                )
            phases.append({"phase": phase, "gua": name, "conditions": conditions})
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise NumerologySourceError("runtime_heluo_yuanqi_context_conflict") from exc
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
                "year_context_literal",
                "absence_literal",
                "rescue_literal",
                "scope",
            )
        },
        "collation_sha256": source["loaded_sha256"],
        "content_sha256": CONTENT_SHA256,
        "year_ganzhi": year_ganzhi,
        "body_scope_policy": "each_phase_lower_upper_and_two_nuclear_bodies; no_cross_phase_substitution",
        "direct_only_policy": "comparison_only; not_selected_body_scope",
        "phases": phases,
        "full_rescue_assessment": False,
        "unresolved": [
            "卦中无正而有反在所列上下体／两互体范围分别求值；乾例扩展至八组映射为具名解释，不是八个原典命例。",
            "原句还要求分节气浅深、气虚与尅制，未量化前rescue_match保持null；无正而有反式不等于完整相反或现实吉凶。",
            "第35页整卦正对／反对图是另一结构层，不以全卦倒序代替年干支的八卦反元气映射。",
        ],
    }


def opposition_snapshot(evidence: dict[str, Any]) -> str:
    lines = ["[元气相反·无正而有反前提]"]
    for row in evidence["phases"]:
        label = "先天" if row["phase"] == "xian" else "后天"
        for condition in row["conditions"]:
            kind = "天" if condition["kind"] == "tian" else "地"
            absent = "无" if condition["yuan_absent"] else "有"
            opposite = "有" if condition["fan_present"] else "无"
            match = "匹配" if condition["condition_match"] else "未匹配"
            lines.append(
                f"{label}·{row['gua']}·{kind}元气{condition['yuan_trigram']}：{absent}正体，"
                f"{opposite}反候选{condition['fan_trigram']}；无正而有反式{match}。"
            )
    lines.append(
        "各阶段按上下体和两互体分别核对；只取上下体的比较不替换本取法。反中有救与综合葉否未定。"
    )
    return "\n".join(lines)
