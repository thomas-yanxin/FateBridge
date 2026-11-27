"""Pure structural Meihua relations, seasonal strength, and 体党/用党 party counts."""

from __future__ import annotations

from typing import Any

from fatebridge.core.hexagram_relations import ELEMENT_GENERATES, relationship_by_role
from fatebridge.core.liuyao.najia import (
    BRANCH_TO_ELEMENT,
    TRIGRAM_LOWER_BRANCHES,
    TRIGRAM_UPPER_BRANCHES,
)
from fatebridge.core.meihua.texts import meihua_ruleset

ROLES = ("use", "body_mutual", "use_mutual", "changed_use")

LABELS = {
    "body": "原体",
    "use": "初用",
    "body_mutual": "体互",
    "use_mutual": "用互",
    "changed_use": "变用",
}

# Pure structural relationship symbols (without counseling prose)
RELATION_SYMBOLS = {
    "体用比和": "比和",
    "体生用": "泄出",
    "体克用": "克出",
    "用生体": "生入",
    "用克体": "克入",
}


def _season(branch: str) -> tuple[str, str, str]:
    if branch not in set("子丑寅卯辰巳午未申酉戌亥"):
        raise ValueError("季令月支必须为十二地支之一。")
    if branch in {"辰", "戌", "丑", "未"}:
        return "四季土月", "土", "水"
    for branches, season, strong, weak in (
        ("寅卯", "春", "木", "土"),
        ("巳午", "夏", "火", "金"),
        ("申酉", "秋", "金", "木"),
        ("亥子", "冬", "水", "火"),
    ):
        if branch in branches:
            return season, strong, weak
    raise ValueError("季令月支必须为十二地支之一。")


def _is_party_element(candidate: str, target: str) -> tuple[bool, str]:
    if candidate == target:
        return True, "same"
    if ELEMENT_GENERATES.get(candidate) == target:
        return True, "generating"
    return False, ""


def compute_party_counts(meihua: dict[str, Any]) -> dict[str, Any]:
    """Compute 体党 / 用党 counts across 本/互/变 trigrams and 本卦 lines."""
    body = meihua["body_trigram"]
    use = meihua["use_trigram"]
    body_elem = body["element"]
    use_elem = use["element"]

    slots = [
        (hex_key, pos, meihua[hex_key][pos])
        for hex_key in ("base_hexagram", "mutual_hexagram", "changed_hexagram")
        for pos in ("upper", "lower")
    ]
    body_same = body_gen = use_same = use_gen = 0
    for _, _, trigram in slots:
        elem = trigram["element"]
        hit_b, kind_b = _is_party_element(elem, body_elem)
        if hit_b:
            if kind_b == "same":
                body_same += 1
            else:
                body_gen += 1
        hit_u, kind_u = _is_party_element(elem, use_elem)
        if hit_u:
            if kind_u == "same":
                use_same += 1
            else:
                use_gen += 1
    body_trigram_party = body_same + body_gen
    use_trigram_party = use_same + use_gen

    base = meihua["base_hexagram"]
    lower_branches = TRIGRAM_LOWER_BRANCHES.get(base["lower"]["name"], ())
    upper_branches = TRIGRAM_UPPER_BRANCHES.get(base["upper"]["name"], ())
    line_elements = [
        BRANCH_TO_ELEMENT[b] for b in (*lower_branches, *upper_branches) if b
    ]
    body_line_party = sum(
        1 for elem in line_elements if _is_party_element(elem, body_elem)[0]
    )
    use_line_party = sum(
        1 for elem in line_elements if _is_party_element(elem, use_elem)[0]
    )
    yang_lines = sum(1 for bit in base["lines"] if bit == 1)
    yin_lines = 6 - yang_lines

    dominant = (
        "body"
        if body_trigram_party > use_trigram_party
        else ("use" if use_trigram_party > body_trigram_party else "equal")
    )
    return {
        "body_trigram": body["name"],
        "body_element": body_elem,
        "use_trigram": use["name"],
        "use_element": use_elem,
        "trigram_counts": {
            "body_party": body_trigram_party,
            "use_party": use_trigram_party,
            "body_same": body_same,
            "body_generating": body_gen,
            "use_same": use_same,
            "use_generating": use_gen,
        },
        "line_counts": {
            "body_party": body_line_party,
            "use_party": use_line_party,
            "yang_lines": yang_lines,
            "yin_lines": yin_lines,
        },
        "dominant_party": dominant,
    }


def meihua_stage_relations(
    meihua: dict[str, Any], *, fact_prefix: str = "meihua"
) -> list[dict[str, Any]]:
    """Compute pure structural body-vs-stage element relations."""
    changed = meihua["changed_hexagram"]
    mutual = meihua["mutual_hexagram"]
    body, use = meihua["body_trigram"], meihua["use_trigram"]
    body_position = "upper" if meihua["moving_palace"] == "下卦" else "lower"
    use_position = "lower" if body_position == "upper" else "upper"
    stages = []
    for role, stage, trigram, path in (
        ("use", "initial", use, "meihua.use_trigram"),
        (
            "body_mutual",
            "middle",
            mutual[body_position],
            f"meihua.mutual_hexagram.{body_position}",
        ),
        (
            "use_mutual",
            "middle",
            mutual[use_position],
            f"meihua.mutual_hexagram.{use_position}",
        ),
        (
            "changed_use",
            "final",
            changed[use_position],
            f"meihua.changed_hexagram.{use_position}",
        ),
    ):
        relation = relationship_by_role(body["element"], trigram["element"])
        stages.append(
            {
                "role": role,
                "stage": stage,
                "body": body["name"],
                "body_element": body["element"],
                "trigram": trigram["name"],
                "element": trigram["element"],
                "relation": relation,
                "traditional_tendency": RELATION_SYMBOLS[relation],
                "fact_path": fact_prefix + path.removeprefix("meihua"),
                "rule_id": "stages" if stage != "middle" else "mutual_roles",
            }
        )
    return stages


def meihua_seasonal_strength(
    meihua: dict[str, Any],
    month_branch: str | None,
    *,
    fact_prefix: str = "meihua",
) -> dict[str, Any] | None:
    """Compute seasonal strength (旺/衰/原文未定) for body and stage trigrams."""
    if month_branch is None:
        return None
    season, strong, weak = _season(month_branch)
    body = meihua["body_trigram"]
    roles = [
        ("body", body["name"], body["element"], fact_prefix + ".body_trigram"),
        *[
            (row["role"], row["trigram"], row["element"], row["fact_path"])
            for row in meihua_stage_relations(meihua, fact_prefix=fact_prefix)
        ],
    ]
    return {
        "month_branch": month_branch,
        "season": season,
        "trigrams": [
            {
                "role": role,
                "trigram": trigram,
                "element": element,
                "strength": (
                    "旺"
                    if element == strong
                    else "衰" if element == weak else "原文未定"
                ),
                "fact_path": path,
            }
            for role, trigram, element, path in roles
        ],
    }


def meihua_traditional_readings(
    stages: list[dict[str, Any]],
    seasonal: dict[str, Any] | None,
    *,
    internal_countercontrol: dict[str, Any] | None = None,
    seasonal_qualification: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Render concise structural stage summary without counseling prose walls."""
    stage_labels = {
        "use": "初应之用",
        "body_mutual": "中间之体互",
        "use_mutual": "中间之用互",
        "changed_use": "终应之变用",
    }
    readings = [
        {
            "role": row["role"],
            "fact_path": row["fact_path"],
            "relation": row["relation"],
            "symbol": row["traditional_tendency"],
            "text": f"{stage_labels[row['role']]}{row['trigram']}({row['element']})对原体{row['body']}({row['body_element']})为{row['relation']}。",
        }
        for row in stages
    ]
    text = "".join(row["text"] for row in readings)
    if seasonal:
        body = next(row for row in seasonal["trigrams"] if row["role"] == "body")
        text += (
            f"节月{seasonal['month_branch']}({seasonal['season']})，"
            f"体卦{body['trigram']}季令为{body['strength']}。"
        )
    return readings, text


def build_meihua_evidence(
    meihua: dict[str, Any],
    *,
    lunar_year: int | None,
    is_leap_month: bool,
    timezone_name: str | None,
    month_branch: str | None,
    casting_trace: list[dict[str, Any]] | None = None,
    selected_ruleset: dict[str, Any] | None = None,
    calendar_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build compact structural Meihua evidence (<25 KB audit)."""
    stages = meihua_stage_relations(meihua)
    party_counts = compute_party_counts(meihua)
    profile = (
        dict(selected_ruleset) if selected_ruleset is not None else meihua_ruleset()
    )
    trace = list(casting_trace) if casting_trace is not None else []
    policy = (
        dict(calendar_policy)
        if calendar_policy is not None
        else {
            "lunar_year": lunar_year,
            "year_boundary": "lunar_new_year",
            "day_boundary": "local_midnight",
            "is_leap_month": is_leap_month,
            "timezone": timezone_name,
            "true_solar_time_applied": False,
        }
    )
    return {
        "ruleset_id": profile["id"],
        "version": profile["version"],
        "ruleset": profile,
        "calendar_policy": policy,
        "stage_relations": stages,
        "seasonal_strength": meihua_seasonal_strength(meihua, month_branch),
        "party_counts": party_counts,
    }


_CONTEXT_FIELDS = ("quiet_room", "nothing_heard", "nothing_seen")


def ensure_observation_method_context(
    method: object, context: dict[str, Any] | None
) -> None:
    """Reject explicitly conflicting observation declarations for the same cast."""
    if context is None:
        return
    if method == "sound_groups" and context.get("nothing_heard") is True:
        raise ValueError("sound_groups声明实际听闻，不能同时声明同次起卦无所闻")
    if method in {"observed_trigrams", "observed_categories"} and all(
        context.get(key) is True for key in _CONTEXT_FIELDS
    ):
        raise ValueError(
            "观物起卦声明外部物象，不能同时套用同次静室无所闻见的无外卦条件"
        )
