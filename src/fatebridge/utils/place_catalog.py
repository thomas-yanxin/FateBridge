"""Load and index the packaged representative place records lazily."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from typing_extensions import NotRequired

PlaceLevel = Literal["province", "special_region", "city", "municipality", "county"]


class PlaceSourceEntry(TypedDict):
    id: str
    aliases: list[str]
    canonical_name: str
    continent: str
    country: str
    coordinate_system: str
    full_name: str
    latitude: float
    level: PlaceLevel
    longitude: float
    parent: str | None
    source: str
    source_id: str
    timezone: str
    admin1_aliases: NotRequired[list[str]]
    feature_code: NotRequired[str]
    population: NotRequired[int]
    source_modified: NotRequired[str]
    source_coordinates: NotRequired[list[float]]


class PlaceEntry(PlaceSourceEntry):
    normalized_aliases: tuple[str, ...]
    specificity: int


class CountryAliases(TypedDict):
    name: str
    continent: str
    aliases: list[str]


class PlaceCatalogAliases(TypedDict):
    preferred_aliases: dict[str, str]


@dataclass(frozen=True)
class PlaceCatalogData:
    entries: tuple[PlaceEntry, ...]
    place_by_id: dict[str, PlaceEntry]
    countries: dict[str, CountryAliases]
    manifest: PlaceCatalogAliases
    alias_index: dict[str, list[str]]
    context_index: dict[str, list[tuple[str, str]]]
    context_commas: dict[str, list[tuple[str, str]]]
    max_alias_length: int
    preferred_aliases: dict[str, str]


PLACE_SPECIFICITY = {
    "province": 1,
    "special_region": 2,
    "city": 3,
    "municipality": 3,
    "county": 4,
}
CATALOG_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "places"


_ASCII_NON_ALNUM_TABLE = str.maketrans(
    "", "", "".join(chr(i) for i in range(128) if not chr(i).isalnum())
)
_PURE_CJK_RE = re.compile(r"^[\u4e00-\u9fff]+$")


def fold_place_text(text: str) -> str:
    if text.isascii():
        return text.lower()
    if _PURE_CJK_RE.match(text):
        return text
    return "".join(
        c
        for c in unicodedata.normalize(
            "NFKD", unicodedata.normalize("NFKC", text).casefold()
        )
        if not unicodedata.combining(c)
    )


def normalize_birth_place_text(text: str) -> str:
    """Fold case/Latin accents and punctuation without dropping other scripts."""
    if text.isascii():
        return text.lower().translate(_ASCII_NON_ALNUM_TABLE)
    if _PURE_CJK_RE.match(text):
        return text
    folded = fold_place_text(text)
    if folded.isascii():
        return folded.translate(_ASCII_NON_ALNUM_TABLE)
    return "".join(c for c in folded if c.isalnum())


def _load_entries() -> tuple[PlaceEntry, ...]:
    entries: list[PlaceEntry] = []
    norm = normalize_birth_place_text
    specificity_by_level = PLACE_SPECIFICITY
    for filename in ("china.json", "world.json"):
        catalog_rows: list[PlaceSourceEntry] = json.loads(
            (CATALOG_DIRECTORY / filename).read_bytes()
        )
        for source_entry in catalog_rows:
            seen_aliases = {
                normalized_alias
                for alias in source_entry["aliases"]
                if (normalized_alias := norm(alias))
            }
            entry = cast(PlaceEntry, source_entry)
            entry["normalized_aliases"] = (
                tuple(sorted(seen_aliases))
                if len(seen_aliases) > 1
                else tuple(seen_aliases)
            )
            entry["specificity"] = specificity_by_level[source_entry["level"]]
            entries.append(entry)
    return tuple(entries)


@lru_cache(maxsize=1)
def get_place_catalog() -> PlaceCatalogData:
    """Parse and index packaged place data once on first lookup."""
    entries = _load_entries()
    place_by_id = {row["id"]: row for row in entries}
    countries: dict[str, CountryAliases] = json.loads(
        (CATALOG_DIRECTORY / "countries.json").read_bytes()
    )
    manifest: PlaceCatalogAliases = json.loads(
        (CATALOG_DIRECTORY / "manifest.json").read_bytes()
    )
    alias_index: dict[str, list[str]] = defaultdict(list)
    context_index: dict[str, list[tuple[str, str]]] = defaultdict(list)
    context_commas: dict[str, list[tuple[str, str]]] = defaultdict(list)

    def index_qualifier(alias: str, jurisdiction: tuple[str, str]) -> None:
        folded = fold_place_text(alias)
        if folded.isascii():
            context_index[folded.translate(_ASCII_NON_ALNUM_TABLE)].append(jurisdiction)
        elif _PURE_CJK_RE.match(folded):
            context_index[folded].append(jurisdiction)
        else:
            context_index["".join(c for c in folded if c.isalnum())].append(
                jurisdiction
            )
        if "," in folded:
            signature = "".join(c for c in folded if c.isalnum() or c == ",")
            context_commas[signature].append(jurisdiction)

    for entry in entries:
        for alias in entry["normalized_aliases"]:
            alias_index[alias].append(entry["id"])
        for alias in entry.get("admin1_aliases", ()):
            index_qualifier(alias, ("admin1", entry["id"]))
    for country, info in countries.items():
        for alias in info["aliases"]:
            index_qualifier(alias, ("country", country))
    max_alias_length = max(map(len, (*alias_index, *context_index)))
    preferred_aliases: dict[str, str] = {}
    for preferred_id in manifest["preferred_aliases"].values():
        if preferred_id in place_by_id:
            for alias in place_by_id[preferred_id]["normalized_aliases"]:
                preferred_aliases[alias] = preferred_id

    return PlaceCatalogData(
        entries=entries,
        place_by_id=place_by_id,
        countries=countries,
        manifest=manifest,
        alias_index=dict(alias_index),
        context_index=dict(context_index),
        context_commas=dict(context_commas),
        max_alias_length=max_alias_length,
        preferred_aliases=preferred_aliases,
    )


_EXPORTED_ATTRS = {
    "KNOWN_BIRTH_PLACE_ENTRIES": "entries",
    "PLACE_BY_ID": "place_by_id",
    "COUNTRIES": "countries",
    "MANIFEST": "manifest",
    "PLACE_ALIAS_INDEX": "alias_index",
    "PLACE_CONTEXT_INDEX": "context_index",
    "PLACE_CONTEXT_COMMAS": "context_commas",
    "MAX_PLACE_ALIAS_LENGTH": "max_alias_length",
    "PREFERRED_PLACE_ALIASES": "preferred_aliases",
}


def __getattr__(name: str) -> Any:
    field_name = _EXPORTED_ATTRS.get(name)
    if field_name is not None:
        return getattr(get_place_catalog(), field_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
