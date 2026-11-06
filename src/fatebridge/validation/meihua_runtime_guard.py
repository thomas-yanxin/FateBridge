"""Stable configured calendar inputs, distinct from a native atomic read set."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from fatebridge.core.ephemeris_paths import ephemeris_search_directories
from fatebridge.utils.json_digest import digest


@lru_cache(maxsize=64)
def _large_ephemeris_digest(filename: str, signature: tuple[int, ...]) -> str:
    path = Path(filename)
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for piece in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(piece)
    if _stat_signature(path) != signature:
        raise ValueError("Ephemeris file changed while its inventory was hashed")
    return hasher.hexdigest()


def _stat_signature(path: Path) -> tuple[int, ...]:
    stat = path.stat()
    return (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino, stat.st_dev)


def _ephemeris_inventory(directory: str | None) -> dict[str, Any]:
    files: dict[str, str] = {}
    if directory:
        for index, root in enumerate(ephemeris_search_directories(directory)):
            for path in sorted(root.glob("*.se1")):
                if path.is_file():
                    files[f"{index}/{path.name}"] = _large_ephemeris_digest(
                        str(path.resolve()), _stat_signature(path)
                    )
            for name in (
                "seorbel.txt",
                "sefstars.txt",
                "seleapsec.txt",
                "seasnam.txt",
                "swe_deltat.txt",
                "sedeltat.txt",
            ):
                path = root / name
                if path.is_file():
                    # Small source files can immediately change a calculation
                    # at the same directory. Never cache solely by path/stat.
                    files[f"{index}/{name}"] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
    return {
        "scope": "effective_se1_and_auxiliary_inventory; actual models/sources are reported separately",
        "freshness": "Auxiliary text bytes hashed each receipt; large se1 hashes cached by size/mtime/ctime/inode/device, not a continuous immutability proof",
        "files": files,
        "sha256": digest(files),
    }


def capture_calendar_runtime() -> dict[str, Any]:
    """Fingerprint the selected configuration without changing native state."""
    from fatebridge.core import ephemeris_runtime
    from fatebridge.core.ephemeris_paths import ephemeris_search_directories
    from fatebridge.core.jpl_ephemeris import configured_jpl_file
    from fatebridge.core.solar_model_policy import solar_model_environment_receipt
    from fatebridge.core.solar_term_runtime import loaded_clock_profile_key

    selected = ephemeris_runtime.effective_ephemeris_search_path()
    solar = solar_model_environment_receipt()
    inventory = _ephemeris_inventory(selected)
    jpl_name = configured_jpl_file()
    jpl_inputs = {}
    if jpl_name is not None:
        for index, directory in enumerate(ephemeris_search_directories(selected)):
            candidate = directory / jpl_name
            if candidate.is_file():
                jpl_inputs[f"{index}/{jpl_name}"] = _large_ephemeris_digest(
                    str(candidate.resolve()), _stat_signature(candidate)
                )
    native = ephemeris_runtime.swe
    binary = getattr(native, "__file__", None)
    try:
        binding_version = version("pyswisseph")
    except PackageNotFoundError:
        binding_version = None
    receipt = {
        "guard_id": "meihua_calendar_runtime_guard_v1",
        "effective_search_path_sha256": digest(
            [str(p.resolve()) for p in ephemeris_search_directories(selected)]
        ),
        "ephemeris_inventory": inventory,
        "configured_native_jpl_filename": jpl_name,
        "configured_native_jpl_files": jpl_inputs,
        "solar_model_configuration": solar,
        "loaded_clock_profile_sha256": loaded_clock_profile_key(),
        "native_library_version": str(getattr(native, "version", "unavailable")),
        "native_binding_distribution_version": binding_version,
        "native_binding_file_sha256": (
            hashlib.sha256(Path(binary).read_bytes()).hexdigest() if binary else None
        ),
        "actual_native_read_set_attested": False,
        "physical_accuracy_established": False,
        "scope": "Configured search paths, tracked native files, loaded solar/clock profiles and binding file held stable between two checkpoints. Not an atomic read set, loaded-memory attestation, proof of fresh native caches or astronomical accuracy. Use a fresh process and a stable materialized runtime.",
    }
    if (
        ephemeris_runtime.effective_ephemeris_search_path() != selected
        or solar_model_environment_receipt() != solar
    ):
        raise ValueError("Calendar runtime inputs changed while capturing audit guard")
    return receipt


def verify_calendar_runtime(expected: dict[str, Any]) -> None:
    if capture_calendar_runtime() != expected:
        raise ValueError("Calendar runtime inputs changed during audit")
