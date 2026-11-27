"""Build and verify the precompiled read-only SQLite place index."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

from fatebridge.utils.place_catalog import (
    CATALOG_DIRECTORY,
    SQLITE_INDEX_FILENAME,
    build_place_catalog_from_directory,
)

SOURCE_FILES = ("china.json", "world.json", "countries.json", "manifest.json")


def compute_source_sha256(directory: Path = CATALOG_DIRECTORY) -> str:
    """Compute a deterministic SHA-256 digest over the packaged place JSON files."""
    digest = hashlib.sha256()
    for filename in SOURCE_FILES:
        path = directory / filename
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_sqlite_index(
    output_path: Path | None = None, *, directory: Path = CATALOG_DIRECTORY
) -> Path:
    """Compile packaged JSON place catalogs into a read-only SQLite index."""
    target = output_path or (directory / SQLITE_INDEX_FILENAME)
    catalog = build_place_catalog_from_directory(directory)
    source_sha256 = compute_source_sha256(directory)

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".places.", suffix=".sqlite.tmp", dir=str(target.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        import os

        os.close(fd)
        conn = sqlite3.connect(str(tmp_path))
        try:
            conn.executescript("""
                PRAGMA journal_mode = OFF;
                PRAGMA synchronous = OFF;
                PRAGMA page_size = 4096;

                CREATE TABLE meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                ) WITHOUT ROWID;

                CREATE TABLE places (
                    id TEXT PRIMARY KEY,
                    parent TEXT,
                    canonical_name TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    country TEXT NOT NULL,
                    level TEXT NOT NULL,
                    specificity INTEGER NOT NULL,
                    longitude REAL NOT NULL,
                    latitude REAL NOT NULL,
                    timezone TEXT NOT NULL,
                    population INTEGER,
                    admin1_aliases_json TEXT,
                    payload_json TEXT NOT NULL
                ) WITHOUT ROWID;

                CREATE TABLE alias_index (
                    alias TEXT NOT NULL,
                    place_id TEXT NOT NULL,
                    PRIMARY KEY (alias, place_id)
                ) WITHOUT ROWID;

                CREATE TABLE context_index (
                    alias TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    key TEXT NOT NULL,
                    PRIMARY KEY (alias, kind, key)
                ) WITHOUT ROWID;

                CREATE TABLE context_commas (
                    signature TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    key TEXT NOT NULL,
                    PRIMARY KEY (signature, kind, key)
                ) WITHOUT ROWID;

                CREATE TABLE preferred_aliases (
                    alias TEXT PRIMARY KEY,
                    place_id TEXT NOT NULL
                ) WITHOUT ROWID;

                CREATE TABLE countries (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    continent TEXT NOT NULL,
                    aliases_json TEXT NOT NULL
                ) WITHOUT ROWID;
                """)

            conn.executemany(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                [
                    ("schema_version", "1"),
                    ("source_sha256", source_sha256),
                    ("max_alias_length", str(catalog.max_alias_length)),
                    ("entry_count", str(len(catalog.entries))),
                ],
            )

            conn.executemany(
                """
                INSERT INTO places (
                    id, parent, canonical_name, full_name, country, level,
                    specificity, longitude, latitude, timezone, population,
                    admin1_aliases_json, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry["id"],
                        entry["parent"],
                        entry["canonical_name"],
                        entry["full_name"],
                        entry["country"],
                        entry["level"],
                        entry["specificity"],
                        entry["longitude"],
                        entry["latitude"],
                        entry["timezone"],
                        entry.get("population"),
                        json.dumps(entry.get("admin1_aliases", []), ensure_ascii=False),
                        json.dumps(entry, ensure_ascii=False, separators=(",", ":")),
                    )
                    for entry in catalog.entries
                ],
            )

            alias_rows = [
                (alias, place_id)
                for alias, place_ids in catalog.alias_index.items()
                for place_id in dict.fromkeys(place_ids)
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO alias_index (alias, place_id) VALUES (?, ?)",
                alias_rows,
            )

            context_rows = [
                (alias, kind, key)
                for alias, pairs in catalog.context_index.items()
                for kind, key in dict.fromkeys(pairs)
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO context_index (alias, kind, key) VALUES (?, ?, ?)",
                context_rows,
            )

            comma_rows = [
                (sig, kind, key)
                for sig, pairs in catalog.context_commas.items()
                for kind, key in dict.fromkeys(pairs)
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO context_commas (signature, kind, key) VALUES (?, ?, ?)",
                comma_rows,
            )

            conn.executemany(
                "INSERT INTO preferred_aliases (alias, place_id) VALUES (?, ?)",
                list(catalog.preferred_aliases.items()),
            )

            conn.executemany(
                "INSERT INTO countries (code, name, continent, aliases_json) VALUES (?, ?, ?, ?)",
                [
                    (
                        code,
                        info["name"],
                        info["continent"],
                        json.dumps(info["aliases"], ensure_ascii=False),
                    )
                    for code, info in catalog.countries.items()
                ],
            )

            conn.commit()
            conn.execute("VACUUM")
            conn.commit()
        finally:
            conn.close()
        tmp_path.replace(target)
        target.chmod(0o644)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    return target


def check_sqlite_index(
    index_path: Path | None = None, *, directory: Path = CATALOG_DIRECTORY
) -> tuple[bool, str]:
    """Verify that the precompiled SQLite index matches the source JSON files."""
    target = index_path or (directory / SQLITE_INDEX_FILENAME)
    if not target.is_file():
        return False, f"Missing place SQLite index: {target}"
    expected_sha = compute_source_sha256(directory)
    conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        if meta.get("schema_version") != "1":
            return False, f"Unexpected schema_version: {meta.get('schema_version')}"
        if meta.get("source_sha256") != expected_sha:
            return (
                False,
                f"source_sha256 mismatch: {meta.get('source_sha256')} != {expected_sha}",
            )
        places_count = conn.execute("SELECT COUNT(*) FROM places").fetchone()[0]
        if str(places_count) != meta.get("entry_count"):
            return (
                False,
                f"entry_count mismatch: {places_count} != {meta.get('entry_count')}",
            )
    except sqlite3.Error as exc:
        return False, f"SQLite verification error: {exc}"
    finally:
        conn.close()
    return True, f"OK: {target} ({places_count} places, sha256={expected_sha[:12]})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that places.sqlite is up-to-date with the source JSON files.",
    )
    args = parser.parse_args(argv)
    if args.check:
        ok, message = check_sqlite_index()
        print(message)
        return 0 if ok else 1
    target = build_sqlite_index()
    ok, message = check_sqlite_index(target)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
