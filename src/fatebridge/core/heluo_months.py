"""Named hexagram month and additional literal windows, kept distinct."""

import json
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Optional

from fatebridge.core.heluo_seasonal import SOURCE_SHA256, SOURCE_URL
from fatebridge.utils.data import get_nayin
from fatebridge.utils.errors import NumerologySourceError

MonthAssignmentMethod = Literal["intro_preferred_v1", "volume_one_table_v1"]
DEFAULT_MONTH_ASSIGNMENT: MonthAssignmentMethod = "intro_preferred_v1"
RULESET_ID = "heluo_wenming_assigned_month_and_windows_v2"
MONTH_BRANCHES = "寅卯辰巳午未申酉戌亥子丑"
COLLATION_PATH = (
    Path(__file__).resolve().parents[1] / "data/heluo/month-collation-v1.json"
)

FRONT_TABLE_PATH = COLLATION_PATH.with_name("volume-one-month-table-v1.json")
INTRO_FACT_SHA256 = "455698ceb175ead962ab71a80a07a8edff41dee7cd146070e925bbe35f02369d"
FRONT_FACT_SHA256 = "431781df084faf624937a7c984d7e6d5ac84155d69579eb54d5cf399a69d334e"


def _fact_hash(data: dict[str, Any]) -> str:
    # Version/scope annotations may change; source facts and review status may not.
    if not isinstance(data, dict):
        raise ValueError("卦月校勘根对象必须为字典。")
    facts = {k: v for k, v in data.items() if k not in {"version", "scope"}}
    return sha256(
        json.dumps(
            facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


@lru_cache(maxsize=1)
def _front_table() -> dict[str, Any]:
    try:
        raw = FRONT_TABLE_PATH.read_bytes()
        data: dict[str, Any] = json.loads(raw)
        if _fact_hash(data) != FRONT_FACT_SHA256:
            raise ValueError("卷首月表事实与封存校勘不一致。")
        data["loaded_sha256"] = sha256(raw).hexdigest()
        return data
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_month_source_data") from exc


def _load_collation() -> dict[str, Any]:
    raw = COLLATION_PATH.read_bytes()
    data: dict[str, Any] = json.loads(raw)
    if _fact_hash(data) != INTRO_FACT_SHA256:
        raise ValueError("卦条月份事实与封存校勘不一致。")
    assigned = data["assigned_months"]
    windows = data["windows"]
    clauses = data["natal_najia_clauses"]
    by_id = {c["id"]: c for c in clauses}
    if (
        data["source_pdf_sha256"] != SOURCE_SHA256
        or len({c["id"] for c in clauses}) != len(clauses)
        or len({c["gua"] for c in clauses}) != len(clauses)
        or any(
            type(m) is not int or m not in range(1, 13)
            for c in clauses
            for m in c["month_numbers"]
        )
        or any(c["connector_status"] != "source_ji_scope_unresolved" for c in clauses)
        or any(
            w.get("natal_najia_clause_id") not in by_id
            or any(
                w[key] != by_id[w["natal_najia_clause_id"]][key]
                for key in ("gua", "page", "literal", "month_numbers")
            )
            for w in windows
            if w["meaning"] == "named_months_with_najia"
        )
        or len({r["gua"] for r in assigned}) != len(assigned)
        or len({w["id"] for w in windows}) != len(windows)
        or not isinstance(data["version"], str)
        or any(
            type(r["month"]) is not int or r["month"] not in range(1, 13)
            for r in assigned
        )
        or any(
            type(r["page"]) is not int or r["page"] < 1
            for r in assigned + windows + clauses
        )
        or any(
            type(m) is not int or m not in range(1, 13)
            for w in windows
            for m in w["month_numbers"] + w.get("uncertain_month_numbers", [])
        )
    ):
        raise ValueError("河洛卦月校勘索引重复或月份无效。")
    data["loaded_sha256"] = sha256(raw).hexdigest()
    return data


@lru_cache(maxsize=1)
def _collation() -> dict[str, Any]:
    try:
        return _load_collation()
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_month_source_data") from exc


def _window(source: dict[str, Any], month: int) -> dict[str, Any]:
    """Separate month-label membership from unevaluated additional conditions."""
    uncertain = source.get("uncertain_month_numbers", [])
    label_match = None if month in uncertain else month in source["month_numbers"]
    qualifiers = source.get("qualifiers", [])
    match = None if qualifiers else label_match
    result = {
        "rule_id": source["id"],
        "source_pdf_page": source["page"],
        "literal": source["literal"],
        "kind": source["kind"],
        "meaning": source["meaning"],
        "month_numbers": list(source["month_numbers"]),
        "uncertain_month_numbers": list(uncertain),
        "month_label_match": label_match,
        "qualifiers": list(qualifiers),
        "qualifier_status": "not_evaluated" if qualifiers else "none",
        "match": match,
        "status": (
            "endpoint_month_unresolved"
            if label_match is None
            else (
                "additional_condition_unresolved"
                if match is None
                else "literal_month_number_match"
            )
        ),
    }
    if source.get("natal_najia_clause_id"):
        result["natal_najia_clause_id"] = source["natal_najia_clause_id"]
    for key in (
        "first_month_number",
        "last_month_number",
        "first_month_inclusive",
        "last_month_inclusive",
    ):
        if key in source:
            result[key] = source[key]
    return result


def _najia_index(
    chart: dict[str, Any], assessments: Optional[list[dict[str, Any]]]
) -> dict[str, dict[str, Any]]:
    """Reuse actual six-line results, validating phase/year and their match list."""
    if assessments is None:
        return {}
    if not isinstance(assessments, list) or len(assessments) != 2:
        raise ValueError("卦月纳甲依据须包含先后天各一项实际六爻结果。")
    result = {}
    for row in assessments:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("phase"), str)
            or row.get("phase") not in {"xian", "hou"}
            or row["phase"] in result
        ):
            raise ValueError("卦月纳甲依据阶段缺失或重复。")
        phase = row["phase"]
        year = row.get("year_ganzhi")
        lines = row.get("lines")
        if (
            row.get("gua") != chart[phase]["name"]
            or not isinstance(year, str)
            or len(year) != 2
            or get_nayin(year[0], year[1]) == "未知纳音"
            or not isinstance(lines, list)
            or len(lines) != 6
            or [line.get("pos") for line in lines if isinstance(line, dict)]
            != list(range(1, 7))
            or any(type(line["pos"]) is not int for line in lines)
        ):
            raise ValueError("卦月纳甲依据与实际卦名、年干支或六爻位置不一致。")
        expected = []
        for line in lines:
            if (
                not isinstance(line.get("direct"), str)
                or not isinstance(line.get("borrowed"), list)
                or any(not isinstance(x, str) for x in line["borrowed"])
            ):
                raise ValueError("卦月纳甲依据须保留正纳及借用。")
            if line["direct"] == year:
                expected.append({"pos": line["pos"], "kind": "direct"})
            if year in line["borrowed"]:
                expected.append({"pos": line["pos"], "kind": "borrowed"})
        matches = row.get("matches")
        if not isinstance(matches, list) or any(
            not isinstance(m, dict)
            or type(m.get("pos")) is not int
            or m.get("kind") not in ("direct", "borrowed")
            for m in matches
        ):
            raise ValueError("卦月纳甲命中位置与类型必须明确。")
        if (
            row.get("matches") != expected
            or type(row.get("present")) is not bool
            or row["present"] != bool(expected)
        ):
            raise ValueError(
                "卦月纳甲命中必须来自该阶段实际六爻，不能以另一阶段或合并布尔代替。"
            )
        result[phase] = {
            k: deepcopy(row[k])
            for k in ("phase", "gua", "year_ganzhi", "matches", "present")
        }
    if len({row["year_ganzhi"] for row in result.values()}) != 1:
        raise ValueError("先后天卦月纳甲依据必须使用同一出生年干支。")
    return result


def month_affinity(
    chart: dict[str, Any],
    month_branch: str,
    assigned_table: dict[str, list[str]],
    *,
    najia_assessments: Optional[list[dict[str, Any]]] = None,
    assignment_method: MonthAssignmentMethod = DEFAULT_MONTH_ASSIGNMENT,
) -> dict[str, Any]:
    """The caller's month-branch convention is explicit, not a lunar-date claim.

    Discrete months, ranges and season labels stay distinct. Ambiguous endpoints,
    unevaluated qualifiers and opposed clauses are never resolved by priority.
    """
    if (
        not isinstance(month_branch, str)
        or len(month_branch) != 1
        or month_branch not in MONTH_BRANCHES
    ):
        raise ValueError("卦月匹配需要明确的出生月支。")
    if assignment_method not in ("intro_preferred_v1", "volume_one_table_v1"):
        raise ValueError("卦属月方法须明确为intro_preferred_v1或volume_one_table_v1。")
    birth_month = MONTH_BRANCHES.index(month_branch) + 1
    data = _collation()
    front = _front_table()
    najia = _najia_index(chart, najia_assessments)
    phases = []
    for phase in ("xian", "hou"):
        name = chart[phase]["name"]
        anchor = next((r for r in data["assigned_months"] if r["gua"] == name), None)
        table_anchor = next(
            (r for r in front["assigned_months"] if r["gua"] == name), None
        )
        if table_anchor is None:
            raise NumerologySourceError("invalid_month_source_data")
        selected_section = (
            "hexagram_intro"
            if assignment_method == "intro_preferred_v1" and anchor is not None
            else "volume_one_table"
        )
        selected = anchor if selected_section == "hexagram_intro" else table_anchor
        assert selected is not None
        assigned_number = selected["month"]
        assigned = MONTH_BRANCHES[assigned_number - 1]
        if assignment_method == "intro_preferred_v1":
            short = name[0] if name[1] == "為" else name[2:]
            legacy = [b for b, names in assigned_table.items() if short in names]
            if legacy != [assigned]:
                raise NumerologySourceError("runtime_month_assignment_conflict")
        readings = [
            {
                "section": "hexagram_intro",
                "month_number": anchor["month"] if anchor else None,
                "source_pdf_page": anchor["page"] if anchor else 177,
                "literal": None,
                "month_label_match": birth_month == anchor["month"] if anchor else None,
                "status": "explicit_month" if anchor else "month_not_explicit",
            },
            {
                "section": "volume_one_table",
                "month_number": table_anchor["month"],
                "source_pdf_page": table_anchor["page"],
                "literal": table_anchor["literal"],
                "month_label_match": birth_month == table_anchor["month"],
                "status": "explicit_month",
            },
        ]
        source_match_values = [r["month_label_match"] for r in readings]
        consensus = (
            source_match_values[0]
            if None not in source_match_values and len(set(source_match_values)) == 1
            else None
        )
        windows = [_window(w, birth_month) for w in data["windows"] if w["gua"] == name]
        timely = [
            w["rule_id"]
            for w in windows
            if w["meaning"] == "timely" and w["month_label_match"] is True
        ]
        untimely = [
            w["rule_id"]
            for w in windows
            if w["meaning"] == "untimely" and w["month_label_match"] is True
        ]
        clause_source = next(
            (c for c in data["natal_najia_clauses"] if c["gua"] == name), None
        )
        clause = (
            None
            if clause_source is None
            else {
                "rule_id": clause_source["id"],
                "source_pdf_page": clause_source["page"],
                "literal": clause_source["literal"],
                "month_numbers": clause_source["month_numbers"][:],
                "month_label_match": birth_month in clause_source["month_numbers"],
                "najia": deepcopy(najia.get(phase)),
                "qualifier_status": (
                    "current_phase_facts_available"
                    if phase in najia
                    else "not_evaluated_missing_najia"
                ),
                "connector_status": clause_source["connector_status"],
                "match": None,
                "scope": clause_source["scope"],
            }
        )
        phases.append(
            {
                "phase": phase,
                "gua": name,
                "assigned_month_number": assigned_number,
                "assigned_month_branch": assigned,
                "assigned_month_match": month_branch == assigned,
                "source_status": (
                    "assigned_month_visually_collated"
                    if selected_section == "hexagram_intro"
                    else "volume_one_table_explicit_month"
                ),
                "source_pdf_page": selected["page"],
                "selected_month_source": selected_section,
                "source_readings": readings,
                "source_months_agree": (
                    anchor["month"] == table_anchor["month"] if anchor else None
                ),
                "source_consensus_match": consensus,
                "additional_windows": windows,
                "natal_najia_clause": clause,
                "opposed_month_conditions": bool(timely and untimely),
                "conflict_rule_ids": timely + untimely if timely and untimely else [],
            }
        )
    return {
        "ruleset_id": RULESET_ID,
        "version": "3.0.0",
        "assignment_method": assignment_method,
        "volume_one_explicit_months": len(front["assigned_months"]),
        "volume_one_collation_sha256": front["loaded_sha256"],
        "intro_fact_sha256": INTRO_FACT_SHA256,
        "volume_one_fact_sha256": FRONT_FACT_SHA256,
        "source_assignment_conflicts": [
            {
                "gua": r["gua"],
                "intro_month": a["month"],
                "intro_pdf_page": a["page"],
                "table_month": r["month"],
                "table_pdf_page": r["page"],
            }
            for r in front["assigned_months"]
            for a in data["assigned_months"]
            if r["gua"] == a["gua"] and r["month"] != a["month"]
        ],
        "source_consensus_match": (
            True
            if any(p["source_consensus_match"] is True for p in phases)
            else (
                None
                if any(p["source_consensus_match"] is None for p in phases)
                else False
            )
        ),
        "collation_version": data["version"],
        "source_url": SOURCE_URL,
        "source_pdf_sha256": SOURCE_SHA256,
        "collation_sha256": data["loaded_sha256"],
        "review_status": data["review_status"],
        "reviewed_hexagram_introductions": data["reviewed_hexagram_introductions"],
        "explicit_assigned_months": len(data["assigned_months"]),
        "additional_month_clauses": len(data["windows"]),
        "registered_natal_najia_clauses": len(data["natal_najia_clauses"]),
        "birth_month_branch": month_branch,
        "birth_month_number": birth_month,
        "month_number_policy": "month_labels_from_four_pillar_branch; source_lunar_vs_solar_boundary_not_resolved",
        "phases": phases,
        "complete_assessment": False,
        "scope": data["scope"],
        "unresolved": [
            "乾卦八月以前的边界月暂不裁成包含或排除，八月匹配为null。",
            "頤卦九月後的九月边界暂不裁定，九月匹配为null。",
            "隨卦正月同时进入及时和失时两段，保留相反条件及规则ID，不挑选有利段覆盖。",
            "十三条具名月号／年命纳甲句分别列出同阶段两项事实；及字连接范围与解卦本命月卦例外未决，单项未中或命中都不替代整条判定。",
            "解卦第214页纳甲列举末两支顺序与按爻位排列表不同，成员一致；尚未核定列举是否按爻位，不称该卦六项爻位已完成原页核对。",
            "月号按输入四柱月支解释，尚未据底本统一月界，不能直接称为农历月或精确节气区间。",
            "無妄总论第177页写巽宫五世且仅称所属本月；卷首第18页明列八月。默认缺号时采用卷首明文，保留总论未明及世爻疑点，不用推演改字。",
            "卷首八宫所属与后卷卦条有晋、节、睽、震、井五处月号差异；方法选择不解决底本内讹异，source_consensus_match=null表示来源不足或本月判断相反。",
            "第38页月卦从世应口诀处于运例上下文，未据此覆盖静态月表；适用范围及反例待核。",
            "得体包含命与卦体相生等语义；继承日干映射不等于该项完成。",
        ],
    }
