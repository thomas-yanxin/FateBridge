"""Pinned native ephemeris files and runtime isolation for Jyotish tests."""

import os
import shutil
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.birth import AstroBirthInfo, build_astro_birth_info
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    verify_ephemeris_bytes,
)
from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.core.astro.tt_epoch import TTInstant


class EphemerisFixture(NamedTuple):
    source_directory: Path
    private_directory: Path


@pytest.fixture(autouse=True)
def restore_runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    previous = e.configured_ephemeris_path()
    previous_env = os.environ.get("SE_EPHE_PATH")
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    yield
    if previous_env is None:
        monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    else:
        monkeypatch.setenv("SE_EPHE_PATH", previous_env)
    e.configure_ephemeris_path(previous if previous is not None else "")


@pytest.fixture
def data18(tmp_path: Path) -> EphemerisFixture:
    root = Path(
        os.environ.get(
            "FATEBRIDGE_TEST_EPHE_DIR", Path(__file__).resolve().parents[3] / "ephe"
        )
    )
    manifest = load_ephemeris_manifest()
    for name in ("sepl_18.se1", "semo_18.se1", "sepl_24.se1", "semo_24.se1"):
        path = root / name
        assert (
            path.is_file()
        ), "Acquire pinned Swiss test files separately: python -m fatebridge.fetch_ephe --years 1800 2500"
        verify_ephemeris_bytes(name, path.read_bytes(), manifest)
    target = tmp_path / "private-ephe"
    target.mkdir()
    for name in ("sepl_18.se1", "semo_18.se1"):
        shutil.copy2(root / name, target / name)
        (target / name).chmod(0o644)
    e.configure_ephemeris_path(str(target))
    return EphemerisFixture(root, target)


def birth(moment: datetime | None = None) -> AstroBirthInfo:
    if moment is None:
        moment = datetime(2000, 1, 1, 12, tzinfo=timezone.utc)
    else:
        pass
    return build_astro_birth_info(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_microsecond=moment.microsecond,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        preserve_instant=True,
    )


def full_files(ephemeris_files: EphemerisFixture) -> Path:
    root, directory = ephemeris_files
    for name in ("sepl_24.se1", "semo_24.se1"):
        shutil.copy2(root / name, directory / name)
    e.configure_ephemeris_path(str(directory))
    return directory


def edge_birth() -> AstroBirthInfo:
    """Return a birth at the actual native Sun file endpoint."""
    e.ephemeris_call("calc", 2451545.0, e.swe.SUN, e.swe.FLG_SWIEPH)
    return birth(datetime_from_tt(e.swe.get_current_file_data(0)[2]))


def from_tt(julian_day_tt: float | TTInstant) -> AstroBirthInfo:
    """Build the equatorial UTC reference birth for a given TT epoch."""
    moment = datetime_from_tt(julian_day_tt)
    return build_astro_birth_info(
        birth_year=moment.year,
        birth_month=moment.month,
        birth_day=moment.day,
        birth_hour=moment.hour,
        birth_minute=moment.minute,
        birth_second=moment.second,
        birth_microsecond=moment.microsecond,
        birth_timezone="UTC",
        birth_longitude=0,
        birth_latitude=0,
        preserve_instant=True,
    )
