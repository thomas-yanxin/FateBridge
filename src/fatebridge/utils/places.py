"""Offline, source-attributed place coordinates shared by all transports.

The catalog contains representative city/admin points, not street geocoding.
Ambiguous names require a province, parent city, country or state qualifier.
See docs/place-catalog.md for coverage, sources and coordinate precision.
"""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from fatebridge.utils.coordinates import parse_geo_coordinate
from fatebridge.utils.errors import ParameterError
from fatebridge.utils.place_catalog import PLACE_SPECIFICITY as PLACE_SPECIFICITY
from fatebridge.utils.place_catalog import (
    PlaceEntry,
    SqlitePlaceIndex,
    fold_place_text,
    get_place_index,
)
from fatebridge.utils.place_catalog import (
    normalize_birth_place_text as normalize_birth_place_text,
)

DEFAULT_BIRTH_TIMEZONE = "Asia/Shanghai"
DEFAULT_COORDINATE_LATITUDE = 31.2167
DEFAULT_COORDINATE_LONGITUDE = 121.4667


def resolve_coordinates(
    *,
    lat: object = None,
    lon: object = None,
    gps_lat: float | None = None,
    gps_lon: float | None = None,
) -> tuple[float, float]:
    latitude = parse_geo_coordinate(
        gps_lat if gps_lat is not None else lat, axis="latitude"
    )
    longitude = parse_geo_coordinate(
        gps_lon if gps_lon is not None else lon, axis="longitude"
    )
    return (
        DEFAULT_COORDINATE_LATITUDE if latitude is None else latitude,
        DEFAULT_COORDINATE_LONGITUDE if longitude is None else longitude,
    )


# UPU United Kingdom addressing guide (11/2011), p. 2: Square and Walk
# occur as thoroughfare fields before the post town.
UK_STREET_ENDING = re.compile(
    r"\S\s+(?:road|street|way|avenue|drive|lane|close|square|walk)\.?$"
)
# Royal Mail PAF Programmer's Guide, ed. 7 v. 6: PO Box is a separate
# delivery field, with a number that may include letters.
UK_PO_BOX = re.compile(r"p\.?o\.?\s+box\s+(?=[a-z0-9]*[0-9])[a-z0-9]{1,6}")
# UPU United Kingdom addressing guide (11/2011), pp. 1 and 3–4. A postal
# area can identify a jurisdiction, but does not validate a delivery point.
UK_POSTCODE = re.compile(r"([a-z]{1,2})[0-9][0-9a-z]?\s+[0-9][a-z]{2}|gir\s+0aa")
GB_POSTCODE_AREAS = frozenset(
    (
        "ab al b ba bb bd bh bl bn br bs bt ca cb cf ch cm co cr ct cv cw da dd "
        "de dg dh dl dn dt dy e ec eh en ex fk fy g gl gu ha hd hg hp hr hs hu hx "
        "ig ip iv ka kt kw ky l la ld le ll ln ls lu m me mk ml n ne ng nn np nr "
        "nw ol ox pa pe ph pl po pr rg rh rm s sa se sg sk sl sm sn so sp sr ss "
        "st sw sy ta td tf tn tq tr ts tw ub w wa wc wd wf wn wr ws wv yo ze"
    ).split()
)
CROWN_DEPENDENCY_POSTCODE_AREAS = {"gy": "GG", "im": "IM", "je": "JE"}


@dataclass(frozen=True)
class BirthPlaceResolution:
    """A resolved representative point, or empty coordinates for unknown names."""

    canonical_name: str | None
    longitude: float | None
    latitude: float | None
    timezone: str | None
    source: str | None
    level: str | None


@dataclass(frozen=True)
class _Match:
    key: str
    start: int
    end: int
    alias: str

    def overlaps(self, other: _Match) -> bool:
        return self.start < other.end and other.start < self.end


EMPTY = BirthPlaceResolution(None, None, None, None, None, None)


def _is_place_word_char(character: str) -> bool:
    return character.islower() or character.isupper() or character.isdecimal()


def _uk_postal_address_matches(
    components: dict[tuple[int, int], str],
    places: list[_Match],
    contexts: list[_Match],
) -> tuple[list[_Match], list[_Match]] | None:
    """Scope aliases to complete fields in a recognized UPU UK postal address."""
    street = next(
        (span for span, text in components.items() if UK_STREET_ENDING.search(text)),
        None,
    )
    if street is None:
        boxes = [span for span, text in components.items() if UK_PO_BOX.fullmatch(text)]
        if len(boxes) != 1:
            return None
        address_end = boxes[0][1]
    else:
        address_end = street[1]
    postcode = None
    postal_country = None
    for span, text in components.items():
        if span[0] < address_end:
            continue
        match = UK_POSTCODE.fullmatch(text)
        if match is None:
            continue
        area = match[1]
        if area is None or area in GB_POSTCODE_AREAS:
            postal_country = "GB"
        else:
            postal_country = CROWN_DEPENDENCY_POSTCODE_AREAS.get(area)
        if postal_country is not None:
            postcode = span
            break
    if street is None:
        if postcode is None or any(
            span != postcode and UK_POSTCODE.fullmatch(text)
            for span, text in components.items()
        ):
            return None
        town = next(span for span in reversed(components) if span[1] <= postcode[0])
        named_places = {
            (match.start, match.end) for match in places
        } & components.keys()
        named_qualifiers = {(match.start, match.end) for match in contexts}
        # Only the full field immediately before the postcode can provide a
        # point here. Preserve complete qualifiers for the resolver to check.
        if (
            town[0] < address_end
            or named_places != {town}
            or any(
                span[0] >= postcode[1] and span not in named_qualifiers
                for span in components
            )
        ):
            return None
        address_end = town[0]
    elif postcode is None and not any(
        context.key == "country:GB" and (context.start, context.end) in components
        for context in contexts
    ):
        return None
    places = [
        match
        for match in places
        if match.start >= address_end
        and (postcode is None or match.end <= postcode[0])
        and (match.start, match.end) in components
    ]
    contexts = [
        match
        for match in contexts
        if (match.start, match.end) in components
        and (
            street is None
            or match.start >= address_end
            or match.key.startswith("country:")
        )
    ]
    if postcode is not None:
        contexts.append(
            _Match(
                f"country:{postal_country}",
                *postcode,
                normalize_birth_place_text(components[postcode]),
            )
        )
    return places, contexts


def _matches(
    text: str,
) -> tuple[str, list[_Match], list[_Match], dict[tuple[int, int], set[str]]]:
    """Indexed lookup with word boundaries for cased letters and digits.

    Retain positions in the folded input so removing spaces does not turn
    "Comparison" into a match for Paris or "Readington" into Reading.
    """
    original = unicodedata.normalize("NFKC", text)
    folded = fold_place_text(original)
    uppercase_code_spans = set()
    for code in re.finditer(r"(?<![A-Za-z0-9])[A-Z]{2,3}(?![A-Za-z0-9])", original):
        start = len(fold_place_text(original[: code.start()]))
        uppercase_code_spans.add((start, start + len(code[0])))
    positions = [i for i, c in enumerate(folded) if c.isalnum()]
    normalized = "".join(folded[i] for i in positions)
    index = get_place_index()
    max_len = index.max_alias_length
    spans: list[tuple[int, int, str]] = []
    candidate_aliases: list[str] = []
    for start in range(len(normalized)):
        for end in range(start + 2, min(len(normalized), start + max_len) + 1):
            alias = normalized[start:end]
            spans.append((start, end, alias))
            candidate_aliases.append(alias)
    alias_hits = index.lookup_aliases(candidate_aliases)
    context_hits = index.lookup_contexts(candidate_aliases)

    places: list[_Match] = []
    contexts: list[_Match] = []
    comma_candidates: list[tuple[int, int, str, str]] = []
    for start, end, alias in spans:
        ids, qualifiers = alias_hits.get(alias), context_hits.get(alias)
        if not ids and not qualifiers:
            continue
        raw_start, raw_end = positions[start], positions[end - 1] + 1
        # Cased city names need a token edge. Uncased Chinese names may
        # be concatenated, with the resolver checking their hierarchy.
        if (
            raw_start > 0
            and _is_place_word_char(alias[0])
            and _is_place_word_char(folded[raw_start - 1])
        ):
            continue
        if (
            raw_end < len(folded)
            and _is_place_word_char(alias[-1])
            and _is_place_word_char(folded[raw_end])
        ):
            continue
        places.extend(_Match(key, start, end, alias) for key in (ids or ()))
        # Two-letter ISO/state codes are qualifiers only when uppercase in
        # the original input; words such as "in" must not mean India.
        short_code = len(alias) <= 3 and alias.isascii() and alias.isalpha()
        if short_code and (raw_start, raw_end) not in uppercase_code_spans:
            continue
        if qualifiers and "," in folded[raw_start:raw_end]:
            signature = "".join(
                c for c in folded[raw_start:raw_end] if c.isalnum() or c == ","
            )
            comma_candidates.append((start, end, alias, signature))
        else:
            contexts.extend(
                _Match(f"{kind}:{key}", start, end, alias)
                for kind, key in (qualifiers or ())
            )
    if comma_candidates:
        comma_hits = index.lookup_context_commas(
            [sig for _, _, _, sig in comma_candidates]
        )
        for start, end, alias, signature in comma_candidates:
            contexts.extend(
                _Match(f"{kind}:{key}", start, end, alias)
                for kind, key in (comma_hits.get(signature) or ())
            )
    components = {
        (bisect_left(positions, part.start()), bisect_left(positions, part.end())): (
            part[0].strip()
        )
        for part in re.finditer(r"[^,\r\n]+", folded)
        if part[0].strip()
    }
    postal = _uk_postal_address_matches(components, places, contexts)
    if postal is not None:
        places, contexts = postal
    place_by_id = index.get_places([m.key for m in places])
    # Discard crossing aliases first: 台南市北区 contains 市北区, but the
    # Shandong name must not suppress the correct 北区 inside that suffix.
    places = [
        m
        for m in places
        if not any(
            n.start < m.start < n.end < m.end
            and place_by_id[n.key]["level"] in {"province", "municipality", "city"}
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
    # In compact lists of complete directory names or qualifiers, every
    # named place field needs an owner. Postal layouts already assign roles
    # to their fields, and other free text may have unnamed address parts.
    place_fields: dict[tuple[int, int], set[str]] = defaultdict(set)
    if postal is None and len(components) > 1:
        for match in places:
            span = (match.start, match.end)
            if span in components:
                place_fields[span].add(match.key)
        if not components.keys() <= (
            place_fields.keys() | {(context.start, context.end) for context in contexts}
        ):
            place_fields.clear()
    return normalized, places, contexts, place_fields


@lru_cache(maxsize=None)
def _ancestors(key: str) -> tuple[str, ...]:
    entry = get_place_index().get_place(key)
    parent = entry["parent"] if entry is not None else None
    if parent is None:
        return ()
    return (parent, *_ancestors(parent))


def _resolve(match: _Match) -> BirthPlaceResolution:
    entry = get_place_index().get_place(match.key)
    assert entry is not None
    return BirthPlaceResolution(
        entry["canonical_name"],
        entry["longitude"],
        entry["latitude"],
        entry["timezone"],
        "birth_place",
        entry["level"],
    )


def resolve_birth_place_context(birth_place: str | None) -> BirthPlaceResolution:
    """Resolve a name/address locally; do not guess among unrelated namesakes."""
    if not birth_place or birth_place == "未提供":
        return EMPTY
    return _resolve_birth_place_context_cached(birth_place.strip())


@lru_cache(maxsize=1024)
def _resolve_birth_place_context_cached(birth_place: str) -> BirthPlaceResolution:
    normalized, matches, contexts, place_fields = _matches(birth_place)
    # An exact name is stronger than embedded shorter names (notably 长沙县
    # versus 长沙市). Qualifiers are applied below before legacy preferences.
    exact = [m for m in matches if m.start == 0 and m.end == len(normalized)]
    pool = exact or matches
    qualifier_options: dict[tuple[int, int], set[str]] = defaultdict(set)
    numeric_contexts = []
    for context in contexts:
        if context.alias.isdecimal():
            numeric_contexts.append(context)
        else:
            qualifier_options[context.start, context.end].add(context.key)
    # One span can name several jurisdictions (CA = Canada or California).
    # A contained short alias is part of the longer qualifier at that position.
    qualifiers = [
        (start, end, options)
        for (start, end), options in qualifier_options.items()
        if not any(
            outer_start <= start
            and end <= outer_end
            and (outer_start, outer_end) != (start, end)
            for outer_start, outer_end in qualifier_options
        )
    ]
    index = get_place_index()
    place_by_id = index.get_places([m.key for m in matches])
    scored: list[tuple[tuple[int, int, int], _Match]] = []
    for match in pool:
        entry = place_by_id[match.key]
        ancestors = _ancestors(match.key)
        if not exact:
            # Reject names crossing an earlier administrative name boundary:
            # 上海安亭 contains 海安, 黑龙江 contains 龙江, 河南开封 contains 南开.
            if any(
                m.start < match.start < m.end < match.end
                and place_by_id[m.key]["level"] in {"province", "municipality", "city"}
                and m.key not in ancestors
                for m in matches
            ):
                continue
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
        jurisdiction_keys = {
            f"country:{entry['country']}",
            f"country:{region}",
            f"admin1:{match.key}",
        }
        if len(place_fields) > 1:
            owners = {match.key, *ancestors}
            if any(
                owners.isdisjoint(ids)
                and jurisdiction_keys.isdisjoint(qualifier_options.get(span, ()))
                for span, ids in place_fields.items()
            ):
                continue
        parent_matches = [
            m for m in matches if m.key in ancestors and not match.overlaps(m)
        ]
        # A country name embedded in a matched ancestor belongs to that name.
        # For example, 蒙古 in 内蒙古自治区 does not qualify a Chinese city.
        explicit_qualifiers = [
            options
            for start, end, options in qualifiers
            if (end <= match.start or start >= match.end)
            and not any(
                parent.start <= start
                and end <= parent.end
                and (parent.start, parent.end) != (start, end)
                for parent in parent_matches
            )
        ]
        if any(
            jurisdiction_keys.isdisjoint(options) for options in explicit_qualifiers
        ):
            continue
        if entry["country"] == "CN":
            anchors = [
                m
                for m in matches
                if not match.overlaps(m)
                and place_by_id[m.key]["level"] in {"province", "municipality", "city"}
                and place_by_id[m.key]["country"] == "CN"
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
        # GeoNames numeric admin codes are local to a country and can also
        # appear as house or postal numbers. Keep their positive match signal.
        numeric_admin_match = any(
            context.key == f"admin1:{match.key}" and not match.overlaps(context)
            for context in numeric_contexts
        )
        context_score = (
            len({m.key for m in parent_matches})
            + len(explicit_qualifiers)
            + numeric_admin_match
        )
        score = (context_score, entry["specificity"], match.end - match.start)
        scored.append((score, match))
    if scored:
        preferred = index.get_preferred(normalized)
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
                if normalize_birth_place_text(place_by_id[m.key]["canonical_name"])
                == normalized
            ]
            if canonical:
                scored = canonical
                cities = [
                    (s, m)
                    for s, m in scored
                    if place_by_id[m.key]["level"]
                    in {"city", "municipality", "special_region"}
                ]
                if cities:
                    scored = cities
        best = max(s for s, _ in scored)
        winners = {m.key: m for s, m in scored if s == best}
        # Explicit context always wins over the few stable, established aliases
        # (London means the UK by default, but Canada/London resolves to Ontario).
        if preferred in winners:
            return _resolve(winners[preferred])
        if len(winners) == 1:
            return _resolve(next(iter(winners.values())))
    return EMPTY


def _admin_path(entry: PlaceEntry, index: SqlitePlaceIndex) -> list[str]:
    ancestors = _ancestors(entry["id"])
    if ancestors:
        anc_places = index.get_places(ancestors)
        return [anc_places[anc]["full_name"] for anc in reversed(ancestors)] + [
            entry["full_name"]
        ]
    if entry["country"] == "CN":
        return [entry["full_name"]]
    country_info = index.get_country(entry["country"])
    country_name = country_info["name"] if country_info else entry["country"]
    admin1 = max(
        (alias for alias in entry.get("admin1_aliases", ()) if not alias.isdigit()),
        key=len,
        default=None,
    )
    parts = [country_name]
    if admin1 and admin1 != entry["full_name"] and admin1 != country_name:
        parts.append(admin1)
    if entry["full_name"] != parts[-1]:
        parts.append(entry["full_name"])
    return parts


def _candidate_record(entry: PlaceEntry, index: SqlitePlaceIndex) -> dict[str, Any]:
    return {
        "canonical_name": entry["canonical_name"],
        "display_name": entry["full_name"],
        "admin_path": _admin_path(entry, index),
        "longitude": entry["longitude"],
        "latitude": entry["latitude"],
        "timezone": entry["timezone"],
        "country_code": entry["country"],
        "precision": entry["level"],
    }


def _resolved_record(
    entry: PlaceEntry, index: SqlitePlaceIndex, *, match_source: str
) -> dict[str, Any]:
    return {
        **_candidate_record(entry, index),
        "match_source": match_source,
    }


def _sort_key(entry: PlaceEntry) -> tuple[int, int, str]:
    return (entry["specificity"], -entry.get("population", 0), entry["id"])


def _qualified_candidates(cleaned: str, index: SqlitePlaceIndex) -> list[PlaceEntry]:
    """Collect candidate entries compatible with explicit qualifiers in a non-exact query."""
    _, matches, contexts, _ = _matches(cleaned)
    if not matches:
        return []
    place_by_id = index.get_places([m.key for m in matches])
    qualifier_options: dict[tuple[int, int], set[str]] = defaultdict(set)
    for context in contexts:
        if not context.alias.isdecimal():
            qualifier_options[context.start, context.end].add(context.key)
    qualifiers = [
        (start, end, options)
        for (start, end), options in qualifier_options.items()
        if not any(
            outer_start <= start
            and end <= outer_end
            and (outer_start, outer_end) != (start, end)
            for outer_start, outer_end in qualifier_options
        )
    ]

    candidate_scores: dict[str, tuple[int, int, int]] = {}
    for match in matches:
        entry = place_by_id[match.key]
        ancestors = _ancestors(match.key)
        if any(
            m.start < match.start < m.end < match.end
            and place_by_id[m.key]["level"] in {"province", "municipality", "city"}
            and m.key not in ancestors
            for m in matches
        ):
            continue
        region = (
            "TW"
            if entry["timezone"] == "Asia/Taipei"
            else (
                "HK"
                if entry["timezone"] == "Asia/Hong_Kong"
                else "MO" if entry["timezone"] == "Asia/Macau" else entry["country"]
            )
        )
        jurisdiction_keys = {
            f"country:{entry['country']}",
            f"country:{region}",
            f"admin1:{match.key}",
        }
        parent_matches = [
            m for m in matches if m.key in ancestors and not match.overlaps(m)
        ]
        explicit_qualifiers = [
            options
            for start, end, options in qualifiers
            if (end <= match.start or start >= match.end)
            and not any(
                parent.start <= start
                and end <= parent.end
                and (parent.start, parent.end) != (start, end)
                for parent in parent_matches
            )
        ]
        if any(
            jurisdiction_keys.isdisjoint(options) for options in explicit_qualifiers
        ):
            continue
        score = (
            len({m.key for m in parent_matches}) + len(explicit_qualifiers),
            entry["specificity"],
            match.end - match.start,
        )
        prev = candidate_scores.get(match.key)
        if prev is None or score > prev:
            candidate_scores[match.key] = score

    if not candidate_scores:
        return []
    best_score = max(candidate_scores.values())
    best_ids = [
        place_id for place_id, score in candidate_scores.items() if score == best_score
    ]
    return sorted((place_by_id[k] for k in best_ids), key=_sort_key)


def lookup_place(query: str, *, limit: int = 5) -> dict[str, Any]:
    """Resolve an offline place query or return disambiguating candidates."""
    cleaned = query.strip()
    if not cleaned:
        return {
            "query": query,
            "status": "not_found",
            "resolved": None,
            "candidates": [],
            "summary": "未提供有效查询地名。",
        }

    index = get_place_index()
    normalized, matches, _, _ = _matches(cleaned)
    place_by_id = index.get_places([m.key for m in matches])
    exact = [m for m in matches if m.start == 0 and m.end == len(normalized)]
    exact_ids = list(dict.fromkeys(m.key for m in exact))

    if exact_ids:
        if len(exact_ids) == 1:
            entry = place_by_id[exact_ids[0]]
            resolved = _resolved_record(entry, index, match_source="exact_alias")
            candidates = [_candidate_record(entry, index)]
            return {
                "query": cleaned,
                "status": "resolved",
                "resolved": resolved,
                "candidates": candidates,
                "summary": (
                    f"已解析「{cleaned}」为 {' / '.join(resolved['admin_path'])}"
                    f"（经度 {resolved['longitude']}，纬度 {resolved['latitude']}，"
                    f"时区 {resolved['timezone']}，精度 {resolved['precision']}）。"
                ),
            }

        preferred_id = index.get_preferred(normalized)
        if preferred_id is not None and preferred_id in exact_ids:
            entry = place_by_id[preferred_id]
            ordered_ids = [
                preferred_id,
                *sorted(
                    (k for k in exact_ids if k != preferred_id),
                    key=lambda k: _sort_key(place_by_id[k]),
                ),
            ]
            resolved = _resolved_record(entry, index, match_source="preferred_alias")
            candidates = [
                _candidate_record(place_by_id[k], index) for k in ordered_ids[:limit]
            ]
            return {
                "query": cleaned,
                "status": "resolved",
                "resolved": resolved,
                "candidates": candidates,
                "summary": (
                    f"已按常用地名解析「{cleaned}」为 {' / '.join(resolved['admin_path'])}"
                    f"（经度 {resolved['longitude']}，纬度 {resolved['latitude']}，"
                    f"时区 {resolved['timezone']}，精度 {resolved['precision']}）。"
                ),
            }

        sorted_entries = sorted((place_by_id[k] for k in exact_ids), key=_sort_key)
        candidates = [_candidate_record(e, index) for e in sorted_entries[:limit]]
        preview = "、".join(" / ".join(c["admin_path"]) for c in candidates[:3])
        return {
            "query": cleaned,
            "status": "ambiguous",
            "resolved": None,
            "candidates": candidates,
            "summary": (
                f"地名「{cleaned}」匹配到 {len(sorted_entries)} 个同名地点"
                f"（已列前 {len(candidates)} 项：{preview}）；请补充省/市/国家前缀消歧。"
            ),
        }

    resolution = resolve_birth_place_context(cleaned)
    if resolution.canonical_name is not None:
        matched_entries = [
            place_by_id[m.key]
            for m in matches
            if place_by_id[m.key]["canonical_name"] == resolution.canonical_name
            and place_by_id[m.key]["longitude"] == resolution.longitude
            and place_by_id[m.key]["latitude"] == resolution.latitude
            and place_by_id[m.key]["level"] == resolution.level
        ]
        if matched_entries:
            entry = matched_entries[0]
            match_source = (
                "province_fallback"
                if entry["level"] == "province"
                and normalized != normalize_birth_place_text(entry["canonical_name"])
                else "qualified_match"
            )
            resolved = _resolved_record(entry, index, match_source=match_source)
            candidates = [_candidate_record(entry, index)]
            return {
                "query": cleaned,
                "status": "resolved",
                "resolved": resolved,
                "candidates": candidates,
                "summary": (
                    f"已解析「{cleaned}」为 {' / '.join(resolved['admin_path'])}"
                    f"（经度 {resolved['longitude']}，纬度 {resolved['latitude']}，"
                    f"时区 {resolved['timezone']}，精度 {resolved['precision']}）。"
                ),
            }

    qualified = _qualified_candidates(cleaned, index)
    if len(qualified) > 1:
        candidates = [_candidate_record(e, index) for e in qualified[:limit]]
        preview = "、".join(" / ".join(c["admin_path"]) for c in candidates[:3])
        return {
            "query": cleaned,
            "status": "ambiguous",
            "resolved": None,
            "candidates": candidates,
            "summary": (
                f"地名「{cleaned}」存在 {len(qualified)} 个候选地点"
                f"（已列前 {len(candidates)} 项：{preview}）；请补充更具体行政区划或直接提供经纬度。"
            ),
        }

    return {
        "query": cleaned,
        "status": "not_found",
        "resolved": None,
        "candidates": [],
        "summary": f"离线地名库未收录「{cleaned}」；请改用省/市级名称或直接提供经纬度与时区。",
    }


def resolve_place_location(
    place: str, *, place_field: str = "place"
) -> BirthPlaceResolution:
    """Resolve a place string to coordinates/timezone or raise a structured ParameterError."""
    cleaned = place.strip()
    if not cleaned or cleaned == "未提供":
        raise ParameterError(
            "地点不能为空",
            [{"path": place_field, "code": "invalid_place"}],
        )
    resolution = resolve_birth_place_context(cleaned)
    if (
        resolution.canonical_name is not None
        and resolution.longitude is not None
        and resolution.latitude is not None
        and resolution.timezone is not None
    ):
        return resolution
    lookup = lookup_place(cleaned, limit=5)
    if lookup["status"] == "ambiguous":
        candidates = [
            " / ".join(c["admin_path"]) for c in (lookup.get("candidates") or [])
        ]
        raise ParameterError(
            str(lookup["summary"]),
            [
                {
                    "path": place_field,
                    "code": "ambiguous_place",
                    "constraints": {"candidates": candidates},
                }
            ],
        )
    raise ParameterError(
        str(lookup["summary"]),
        [{"path": place_field, "code": "unknown_place"}],
    )
