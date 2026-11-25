"""Load and index the packaged representative place records."""

import json
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Literal, TypedDict

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


PLACE_SPECIFICITY = {
    "province": 1,
    "special_region": 2,
    "city": 3,
    "municipality": 3,
    "county": 4,
}
CATALOG_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "places"


def fold_place_text(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize(
            "NFKD", unicodedata.normalize("NFKC", text).casefold()
        )
        if not unicodedata.combining(c)
    )


def normalize_birth_place_text(text: str) -> str:
    """Fold case/Latin accents and punctuation without dropping other scripts."""
    return "".join(filter(str.isalnum, fold_place_text(text)))


def _load_entries() -> tuple[PlaceEntry, ...]:
    entries: list[PlaceEntry] = []
    for filename in ("china.json", "world.json"):
        catalog_rows: list[PlaceSourceEntry] = json.loads(
            (CATALOG_DIRECTORY / filename).read_text(encoding="utf-8")
        )
        for source_entry in catalog_rows:
            normalized_aliases = tuple(
                sorted(
                    {
                        normalized_alias
                        for alias in source_entry["aliases"]
                        if (normalized_alias := normalize_birth_place_text(alias))
                    }
                )
            )
            entries.append(
                {
                    **source_entry,
                    "normalized_aliases": normalized_aliases,
                    "specificity": PLACE_SPECIFICITY[source_entry["level"]],
                }
            )
    return tuple(entries)


KNOWN_BIRTH_PLACE_ENTRIES = _load_entries()
PLACE_BY_ID = {r["id"]: r for r in KNOWN_BIRTH_PLACE_ENTRIES}
_COUNTRIES: dict[str, CountryAliases] = json.loads(
    (CATALOG_DIRECTORY / "countries.json").read_text(encoding="utf-8")
)
_MANIFEST: PlaceCatalogAliases = json.loads(
    (CATALOG_DIRECTORY / "manifest.json").read_text(encoding="utf-8")
)
PLACE_ALIAS_INDEX: dict[str, list[str]] = defaultdict(list)
PLACE_CONTEXT_INDEX: dict[str, list[tuple[str, str]]] = defaultdict(list)
PLACE_CONTEXT_COMMAS: dict[str, list[tuple[str, str]]] = defaultdict(list)


def _index_qualifier(alias: str, jurisdiction: tuple[str, str]) -> None:
    folded = fold_place_text(alias)
    PLACE_CONTEXT_INDEX["".join(filter(str.isalnum, folded))].append(jurisdiction)
    if "," in folded:
        signature = "".join(c for c in folded if c.isalnum() or c == ",")
        PLACE_CONTEXT_COMMAS[signature].append(jurisdiction)


for _entry in KNOWN_BIRTH_PLACE_ENTRIES:
    for _alias in _entry["normalized_aliases"]:
        PLACE_ALIAS_INDEX[_alias].append(_entry["id"])
    for _alias in _entry.get("admin1_aliases", ()):
        _index_qualifier(_alias, ("admin1", _entry["id"]))
for _country, _info in _COUNTRIES.items():
    for _alias in _info["aliases"]:
        _index_qualifier(_alias, ("country", _country))
MAX_PLACE_ALIAS_LENGTH = max(map(len, (*PLACE_ALIAS_INDEX, *PLACE_CONTEXT_INDEX)))
PREFERRED_PLACE_ALIASES: dict[str, str] = {}
for _preferred_id in _MANIFEST["preferred_aliases"].values():
    if _preferred_id in PLACE_BY_ID:
        for _alias in PLACE_BY_ID[_preferred_id]["normalized_aliases"]:
            PREFERRED_PLACE_ALIASES[_alias] = _preferred_id
