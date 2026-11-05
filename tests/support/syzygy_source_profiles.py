"""Explicit data identities for source-history and source-observation checks."""

import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as configuration

PROTOCOL = json.loads(
    (
        Path(__file__).parents[1] / "fixtures/western-syzygy-source-profiles-v1.json"
    ).read_text()
)


@pytest.fixture(scope="session")
def syzygy_profile_directories(tmp_path_factory):
    root = Path(
        os.environ.get(
            "FATEBRIDGE_TEST_EPHE_DIR", Path(__file__).resolve().parents[2] / "ephe"
        )
    )
    parent = tmp_path_factory.mktemp("syzygy-source-profiles")
    prepared = {}

    def directory(profile):
        if profile not in prepared:
            target = parent / profile
            target.mkdir()
            for row in PROTOCOL["profiles"][profile]:
                path = root / row["name"]
                assert (
                    path.is_file()
                ), f"Acquire pinned ephemeris input {row['name']} before running this profile"
                assert path.stat().st_size == row["size"]
                assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
                shutil.copy2(path, target / row["name"])
            assert {p.name for p in target.iterdir()} == {
                r["name"] for r in PROTOCOL["profiles"][profile]
            }
            prepared[profile] = target
        return prepared[profile]

    return directory


@pytest.fixture
def syzygy_source_profile(request, syzygy_profile_directories, monkeypatch):
    profile = getattr(request, "param", "recorded5")
    previous = configuration.configured_ephemeris_path()
    previous_env = os.environ.get("SE_EPHE_PATH")
    selected = syzygy_profile_directories(profile)
    monkeypatch.setenv("SE_EPHE_PATH", str(selected))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    configuration.configure_ephemeris_path(str(selected))
    try:
        yield profile
    finally:
        if previous_env is None:
            monkeypatch.delenv("SE_EPHE_PATH", raising=False)
        else:
            monkeypatch.setenv("SE_EPHE_PATH", previous_env)
        configuration.configure_ephemeris_path(previous if previous is not None else "")
