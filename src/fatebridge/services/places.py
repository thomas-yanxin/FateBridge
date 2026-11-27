"""Offline place lookup service exposing coordinates, timezone and disambiguation candidates."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fatebridge.utils.place_catalog import (
    PlaceCatalogData,
    PlaceEntry,
    get_place_catalog,
    normalize_birth_place_text,
)
from fatebridge.utils.places import (
    _ancestors,
    _matches,
    resolve_birth_place_context,
)


def _admin_path(entry: PlaceEntry, catalog: PlaceCatalogData) -> list[str]:
    place_by_id = catalog.place_by_id
    ancestors = _ancestors(entry["id"])
    if ancestors:
        return [place_by_id[anc]["full_name"] for anc in reversed(ancestors)] + [
            entry["full_name"]
        ]
    if entry["country"] == "CN":
        return [entry["full_name"]]
    country_info = catalog.countries.get(entry["country"])
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


def _candidate_record(entry: PlaceEntry, catalog: PlaceCatalogData) -> dict[str, Any]:
    return {
        "canonical_name": entry["canonical_name"],
        "display_name": entry["full_name"],
        "admin_path": _admin_path(entry, catalog),
        "longitude": entry["longitude"],
        "latitude": entry["latitude"],
        "timezone": entry["timezone"],
        "country_code": entry["country"],
        "precision": entry["level"],
    }


def _resolved_record(
    entry: PlaceEntry, catalog: PlaceCatalogData, *, match_source: str
) -> dict[str, Any]:
    return {
        **_candidate_record(entry, catalog),
        "match_source": match_source,
    }


def _sort_key(entry: PlaceEntry) -> tuple[int, int, str]:
    return (entry["specificity"], -entry.get("population", 0), entry["id"])


def _qualified_candidates(cleaned: str, catalog: PlaceCatalogData) -> list[PlaceEntry]:
    """Collect candidate entries compatible with explicit qualifiers in a non-exact query."""
    _, matches, contexts, _ = _matches(cleaned)
    if not matches:
        return []
    place_by_id = catalog.place_by_id
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


def calculate_place_lookup(*, query: str, limit: int = 5) -> dict[str, Any]:
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

    catalog = get_place_catalog()
    place_by_id = catalog.place_by_id
    normalized, matches, _, _ = _matches(cleaned)
    exact = [m for m in matches if m.start == 0 and m.end == len(normalized)]
    exact_ids = list(dict.fromkeys(m.key for m in exact))

    if exact_ids:
        if len(exact_ids) == 1:
            entry = place_by_id[exact_ids[0]]
            resolved = _resolved_record(entry, catalog, match_source="exact_alias")
            candidates = [_candidate_record(entry, catalog)]
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

        preferred_id = catalog.preferred_aliases.get(normalized)
        if preferred_id is not None and preferred_id in exact_ids:
            entry = place_by_id[preferred_id]
            ordered_ids = [
                preferred_id,
                *sorted(
                    (k for k in exact_ids if k != preferred_id),
                    key=lambda k: _sort_key(place_by_id[k]),
                ),
            ]
            resolved = _resolved_record(entry, catalog, match_source="preferred_alias")
            candidates = [
                _candidate_record(place_by_id[k], catalog) for k in ordered_ids[:limit]
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
        candidates = [_candidate_record(e, catalog) for e in sorted_entries[:limit]]
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
            resolved = _resolved_record(entry, catalog, match_source=match_source)
            candidates = [_candidate_record(entry, catalog)]
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

    qualified = _qualified_candidates(cleaned, catalog)
    if len(qualified) > 1:
        candidates = [_candidate_record(e, catalog) for e in qualified[:limit]]
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
