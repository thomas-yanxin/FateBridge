"""Image-backed schedule clauses, separate from modern date-mapping choices."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fatebridge.core.canping_scope_rendering import (
    CURRENT_SCOPE_STATEMENT as SCOPE_STATEMENT,
)
from fatebridge.core.canping_scope_rendering import scope_rendering_receipt
from fatebridge.utils.errors import NumerologySourceError

COLLATION_PATH = (
    Path(__file__).resolve().parents[1] / "data/canping/schedule-basis-v1.json"
)
CONTENT_SHA256 = "c8da433b4ab29c86f044f05e06593ead40992b76612147b6f1d11b5a37ccccc4"
POLICY_ID = "canping_schedule_source_mapping_v1"
APPENDIX = "bazi_appendix_v1"
CONTINUOUS = "bazi_continuous_v1"
LEGACY = "legacy_minggong_v1"
APPLIED = {
    APPENDIX: ["appendix_month_order", "appendix_integer_rounding"],
    CONTINUOUS: ["appendix_month_order"],
    LEGACY: [],
}
SUMMARIES = MappingProxyType(
    {
        APPENDIX: (
            "本次用卷七月柱顺逆及三日整日借除；民用日差、周年、时区和半开区间"
            "是具名软件映射。十年步长另有《三命通会》书影支持，不冒称所核附段已明载。"
            "河洛卦运另为阳爻九年、阴爻六年。"
        ),
        CONTINUOUS: (
            "本次用月柱顺逆及现代连续折算，不执行卷七的整日借除；"
            "三日折岁和十年换运有子平文献背景，连续秒数及公历落点仍为具名软件映射。"
            "这不是河洛阳爻九年、阴爻六年卦运。"
        ),
        LEGACY: (
            "本次为继承的命宫顺排、一岁起运，仅保留年标签，没有已核实际日期映射。"
            "卷七附法及《三命通会》引文只作对照，不替此法认证原典依据；"
            "也不是已核河洛六九年卦运。"
        ),
    }
)
ROLE_LABELS = MappingProxyType(
    {
        "applied_rule": "本次采用的原句",
        "supplementary_ziping_background": "另书子平背景",
        "source_context": "来源语境",
        "comparison_not_applied": "对照而未采用",
    }
)


def clause_role(profile: str, clause: dict[str, Any]) -> str:
    """The role belongs to this profile, not just to the book containing it."""
    if clause["id"] in APPLIED[profile]:
        return "applied_rule"
    if clause["source_id"] == "sanming_nlc":
        return (
            "supplementary_ziping_background"
            if profile != LEGACY
            else "comparison_not_applied"
        )
    if profile == LEGACY:
        return "comparison_not_applied"
    if clause["kind"] in {"attribution", "method_distinction"}:
        return "source_context"
    return "comparison_not_applied"


def clock_policy_for_rules(rules: dict[str, Any]) -> str | None:
    """Do not infer a provider for a projected receipt that omits it."""
    database = rules.get("database")
    if database is None:
        return None
    if database == "explicit_fixed_offset":
        return "explicit_fixed_offset_assumption; no_regional_future_rules"
    if database == "pytz":
        return "pinned_regional_rules; subject_to_future_legislation"
    raise ValueError("参评时区规则提供方未登记。")


@lru_cache(maxsize=1)
def _collation() -> dict[str, Any]:
    try:
        raw = COLLATION_PATH.read_bytes()
        data: dict[str, Any] = json.loads(raw)
        digest = sha256(
            json.dumps(
                data,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        if digest != CONTENT_SHA256:
            raise ValueError("配运原句或来源身份与所核读法不符。")
    except (OSError, TypeError, ValueError) as exc:
        raise NumerologySourceError("invalid_canping_schedule_collation") from exc
    data["_file_sha256"] = sha256(raw).hexdigest()
    return data


def source_readings() -> dict[str, Any]:
    """Return detached readings so consumers cannot mutate a cached source."""
    return deepcopy(_collation())


def reading_source_citations(profile: str) -> list[dict[str, Any]]:
    """Join the registered book identity, examined pages and actual roles."""
    if profile not in APPLIED:
        raise ValueError("未登记的参评配运方法。")
    data = _collation()
    result = []
    for source_id, source in data["sources"].items():
        clauses = [c for c in data["clauses"] if c["source_id"] == source_id]
        result.append(
            {
                "source_id": source_id,
                **deepcopy(source),
                "pdf_pages": sorted({c["pdf_page"] for c in clauses}),
                "roles": list(dict.fromkeys(clause_role(profile, c) for c in clauses)),
            }
        )
    return result


def date_mapping_statement(
    profile: str, future_clock_policy: str | None, timezone_spec: str | None
) -> str:
    """Qualify mapped dates without inventing dates for the legacy profile."""
    if profile not in APPLIED:
        raise ValueError("未登记的参评配运方法。")
    if profile == LEGACY:
        return (
            "本次旧命宫方案仅有年龄标签，没有已核的实际起止日期；"
            "出生钟制记录不构成运期日期映射。"
        )
    if not isinstance(timezone_spec, str) or not timezone_spec.strip():
        raise ValueError("日期条件需要同次实际时区记录。")
    if (
        future_clock_policy
        == "explicit_fixed_offset_assumption; no_regional_future_rules"
    ):
        return (
            f"本次日期按显式固定偏移{timezone_spec}映射，仅在该固定偏移假设下成立；"
            "不表示当地未来法定时间已确认。"
        )
    if future_clock_policy == "pinned_regional_rules; subject_to_future_legislation":
        return (
            f"本次日期按封存的{timezone_spec}地区规则映射；涉及未来的落点受将来立法影响，"
            "不是已确认的未来当地法定时刻。"
        )
    raise ValueError("日期条件缺少已登记的同次钟制政策。")


def build_reading_context(
    profile: str, future_clock_policy: str, timezone_spec: str
) -> dict[str, Any]:
    """A local reading view of existing facts, not another schedule calculation."""
    return {
        "profile_id": profile,
        "future_clock_policy": future_clock_policy,
        "timezone_spec": timezone_spec,
        "date_mapping_statement": date_mapping_statement(
            profile, future_clock_policy, timezone_spec
        ),
        "source_citations": reading_source_citations(profile),
    }


def build_schedule_basis(profile: str, timing: dict, clock: dict) -> dict[str, Any]:
    """Bind a source map to the actual selected profile and clock policies.

    A supplementary Zi Ping book supports the decade background, but cannot
    certify that the target Heluo appendix printed the same explicit rule.
    The legacy profile must not inherit the appendix's source certification.
    """
    if profile not in APPLIED or timing.get("profile_id") != profile:
        raise NumerologySourceError("runtime_canping_schedule_profile_conflict")
    data = _collation()
    clauses = []
    for original in data["clauses"]:
        clause = deepcopy(original)
        clauses.append({**clause, "role": clause_role(profile, clause)})
    mapping = (
        {
            "calendar_policy": timing["calendar_policy"],
            "reference_policy": timing["reference_policy"],
            "boundary_policy": timing["boundary_policy"],
            "dst_policy": timing["dst_policy"],
        }
        if profile != LEGACY
        else {"calendar_policy": timing["calendar_scope"]}
    )
    try:
        clock_policy = clock_policy_for_rules(clock["timezone_rules"])
    except (TypeError, ValueError) as exc:
        raise NumerologySourceError(
            "runtime_canping_schedule_binding_conflict"
        ) from exc
    if clock_policy is None:
        raise NumerologySourceError("runtime_canping_schedule_binding_conflict")
    return {
        "policy_id": POLICY_ID,
        "profile_id": profile,
        "corpus_id": data["corpus_id"],
        "corpus_version": data["version"],
        "source_content_sha256": CONTENT_SHA256,
        "source_file_sha256": data["_file_sha256"],
        "review_status": data["review_status"],
        "sources": deepcopy(data["sources"]),
        "clauses": clauses,
        "applied_clause_ids": list(APPLIED[profile]),
        "bridge_step_years": 10,
        "target_excerpt_ten_year_step_explicitly_collated": False,
        "has_actual_date_mapping": profile != LEGACY,
        "datetime_mapping_is_original_source_formula": False,
        "calendar_mapping": mapping,
        "age_conversion_result": deepcopy(timing.get("calendar_offset")),
        "actual_start_at": timing.get("start_at"),
        "timezone_spec": clock["timezone_spec"],
        "timezone_rules": deepcopy(clock["timezone_rules"]),
        "future_clock_policy": clock_policy,
        "reading_context": build_reading_context(
            profile, clock_policy, clock["timezone_spec"]
        ),
        "summary": SUMMARIES[profile],
        "scope_statement": SCOPE_STATEMENT,
        "scope_rendering": scope_rendering_receipt(),
        "whole_book_alignment_established": False,
        "real_world_efficacy_validated": False,
    }


def attach_schedule_basis(evidence: dict, basis: dict) -> None:
    evidence["rule_trace"].append(
        {
            "rule_id": POLICY_ID,
            "source_section": "卷七附法原句、另书子平十年背景与本次软件日期映射",
            "facts": deepcopy(basis),
        }
    )


def schedule_basis_snapshot(basis: dict) -> str:
    lines = ["[配运原典与日期映射]", basis["summary"]]
    context = basis.get("reading_context")
    if context is not None:
        lines.append(context["date_mapping_statement"])
        for citation in context["source_citations"]:
            pages = "、".join(map(str, citation["pdf_pages"]))
            roles = "、".join(ROLE_LABELS[role] for role in citation["roles"])
            lines.append(
                f"出处：《{citation['title']}》；{citation['edition']}；"
                f"PDF第{pages}页；本次角色：{roles}。书影：{citation['url']}"
            )
    lines.append(basis["scope_statement"])
    return "\n".join(lines)
