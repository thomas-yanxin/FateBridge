"""Deterministic scoring and item specification for the 50-item IPIP Big-Five Factor Markers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal, Mapping

from pydantic import Field, JsonValue, StrictInt, field_validator, model_validator
from pydantic_core import PydanticCustomError

from fatebridge.core.contracts.output_base import PartialOutput
from fatebridge.core.receipt_models import RunMetadata
from fatebridge.core.requests.base import FateBridgeBaseRequest
from fatebridge.core.response_models import ProjectedOutput

BigFiveDomain = Literal[
    "extraversion",
    "agreeableness",
    "conscientiousness",
    "emotional_stability",
    "intellect",
]
DomainStatus = Literal["complete", "prorated", "insufficient_items"]
ScaleStatus = Literal["complete", "partial", "insufficient_items"]
LikertScore = Annotated[StrictInt, Field(ge=1, le=5)]

SCALE_ID = "ipip_big_five_50"
METHOD_ID = "fatebridge.ipip_big_five_50.contract_v1"
ITEMS_PER_DOMAIN = 10
MIN_ANSWERED_PER_DOMAIN = 8
TOTAL_ITEMS = 50

DOMAIN_ORDER: tuple[BigFiveDomain, ...] = (
    "extraversion",
    "agreeableness",
    "conscientiousness",
    "emotional_stability",
    "intellect",
)

DOMAIN_METADATA: dict[BigFiveDomain, tuple[int, str, str]] = {
    "extraversion": (1, "Extraversion", "外向性"),
    "agreeableness": (2, "Agreeableness", "宜人性"),
    "conscientiousness": (3, "Conscientiousness", "尽责性"),
    "emotional_stability": (4, "Emotional Stability", "情绪稳定性"),
    "intellect": (5, "Intellect / Imagination", "智识/开放性"),
}

RESPONSE_ANCHORS: dict[str, str] = {
    "1": "Very Inaccurate",
    "2": "Moderately Inaccurate",
    "3": "Neither Inaccurate nor Accurate",
    "4": "Moderately Accurate",
    "5": "Very Accurate",
}


@dataclass(frozen=True)
class IpipItem:
    """One item from Goldberg (1992) IPIP 50-item Big-Five Factor Markers."""

    item_id: int
    domain: BigFiveDomain
    factor: int
    keying: Literal[1, -1]
    text: str
    gloss_zh: str


def _item(
    item_id: int,
    domain: BigFiveDomain,
    keying: Literal[1, -1],
    text: str,
    gloss_zh: str,
) -> IpipItem:
    return IpipItem(
        item_id=item_id,
        domain=domain,
        factor=DOMAIN_METADATA[domain][0],
        keying=keying,
        text=text,
        gloss_zh=gloss_zh,
    )


IPIP_BIG_FIVE_ITEMS: tuple[IpipItem, ...] = (
    _item(1, "extraversion", 1, "Am the life of the party.", "在聚会中能活跃气氛。"),
    _item(
        2, "agreeableness", -1, "Feel little concern for others.", "对他人较少关心。"
    ),
    _item(3, "conscientiousness", 1, "Am always prepared.", "总是事先做好准备。"),
    _item(4, "emotional_stability", -1, "Get stressed out easily.", "容易感到压力。"),
    _item(5, "intellect", 1, "Have a rich vocabulary.", "词汇量丰富。"),
    _item(6, "extraversion", -1, "Don't talk a lot.", "话不多。"),
    _item(7, "agreeableness", 1, "Am interested in people.", "对他人感兴趣。"),
    _item(8, "conscientiousness", -1, "Leave my belongings around.", "东西随手乱放。"),
    _item(
        9,
        "emotional_stability",
        1,
        "Am relaxed most of the time.",
        "大多数时候都很放松。",
    ),
    _item(
        10,
        "intellect",
        -1,
        "Have difficulty understanding abstract ideas.",
        "理解抽象概念有困难。",
    ),
    _item(
        11, "extraversion", 1, "Feel comfortable around people.", "在人群中感到自在。"
    ),
    _item(12, "agreeableness", -1, "Insult people.", "会冒犯或侮辱他人。"),
    _item(13, "conscientiousness", 1, "Pay attention to details.", "注重细节。"),
    _item(14, "emotional_stability", -1, "Worry about things.", "常常忧虑事情。"),
    _item(15, "intellect", 1, "Have a vivid imagination.", "想象力丰富生动。"),
    _item(16, "extraversion", -1, "Keep in the background.", "习惯退居幕后。"),
    _item(
        17,
        "agreeableness",
        1,
        "Sympathize with others' feelings.",
        "能体察并同情他人感受。",
    ),
    _item(
        18, "conscientiousness", -1, "Make a mess of things.", "常把事情弄得一团糟。"
    ),
    _item(19, "emotional_stability", 1, "Seldom feel blue.", "很少感到忧郁。"),
    _item(
        20,
        "intellect",
        -1,
        "Am not interested in abstract ideas.",
        "对抽象概念不感兴趣。",
    ),
    _item(21, "extraversion", 1, "Start conversations.", "会主动开启对话。"),
    _item(
        22,
        "agreeableness",
        -1,
        "Am not interested in other people's problems.",
        "对他人的困扰不感兴趣。",
    ),
    _item(
        23,
        "conscientiousness",
        1,
        "Get chores done right away.",
        "琐事会立刻动手做完。",
    ),
    _item(24, "emotional_stability", -1, "Am easily disturbed.", "容易心神不宁。"),
    _item(25, "intellect", 1, "Have excellent ideas.", "常有很好的点子。"),
    _item(26, "extraversion", -1, "Have little to say.", "没什么话可说。"),
    _item(27, "agreeableness", 1, "Have a soft heart.", "心肠柔软、富有恻隐之心。"),
    _item(
        28,
        "conscientiousness",
        -1,
        "Often forget to put things back in their proper place.",
        "常忘记把东西放回原位。",
    ),
    _item(29, "emotional_stability", -1, "Get upset easily.", "容易心烦或沮丧。"),
    _item(30, "intellect", -1, "Do not have a good imagination.", "缺乏良好的想象力。"),
    _item(
        31,
        "extraversion",
        1,
        "Talk to a lot of different people at parties.",
        "在聚会上会和许多不同的人交谈。",
    ),
    _item(
        32,
        "agreeableness",
        -1,
        "Am not really interested in others.",
        "对他人其实不太感兴趣。",
    ),
    _item(33, "conscientiousness", 1, "Like order.", "喜欢有条理、讲求秩序。"),
    _item(34, "emotional_stability", -1, "Change my mood a lot.", "情绪起伏很大。"),
    _item(35, "intellect", 1, "Am quick to understand things.", "理解事物很快。"),
    _item(
        36,
        "extraversion",
        -1,
        "Don't like to draw attention to myself.",
        "不喜欢引人注意。",
    ),
    _item(
        37,
        "agreeableness",
        1,
        "Take time out for others.",
        "愿意花时间照顾或帮助他人。",
    ),
    _item(38, "conscientiousness", -1, "Shirk my duties.", "会逃避自己的职责。"),
    _item(
        39,
        "emotional_stability",
        -1,
        "Have frequent mood swings.",
        "经常出现情绪波动。",
    ),
    _item(40, "intellect", 1, "Use difficult words.", "会使用较生僻或高深的词汇。"),
    _item(
        41,
        "extraversion",
        1,
        "Don't mind being the center of attention.",
        "不介意成为众人关注的焦点。",
    ),
    _item(42, "agreeableness", 1, "Feel others' emotions.", "能感受到他人的情绪。"),
    _item(43, "conscientiousness", 1, "Follow a schedule.", "按计划表或日程行事。"),
    _item(44, "emotional_stability", -1, "Get irritated easily.", "容易烦躁或生气。"),
    _item(45, "intellect", 1, "Spend time reflecting on things.", "会花时间反思事物。"),
    _item(
        46, "extraversion", -1, "Am quiet around strangers.", "在陌生人面前比较沉默。"
    ),
    _item(47, "agreeableness", 1, "Make people feel at ease.", "能让人感到轻松自在。"),
    _item(
        48,
        "conscientiousness",
        1,
        "Am exacting in my work.",
        "做事严谨、对自己要求高。",
    ),
    _item(49, "emotional_stability", -1, "Often feel blue.", "经常感到忧郁低落。"),
    _item(50, "intellect", 1, "Am full of ideas.", "点子很多、思维活跃。"),
)

ITEMS_BY_ID: dict[int, IpipItem] = {item.item_id: item for item in IPIP_BIG_FIVE_ITEMS}
ITEMS_BY_DOMAIN: dict[BigFiveDomain, tuple[IpipItem, ...]] = {
    domain: tuple(item for item in IPIP_BIG_FIVE_ITEMS if item.domain == domain)
    for domain in DOMAIN_ORDER
}


def scale_provenance() -> dict[str, JsonValue]:
    """Return authoritative public-domain provenance for IPIP Big-Five 50."""
    return {
        "method_id": METHOD_ID,
        "scale_id": SCALE_ID,
        "scale_name": "IPIP Big-Five Factor Markers (50-item)",
        "scale_name_zh": "IPIP 50题大五人格因子标记量表",
        "author": "Lewis R. Goldberg (1992)",
        "license": "Public Domain",
        "domains": {
            domain: {
                "factor": DOMAIN_METADATA[domain][0],
                "name": DOMAIN_METADATA[domain][1],
                "label_zh": DOMAIN_METADATA[domain][2],
            }
            for domain in DOMAIN_ORDER
        },
        "response_scale": dict(RESPONSE_ANCHORS),
        "reverse_scoring_rule": "6 - raw_score for keying=-1",
        "missing_item_policy": "prorate_domain_mean_if_answered_ge_8_else_insufficient_items",
        "min_answered_per_domain": MIN_ANSWERED_PER_DOMAIN,
        "items_per_domain": ITEMS_PER_DOMAIN,
        "total_items": TOTAL_ITEMS,
    }


def _parse_item_id(key: object) -> int | None:
    if isinstance(key, bool):
        return None
    if isinstance(key, int):
        return key if 1 <= key <= TOTAL_ITEMS else None
    if isinstance(key, str) and key.isascii() and key.isdigit():
        item_id = int(key)
        if 1 <= item_id <= TOTAL_ITEMS and str(item_id) == key:
            return item_id
    return None


class IpipBigFiveRequest(FateBridgeBaseRequest):
    """Shared request contract for administering or scoring IPIP Big-Five 50."""

    action: Literal["score", "list_items"] = Field(
        default="score",
        description=(
            "操作模式：list_items 列出50道标准IPIP题项与计分方向；"
            "score 对1-5分整数作答进行确定性正反向计分。"
        ),
    )
    responses: dict[str, LikertScore | None] | None = Field(
        default=None,
        description=(
            "按题号（'1'..'50'）映射的1-5分整数作答（JSON对象，CLI支持 --responses '{\"1\":5,...}'）；"
            "缺题可省略或设为 null，不可与 ratings 同时提供。"
        ),
    )
    ratings: list[LikertScore | None] | None = Field(
        default=None,
        min_length=1,
        max_length=TOTAL_ITEMS,
        description=(
            "按第1..50题顺序提交的1-5分整数列表（CLI支持 --ratings 5 1 4 ...）；"
            "缺题可设为 null，不可与 responses 同时提供。"
        ),
    )
    domain: BigFiveDomain | None = Field(
        default=None,
        description=(
            "仅在 action=list_items 时可选筛选单个维度："
            "extraversion / agreeableness / conscientiousness / emotional_stability / intellect。"
        ),
    )
    include_item_breakdown: bool = Field(
        default=False,
        description="仅在 action=score 时为 true 返回逐题原始分、计分键与折算后分值明细。",
    )

    @field_validator("responses", mode="before")
    @classmethod
    def _normalize_response_keys(cls, value: object) -> object:
        if value is None or not isinstance(value, dict):
            return value
        normalized: dict[str, object] = {}
        for raw_key, raw_score in value.items():
            item_id = _parse_item_id(raw_key)
            if item_id is None:
                raise PydanticCustomError(
                    "invalid_item_id",
                    "题号必须为 '1' 到 '50' 的规范整数：{item_key}",
                    {"item_key": str(raw_key), "path": "responses"},
                )
            canonical_key = str(item_id)
            if canonical_key in normalized:
                raise PydanticCustomError(
                    "duplicate_item_id",
                    "存在重复题号：{item_id}",
                    {"item_id": item_id, "path": "responses"},
                )
            normalized[canonical_key] = raw_score
        return normalized

    def _answered_map(self) -> dict[int, int]:
        if self.responses is not None:
            return {
                int(key): score
                for key, score in self.responses.items()
                if score is not None
            }
        if self.ratings is not None:
            return {
                index + 1: score
                for index, score in enumerate(self.ratings)
                if score is not None
            }
        return {}

    @model_validator(mode="after")
    def _validate_mode_inputs(self) -> "IpipBigFiveRequest":
        if self.action == "list_items":
            if self.responses is not None or self.ratings is not None:
                raise PydanticCustomError(
                    "invalid_mode_parameters",
                    "action=list_items 时不应提供 responses 或 ratings",
                    {"path": "responses" if self.responses is not None else "ratings"},
                )
            return self
        if self.domain is not None:
            raise PydanticCustomError(
                "invalid_mode_parameters",
                "action=score 时不支持 domain 筛选参数",
                {"path": "domain"},
            )
        if self.responses is not None and self.ratings is not None:
            raise PydanticCustomError(
                "conflicting_inputs",
                "responses 与 ratings 不能同时提供，请二选一",
                {"path": "ratings"},
            )
        if self.responses is None and self.ratings is None:
            raise PydanticCustomError(
                "missing_responses",
                "action=score 时必须提供 responses 或 ratings",
                {"path": "responses"},
            )
        if not self._answered_map():
            raise PydanticCustomError(
                "empty_responses",
                "至少需要提供 1 道有效（1-5 整数）作答",
                {"path": "responses" if self.responses is not None else "ratings"},
            )
        return self

    def service_inputs(self) -> dict[str, str | bool | dict[int, int] | None]:
        if self.action == "list_items":
            return {"action": "list_items", "domain": self.domain}
        return {
            "action": "score",
            "answers": self._answered_map(),
            "include_item_breakdown": self.include_item_breakdown,
        }


class IpipScaleProvenance(PartialOutput):
    method_id: str | None = None
    scale_id: str | None = None
    scale_name: str | None = None
    scale_name_zh: str | None = None
    author: str | None = None
    license: str | None = None
    scale_url: str | None = None
    scoring_url: str | None = None
    domains: dict[str, dict[str, JsonValue]] | None = None
    response_scale: dict[str, str] | None = None
    reverse_scoring_rule: str | None = None
    missing_item_policy: str | None = None
    min_answered_per_domain: int | None = None
    items_per_domain: int | None = None
    total_items: int | None = None


class IpipItemDefinitionOutput(PartialOutput):
    item_id: int
    domain: BigFiveDomain
    keying: Literal[1, -1]
    text: str
    gloss_zh: str


class IpipDomainScoreOutput(PartialOutput):
    domain: BigFiveDomain | None = None
    domain_label_zh: str | None = None
    factor: int | None = None
    status: DomainStatus | None = None
    answered_count: int | None = None
    missing_count: int | None = None
    total_items: int | None = None
    missing_item_ids: list[int] | None = None
    raw_sum: int | None = None
    prorated_sum: float | None = None
    mean: float | None = None


class IpipItemBreakdownOutput(PartialOutput):
    item_id: int
    domain: BigFiveDomain
    keying: Literal[1, -1]
    raw_score: int | None = None
    scored_value: int | None = None
    status: Literal["answered", "missing"]


class IpipBigFiveOutput(ProjectedOutput):
    run_metadata: RunMetadata | None = None
    mode: Literal["score", "list_items"] | None = None
    scale_id: str | None = None
    status: ScaleStatus | None = None
    domain_filter: BigFiveDomain | None = None
    item_count: int | None = None
    items: list[IpipItemDefinitionOutput] | None = None
    answered_count: int | None = None
    missing_count: int | None = None
    total_items: int | None = None
    scale_raw_sum: int | None = None
    scale_mean: float | None = None
    domains: dict[str, IpipDomainScoreOutput] | None = None
    item_breakdown: list[IpipItemBreakdownOutput] | None = None
    provenance: IpipScaleProvenance | None = None
    summary: str | None = None


def list_ipip_big_five_items(
    domain: BigFiveDomain | None = None,
) -> dict[str, JsonValue]:
    """Return the 50-item IPIP Big-Five questionnaire (or one domain subset)."""
    selected = ITEMS_BY_DOMAIN[domain] if domain is not None else IPIP_BIG_FIVE_ITEMS
    items: list[JsonValue] = [
        {
            "item_id": item.item_id,
            "domain": item.domain,
            "keying": item.keying,
            "text": item.text,
            "gloss_zh": item.gloss_zh,
        }
        for item in selected
    ]
    scope = (
        f"维度 {domain}（{DOMAIN_METADATA[domain][2]}）{len(items)} 题"
        if domain is not None
        else f"全部 {len(items)} 题（每因子 10 题）"
    )
    return {
        "mode": "list_items",
        "scale_id": SCALE_ID,
        **({"domain_filter": domain} if domain is not None else {}),
        "item_count": len(items),
        "items": items,
        "provenance": scale_provenance(),
        "summary": f"IPIP 50题大五人格因子标记量表条目清单：{scope}，作答刻度 1-5 整数。",
    }


def score_ipip_big_five(
    answers: Mapping[int, int],
    *,
    include_item_breakdown: bool = False,
) -> dict[str, JsonValue]:
    """Deterministically score validated 1..5 item responses for IPIP Big-Five 50."""
    for item_id, raw_score in answers.items():
        if isinstance(item_id, bool) or item_id not in ITEMS_BY_ID:
            raise ValueError(f"无效题号：{item_id}（必须为 1–50 整数）")
        if (
            isinstance(raw_score, bool)
            or not isinstance(raw_score, int)
            or not (1 <= raw_score <= 5)
        ):
            raise ValueError(f"第 {item_id} 题作答无效：{raw_score}（必须为 1–5 整数）")

    breakdown: list[JsonValue] = []
    domain_raw_sums: dict[BigFiveDomain, int] = {d: 0 for d in DOMAIN_ORDER}
    domain_answered_counts: dict[BigFiveDomain, int] = {d: 0 for d in DOMAIN_ORDER}
    domain_missing_ids: dict[BigFiveDomain, list[int]] = {d: [] for d in DOMAIN_ORDER}

    for item in IPIP_BIG_FIVE_ITEMS:
        submitted_score = answers.get(item.item_id)
        if submitted_score is None:
            domain_missing_ids[item.domain].append(item.item_id)
            if include_item_breakdown:
                breakdown.append(
                    {
                        "item_id": item.item_id,
                        "domain": item.domain,
                        "keying": item.keying,
                        "raw_score": None,
                        "scored_value": None,
                        "status": "missing",
                    }
                )
            continue
        scored_value = submitted_score if item.keying == 1 else 6 - submitted_score
        domain_raw_sums[item.domain] += scored_value
        domain_answered_counts[item.domain] += 1
        if include_item_breakdown:
            breakdown.append(
                {
                    "item_id": item.item_id,
                    "domain": item.domain,
                    "keying": item.keying,
                    "raw_score": submitted_score,
                    "scored_value": scored_value,
                    "status": "answered",
                }
            )

    domains_payload: dict[str, JsonValue] = {}
    domain_parts: list[str] = []
    insufficient_domains = 0
    for domain in DOMAIN_ORDER:
        factor, _name_en, label_zh = DOMAIN_METADATA[domain]
        answered = domain_answered_counts[domain]
        missing_ids: list[JsonValue] = list(domain_missing_ids[domain])
        missing = len(missing_ids)
        raw_sum = domain_raw_sums[domain]
        if answered == ITEMS_PER_DOMAIN:
            status: DomainStatus = "complete"
            mean: float | None = float(round(raw_sum / answered, 4))
            prorated_sum: float | None = float(raw_sum)
        elif answered >= MIN_ANSWERED_PER_DOMAIN:
            status = "prorated"
            mean = float(round(raw_sum / answered, 4))
            prorated_sum = float(round(raw_sum * ITEMS_PER_DOMAIN / answered, 4))
        else:
            status = "insufficient_items"
            mean = None
            prorated_sum = None
            insufficient_domains += 1
        domains_payload[domain] = {
            "domain": domain,
            "domain_label_zh": label_zh,
            "factor": factor,
            "status": status,
            "answered_count": answered,
            "missing_count": missing,
            "total_items": ITEMS_PER_DOMAIN,
            "missing_item_ids": missing_ids,
            "raw_sum": raw_sum,
            "prorated_sum": prorated_sum,
            "mean": mean,
        }
        domain_parts.append(
            f"{label_zh}={mean}"
            if mean is not None
            else f"{label_zh}=insufficient_items({answered}/10)"
        )

    total_answered = sum(domain_answered_counts.values())
    total_missing = TOTAL_ITEMS - total_answered
    scale_raw_sum = sum(domain_raw_sums.values())
    scale_mean: float | None = (
        float(round(scale_raw_sum / total_answered, 4)) if total_answered > 0 else None
    )
    if total_answered == TOTAL_ITEMS:
        overall_status: ScaleStatus = "complete"
    elif insufficient_domains == len(DOMAIN_ORDER):
        overall_status = "insufficient_items"
    else:
        overall_status = "partial"

    summary = (
        f"IPIP-50 计分（{overall_status}，作答 {total_answered}/{TOTAL_ITEMS} 题，"
        f"总量表原始分 {scale_raw_sum}，作答均分 {scale_mean}）："
        + "；".join(domain_parts)
        + "。"
    )
    result: dict[str, JsonValue] = {
        "mode": "score",
        "scale_id": SCALE_ID,
        "status": overall_status,
        "answered_count": total_answered,
        "missing_count": total_missing,
        "total_items": TOTAL_ITEMS,
        "scale_raw_sum": scale_raw_sum,
        "scale_mean": scale_mean,
        "domains": domains_payload,
        "provenance": scale_provenance(),
        "summary": summary,
    }
    if include_item_breakdown:
        result["item_breakdown"] = breakdown
    return result
