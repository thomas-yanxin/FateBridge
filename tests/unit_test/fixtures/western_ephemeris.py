"""Supply pinned Swiss segments and preserve the test runtime selection."""

import os
import shutil
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro.birth import AstroBirthInfo, build_astro_birth_info
from fatebridge.core.astro.ephemeris_integrity import (
    load_ephemeris_manifest,
    verify_ephemeris_bytes,
)


@pytest.fixture(autouse=True)
def restore_configuration(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    previous = e.configured_ephemeris_path()
    previous_env = os.environ.get("SE_EPHE_PATH")
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    yield
    if previous_env is None:
        monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    else:
        monkeypatch.setenv("SE_EPHE_PATH", previous_env)
    e.configure_ephemeris_path(previous if previous is not None else "")


@pytest.fixture
def ephemeris_files(tmp_path: Path) -> tuple[Path, Path]:
    source = Path(
        os.environ.get(
            "FATEBRIDGE_TEST_EPHE_DIR",
            str(Path(__file__).resolve().parents[3] / "ephe"),
        )
    )
    manifest = load_ephemeris_manifest()
    for name in ("sepl_18.se1", "semo_18.se1", "sepl_24.se1", "semo_24.se1"):
        if not (source / name).is_file():
            pytest.fail(
                "This integration test requires separately acquired, pinned Swiss files: "
                "uv run --locked --extra dev python -m fatebridge.fetch_ephe --years 1800 2500"
            )
        else:
            pass
        verify_ephemeris_bytes(name, (source / name).read_bytes(), manifest)
    target = tmp_path / "ephe"
    target.mkdir()
    for name in ("sepl_18.se1", "semo_18.se1"):
        shutil.copy2(source / name, target / name)
        # Frozen integration inputs are read-only. Only private disposable
        # copies may be mutated by the file-change regression on every OS.
        (target / name).chmod(0o644)
    return source, target


def birth(moment: datetime | None = None) -> AstroBirthInfo:
    if moment is None:
        return build_astro_birth_info(
            birth_year=2000,
            birth_month=1,
            birth_day=1,
            birth_hour=12,
            birth_timezone="UTC",
            birth_longitude=0,
            birth_latitude=0,
        )
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
    )


@pytest.fixture
def configured_ephemeris_files(ephemeris_files: tuple[Path, Path]) -> tuple[Path, Path]:
    _, directory = ephemeris_files
    e.configure_ephemeris_path(str(directory))
    return ephemeris_files
