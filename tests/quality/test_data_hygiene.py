"""Verify that packaged data files are actively referenced by runtime or build code."""

from __future__ import annotations

import json
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src" / "fatebridge"
DATA_DIR = SRC_DIR / "data"

LICENSE_FILES = frozenset(
    {
        "astronomy/erfa-license.txt",
        "knowledge/iers-c04-LICENSE.txt",
        "sukuyo_dayan_reference_LICENSE.txt",
    }
)


def _data_stem(filename: str) -> str:
    for suffix in (".bin.gz", ".json.gz", ".json", ".txt", ".c.in", ".c", ".S"):
        if filename.endswith(suffix):
            return filename[: -len(suffix)]
    return filename


def test_every_packaged_data_file_is_referenced_by_source() -> None:
    """Every non-license, non-__init__.py file in data/ must be referenced in src/fatebridge."""
    source_blob = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(SRC_DIR.rglob("*.py"))
    )

    unreferenced: list[str] = []
    for path in sorted(DATA_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(DATA_DIR).as_posix()
        if path.name == "__init__.py" or rel in LICENSE_FILES:
            continue
        if fnmatch(rel, "astronomy/de441-planetary-*-part-*.bin.gz"):
            continue
        stem = _data_stem(path.name)
        if (
            rel not in source_blob
            and path.name not in source_blob
            and not (len(stem) >= 8 and stem in source_blob)
        ):
            unreferenced.append(rel)

    assert (
        not unreferenced
    ), f"Unreferenced files in src/fatebridge/data/: {unreferenced}"


def test_purged_audit_and_witness_files_stay_absent() -> None:
    """Removed research-validation and witness-only files must not be reintroduced."""
    assert not (DATA_DIR / "meihua" / "weather-research-validation-v1.json").exists()
    assert not (DATA_DIR / "canping" / "text-witnesses-v1.json").exists()


def test_numerology_source_catalogue_paths_exist() -> None:
    """Every entry in numerology-sources-v1.json must resolve to an existing file."""
    catalogue = json.loads(
        (DATA_DIR / "knowledge" / "numerology-sources-v1.json").read_bytes()
    )
    missing = [
        entry["source_path"]
        for entry in catalogue["sources"]
        if not (DATA_DIR / entry["source_path"]).is_file()
    ]
    assert not missing, f"Missing numerology source files: {missing}"
