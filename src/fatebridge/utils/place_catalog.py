"""Load and index the packaged representative place records lazily."""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
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
SQLITE_INDEX_FILENAME = "places.sqlite"


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


def _load_entries(directory: Path = CATALOG_DIRECTORY) -> tuple[PlaceEntry, ...]:
    entries: list[PlaceEntry] = []
    norm = normalize_birth_place_text
    specificity_by_level = PLACE_SPECIFICITY
    for filename in ("china.json", "world.json"):
        catalog_rows: list[PlaceSourceEntry] = json.loads(
            (directory / filename).read_bytes()
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


def build_place_catalog_from_directory(
    directory: Path = CATALOG_DIRECTORY,
) -> PlaceCatalogData:
    """Parse and index place JSON files from a directory."""
    entries = _load_entries(directory)
    place_by_id = {row["id"]: row for row in entries}
    countries: dict[str, CountryAliases] = json.loads(
        (directory / "countries.json").read_bytes()
    )
    manifest: PlaceCatalogAliases = json.loads(
        (directory / "manifest.json").read_bytes()
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


@lru_cache(maxsize=1)
def get_place_catalog() -> PlaceCatalogData:
    """Parse and index packaged place data once on first full-catalog demand."""
    return build_place_catalog_from_directory(CATALOG_DIRECTORY)


_SQLITE_BATCH_CHUNK = 500


class SqlitePlaceIndex:
    """Fast read-only point/batch lookup backed by precompiled places.sqlite."""

    def __init__(self, db_path: Path) -> None:
        self._conn = sqlite3.connect(
            f"file:{db_path}?mode=ro&immutable=1",
            uri=True,
            check_same_thread=False,
        )
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'max_alias_length'"
        ).fetchone()
        self.max_alias_length: int = int(row[0]) if row is not None else 64
        self._place_cache: dict[str, PlaceEntry] = {}
        self._country_cache: dict[str, CountryAliases | None] = {}

    def lookup_aliases(self, candidates: Sequence[str]) -> dict[str, list[str]]:
        unique = [c for c in dict.fromkeys(candidates) if c]
        if not unique:
            return {}
        out: dict[str, list[str]] = {}
        for i in range(0, len(unique), _SQLITE_BATCH_CHUNK):
            chunk = unique[i : i + _SQLITE_BATCH_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            rows = self._conn.execute(
                f"SELECT alias, place_id FROM alias_index WHERE alias IN ({placeholders})",
                chunk,
            ).fetchall()
            for alias, place_id in rows:
                out.setdefault(alias, []).append(place_id)
        return out

    def lookup_contexts(
        self, candidates: Sequence[str]
    ) -> dict[str, list[tuple[str, str]]]:
        unique = [c for c in dict.fromkeys(candidates) if c]
        if not unique:
            return {}
        out: dict[str, list[tuple[str, str]]] = {}
        for i in range(0, len(unique), _SQLITE_BATCH_CHUNK):
            chunk = unique[i : i + _SQLITE_BATCH_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            rows = self._conn.execute(
                f"SELECT alias, kind, key FROM context_index WHERE alias IN ({placeholders})",
                chunk,
            ).fetchall()
            for alias, kind, key in rows:
                out.setdefault(alias, []).append((kind, key))
        return out

    def lookup_context_commas(
        self, signatures: Sequence[str]
    ) -> dict[str, list[tuple[str, str]]]:
        unique = [s for s in dict.fromkeys(signatures) if s]
        if not unique:
            return {}
        out: dict[str, list[tuple[str, str]]] = {}
        for i in range(0, len(unique), _SQLITE_BATCH_CHUNK):
            chunk = unique[i : i + _SQLITE_BATCH_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            rows = self._conn.execute(
                f"SELECT signature, kind, key FROM context_commas WHERE signature IN ({placeholders})",
                chunk,
            ).fetchall()
            for sig, kind, key in rows:
                out.setdefault(sig, []).append((kind, key))
        return out

    def get_places(self, place_ids: Sequence[str]) -> dict[str, PlaceEntry]:
        result: dict[str, PlaceEntry] = {}
        missing: list[str] = []
        for pid in dict.fromkeys(place_ids):
            if pid in self._place_cache:
                result[pid] = self._place_cache[pid]
            else:
                missing.append(pid)
        for i in range(0, len(missing), _SQLITE_BATCH_CHUNK):
            chunk = missing[i : i + _SQLITE_BATCH_CHUNK]
            placeholders = ",".join("?" for _ in chunk)
            rows = self._conn.execute(
                f"SELECT id, payload_json FROM places WHERE id IN ({placeholders})",
                chunk,
            ).fetchall()
            for pid, payload_json in rows:
                entry = cast(PlaceEntry, json.loads(payload_json))
                entry["normalized_aliases"] = tuple(entry["normalized_aliases"])
                self._place_cache[pid] = entry
                result[pid] = entry
        return result

    def get_place(self, place_id: str) -> PlaceEntry | None:
        cached = self._place_cache.get(place_id)
        if cached is not None:
            return cached
        row = self._conn.execute(
            "SELECT payload_json FROM places WHERE id = ?", (place_id,)
        ).fetchone()
        if row is None:
            return None
        entry = cast(PlaceEntry, json.loads(row[0]))
        entry["normalized_aliases"] = tuple(entry["normalized_aliases"])
        self._place_cache[place_id] = entry
        return entry

    def get_preferred(self, normalized_alias: str) -> str | None:
        row = self._conn.execute(
            "SELECT place_id FROM preferred_aliases WHERE alias = ?",
            (normalized_alias,),
        ).fetchone()
        return str(row[0]) if row is not None else None

    def get_country(self, code: str) -> CountryAliases | None:
        if code in self._country_cache:
            return self._country_cache[code]
        row = self._conn.execute(
            "SELECT name, continent, aliases_json FROM countries WHERE code = ?",
            (code,),
        ).fetchone()
        if row is None:
            self._country_cache[code] = None
            return None
        info: CountryAliases = {
            "name": str(row[0]),
            "continent": str(row[1]),
            "aliases": list(json.loads(row[2])),
        }
        self._country_cache[code] = info
        return info


@lru_cache(maxsize=1)
def get_place_index() -> SqlitePlaceIndex:
    """Return the precompiled read-only SQLite place index."""
    db_path = CATALOG_DIRECTORY / SQLITE_INDEX_FILENAME
    if not db_path.is_file():
        raise FileNotFoundError(
            f"Precompiled place index missing: {db_path}. "
            "Run scripts/build_place_index.py to generate it."
        )
    return SqlitePlaceIndex(db_path)


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
