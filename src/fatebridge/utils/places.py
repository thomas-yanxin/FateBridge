"""Offline, source-attributed place coordinates shared by all transports.

The catalog contains representative city/admin points, not street geocoding.
Ambiguous names require a province, parent city, country or state qualifier.
See docs/place-catalog.md for coverage, sources and coordinate precision.
"""

from __future__ import annotations

import json
import logging
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)
DEFAULT_BIRTH_TIMEZONE = "Asia/Shanghai"
PLACE_SPECIFICITY = {
    "province": 1,
    "special_region": 2,
    "city": 3,
    "municipality": 3,
    "county": 4,
}
_DATA = Path(__file__).resolve().parents[1] / "data" / "places"


def _fold_text(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize(
            "NFKD", unicodedata.normalize("NFKC", text).casefold()
        )
        if not unicodedata.combining(c)
    )


def normalize_birth_place_text(text: str) -> str:
    """Fold case/Latin accents and punctuation without dropping other scripts."""
    return "".join(c for c in _fold_text(text) if c.isalnum())


def _load_entries() -> tuple[dict[str, Any], ...]:
    entries = []
    for filename in ("china.json", "world.json"):
        for row in json.loads((_DATA / filename).read_text(encoding="utf-8")):
            row["normalized_aliases"] = tuple(
                sorted(
                    {
                        normalize_birth_place_text(a)
                        for a in row["aliases"]
                        if normalize_birth_place_text(a)
                    }
                )
            )
            row["specificity"] = PLACE_SPECIFICITY[row["level"]]
            entries.append(row)
    return tuple(entries)


KNOWN_BIRTH_PLACE_ENTRIES = _load_entries()
_BY_ID = {r["id"]: r for r in KNOWN_BIRTH_PLACE_ENTRIES}
_COUNTRIES = json.loads((_DATA / "countries.json").read_text(encoding="utf-8"))
_MANIFEST = json.loads((_DATA / "manifest.json").read_text(encoding="utf-8"))
_ALIAS_INDEX: dict[str, list[str]] = defaultdict(list)
_CONTEXT_INDEX: dict[str, list[tuple[str, str]]] = defaultdict(list)
for _entry in KNOWN_BIRTH_PLACE_ENTRIES:
    for _alias in _entry["normalized_aliases"]:
        _ALIAS_INDEX[_alias].append(_entry["id"])
    for _alias in _entry.get("admin1_aliases", ()):
        _CONTEXT_INDEX[normalize_birth_place_text(_alias)].append(
            ("admin1", _entry["id"])
        )
for _country, _info in _COUNTRIES.items():
    for _alias in _info["aliases"]:
        _CONTEXT_INDEX[normalize_birth_place_text(_alias)].append(("country", _country))
_MAX_ALIAS_LENGTH = max(map(len, (*_ALIAS_INDEX, *_CONTEXT_INDEX)))
_PREFERRED: dict[str, str] = {}
for _name, _preferred_id in _MANIFEST["preferred_aliases"].items():
    if _preferred_id in _BY_ID:
        for _alias in _BY_ID[_preferred_id]["normalized_aliases"]:
            _PREFERRED[_alias] = _preferred_id


@dataclass(frozen=True)
class BirthPlaceResolution:
    """A resolved representative point, or empty coordinates for unknown names."""

    canonical_name: Optional[str]
    longitude: Optional[float]
    latitude: Optional[float]
    timezone: Optional[str]
    source: Optional[str]
    level: Optional[str]


@dataclass(frozen=True)
class _Match:
    key: str
    start: int
    end: int
    alias: str

    def overlaps(self, other: _Match) -> bool:
        return self.start < other.end and other.start < self.end


_EMPTY = BirthPlaceResolution(None, None, None, None, None, None)


def _matches(text: str) -> tuple[str, list[_Match], list[_Match]]:
    """Indexed lookup; Latin names must start/end at a word boundary.

    Retain positions in the folded input so removing spaces does not turn
    "Comparison" into a match for Paris or "Readington" into Reading.
    """
    folded = _fold_text(text)
    positions = [i for i, c in enumerate(folded) if c.isalnum()]
    normalized = "".join(folded[i] for i in positions)
    places: list[_Match] = []
    contexts: list[_Match] = []
    for start in range(len(normalized)):
        for end in range(
            start + 1, min(len(normalized), start + _MAX_ALIAS_LENGTH) + 1
        ):
            alias = normalized[start:end]
            if len(alias) == 1:
                continue
            ids, qualifiers = _ALIAS_INDEX.get(alias), _CONTEXT_INDEX.get(alias)
            if not ids and not qualifiers:
                continue
            raw_start, raw_end = positions[start], positions[end - 1] + 1
            # Do not match the middle of ANY alphabetic word. Chinese names can
            # be concatenated in an address, so their boundaries are hierarchical.
            if alias[0].isascii() and alias[0].isalnum() and raw_start > 0:
                previous = folded[raw_start - 1]
                if previous.isascii() and previous.isalnum():
                    continue
            if alias[-1].isascii() and alias[-1].isalnum() and raw_end < len(folded):
                following = folded[raw_end]
                if following.isascii() and following.isalnum():
                    continue
            places.extend(_Match(key, start, end, alias) for key in (ids or ()))
            # Two-letter ISO/state codes are qualifiers only when uppercase in
            # the original input; words such as "in" must not mean India.
            code = len(alias) <= 3 and alias.isascii() and alias.isalpha()
            if code:
                original = unicodedata.normalize("NFKC", text)
                if alias.upper() not in original:
                    continue
            contexts.extend(
                _Match(f"{kind}:{key}", start, end, alias)
                for kind, key in (qualifiers or ())
            )
    # Discard crossing aliases first: 台南市北区 contains 市北区, but the
    # Shandong name must not suppress the correct 北区 inside that suffix.
    places = [
        m
        for m in places
        if not any(
            n.start < m.start < n.end < m.end
            and _BY_ID[n.key]["level"] in {"province", "municipality", "city"}
            and n.key not in _ancestors(m.key)
            for n in places
        )
    ]
    # A complete name outranks a different name embedded inside it: 河北省 is
    # not 河北区, 连云港市 is not 连云区, 南投县 is not 南投市.
    places = [
        m
        for m in places
        if not any(
            n.start <= m.start and n.end >= m.end and n.end - n.start > m.end - m.start
            for n in places
        )
    ]
    return normalized, places, contexts


@lru_cache(maxsize=None)
def _ancestors(key: str) -> tuple[str, ...]:
    parent = _BY_ID[key]["parent"]
    if parent is None:
        return ()
    return (parent, *_ancestors(parent))


def _resolve(match: _Match) -> BirthPlaceResolution:
    entry = _BY_ID[match.key]
    return BirthPlaceResolution(
        entry["canonical_name"],
        entry["longitude"],
        entry["latitude"],
        entry["timezone"],
        "birth_place",
        entry["level"],
    )


def resolve_birth_place_context(birth_place: Optional[str]) -> BirthPlaceResolution:
    """Resolve a name/address locally; do not guess among unrelated namesakes."""
    if not birth_place or birth_place == "未提供":
        return _EMPTY
    return _resolve_birth_place_context_cached(birth_place.strip())


@lru_cache(maxsize=1024)
def _resolve_birth_place_context_cached(birth_place: str) -> BirthPlaceResolution:
    normalized, matches, contexts = _matches(birth_place)
    # An exact name is stronger than embedded shorter names (notably 长沙县
    # versus 长沙市). Qualifiers are applied below before legacy preferences.
    exact = [m for m in matches if m.start == 0 and m.end == len(normalized)]
    pool = exact or matches
    scored: list[tuple[tuple[int, int, int], _Match]] = []
    for match in pool:
        entry = _BY_ID[match.key]
        ancestors = _ancestors(match.key)
        if not exact:
            # Reject names crossing an earlier administrative name boundary:
            # 上海安亭 contains 海安, 黑龙江 contains 龙江, 河南开封 contains 南开.
            if any(
                m.start < match.start < m.end < match.end
                and _BY_ID[m.key]["level"] in {"province", "municipality", "city"}
                and m.key not in ancestors
                for m in matches
            ):
                continue
        country_hits = {
            m.key.split(":", 1)[1]
            for m in contexts
            if m.key.startswith("country:") and not match.overlaps(m)
        }
        # TW/HK/MO are GeoNames region qualifiers, represented in the China
        # catalog with their proper local civil timezone.
        region = (
            "TW"
            if entry["timezone"] == "Asia/Taipei"
            else (
                "HK"
                if entry["timezone"] == "Asia/Hong_Kong"
                else "MO" if entry["timezone"] == "Asia/Macau" else entry["country"]
            )
        )
        if country_hits and not ({entry["country"], region} & country_hits):
            continue
        if entry["country"] == "CN" and country_hits & {"TW", "HK", "MO"}:
            if region not in country_hits:
                continue
        parent_hits = {
            m.key for m in matches if m.key in ancestors and not match.overlaps(m)
        }
        if entry["country"] == "CN":
            anchors = [
                m
                for m in matches
                if not match.overlaps(m)
                and _BY_ID[m.key]["level"] in {"province", "municipality", "city"}
                and _BY_ID[m.key]["country"] == "CN"
            ]
            # A longer parent alias can contain a shorter unrelated one. Keep
            # the longest at each position, e.g. 广西 versus 西安 pinyin.
            anchors = [
                m
                for m in anchors
                if not any(
                    n.start <= m.start
                    and n.end >= m.end
                    and n.end - n.start > m.end - m.start
                    for n in anchors
                )
            ]
            if any(
                m.key not in ancestors
                and m.key != match.key
                and not any(n.key in ancestors and n.overlaps(m) for n in anchors)
                for m in anchors
            ):
                continue
        admin_hits = {
            m.alias
            for m in contexts
            if m.key == f"admin1:{match.key}" and not match.overlaps(m)
        }
        context_score = len(parent_hits) + bool(country_hits) + bool(admin_hits)
        score = (context_score, entry["specificity"], match.end - match.start)
        scored.append((score, match))
    if scored:
        preferred = _PREFERRED.get(normalized)
        context_best = max(s[0] for s, _ in scored)
        preferred_matches = [
            m for s, m in scored if m.key == preferred and s[0] == context_best
        ]
        if preferred_matches:
            return _resolve(preferred_matches[0])
        if exact:
            # Bare prefecture names (南昌/吉林) retain their city meaning; a
            # homonymous county requires 县/区 or a qualifying parent address.
            canonical = [
                (score, m)
                for score, m in scored
                if normalize_birth_place_text(_BY_ID[m.key]["canonical_name"])
                == normalized
            ]
            if canonical:
                scored = canonical
                cities = [
                    (s, m)
                    for s, m in scored
                    if _BY_ID[m.key]["level"]
                    in {"city", "municipality", "special_region"}
                ]
                if cities:
                    scored = cities
        best = max(s for s, _ in scored)
        winners = {m.key: m for s, m in scored if s == best}
        # Explicit context always wins over the few stable, established aliases
        # (London means the UK by default, but Canada/London resolves to Ontario).
        preferred = _PREFERRED.get(normalized)
        if preferred in winners:
            return _resolve(winners[preferred])
        if len(winners) == 1:
            return _resolve(next(iter(winners.values())))
        logger.warning(
            "出生地 %r 含同名地点，请补充省、市、国家或州名以确定坐标。", birth_place
        )
        return _EMPTY
    logger.warning(
        "出生地 %r 不在离线地名库中或与行政层级冲突，已跳过真太阳时经度校正"
        "（如需精确请显式传入经度）。",
        birth_place,
    )
    return _EMPTY
