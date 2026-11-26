"""Detect explicit restricted consultation requests without inspecting person names."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

POLICY_ID = "consultation_boundaries_v1"
BLOCKED_HORARY_CATEGORIES = frozenset({"death", "health", "pregnancy"})
BLOCKED_ELECTION_TOPICS = frozenset({"surgery"})

INTENT_FIELDS = frozenset({"question", "query", "topic", "intent"})
PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"寿命|寿元|死期|死亡|离世|去世|生死|阳寿|阴寿|致命|绝症|大限将至|寿终|夭折|短寿|延寿|续命",
        r"活(?:到|多久|不(?:过|到))|还能活|哪[年天日时].{0,8}死|什么时[候间].{0,8}死|会(?:不会|不)?死",
        r"几岁.{0,4}(?:死|走)|(?:父|母|爸|妈|亲人|家人).{0,6}还能陪.{0,8}多久",
        r"(?:哪[年天日时]|何时|什么时[候间]|几[年岁]|多久).{0,16}(?:白事|丧事|葬礼|出殡)",
        r"(?:白事|丧事|葬礼|出殡).{0,12}(?:哪[年天日时]|何时|什么时[候间]|几[年岁]|多久)",
        r"自杀|自伤|轻生|寻死|结束生命|不想活|跳楼|割腕",
        r"(?:算|预测|命盘|八字|星盘|占卜|卦).{0,12}(?:癌症|病情|患病|疾病|诊断|不孕|怀孕|流产)",
        r"(?:得|患|有|是什么|什么).{0,3}(?:癌|病)|(?:病|癌).{0,5}(?:能好|治好|治愈|会好)",
        r"(?:停药|换药|药方|处方|用药|治疗|手术).{0,12}(?:吉日|择日|择时|运势|何时|哪天|哪年|时机)",
        r"(?:哪天|何时|什么时[候间]).{0,8}(?:停药|换药|治疗|手术)",
        r"(?:适不适合|适合|吉不吉).{0,8}(?:手术|治疗)",
        r"(?:命盘|八字|星盘|占卜|预测|算).{0,8}(?:车祸|空难|大灾|灾祸|血光之灾)",
        r"(?:death|lifespan|lifeexpectancy|wheni(?:will)?die|whenwill.{0,20}die|howlong.{0,20}live)",
        r"will(?:i|he|she|they).{0,12}die|(?:date|time|age)ofdeath",
        r"suicid|selfharm|killmyself|endmylife|lethaldose",
        r"(?:predict|divin|astrolog|horoscop).{0,20}(?:illness|disease|cancer|pregnan|fertil|accident)",
        r"(?:surgery|treatment|medication).{0,16}(?:timing|auspicious|election)|(?:when|besttime).{0,16}(?:surgery|stopmedication)",
    )
)


def _normalize(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKC", value).casefold()
        if not char.isspace() and not unicodedata.category(char).startswith("C")
    )


def restricted_intent_path(data: Mapping[str, object]) -> str | None:
    """Find the path of an explicit restricted intent in a raw request."""
    category = data.get("category")
    topic = data.get("topic_id")
    if (
        "question_year" in data
        and isinstance(category, str)
        and _normalize(category) in BLOCKED_HORARY_CATEGORIES
    ):
        return "category"
    elif isinstance(topic, str) and _normalize(topic) in BLOCKED_ELECTION_TOPICS:
        return "topic_id"
    for field_name, submitted_value in data.items():
        if field_name in INTENT_FIELDS and isinstance(submitted_value, str):
            normalized_intent = _normalize(submitted_value)
            if any(pattern.search(normalized_intent) for pattern in PATTERNS):
                return field_name
        elif isinstance(submitted_value, Mapping):
            nested_path = restricted_intent_path(submitted_value)
            if nested_path:
                return f"{field_name}.{nested_path}"
    return None
