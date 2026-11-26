"""Shared Guolao chart inputs and native ephemeris controls."""

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import JsonValue

from fatebridge.core import ephemeris_runtime
from fatebridge.core.astro.physical_epoch import PhysicalEpoch
from fatebridge.core.astro.time_scales import ut1_from_tt
from fatebridge.services.astrology import calculate_core_chart_analysis
from tests.fixtures.surface_payloads import astro_payload

SOURCE_DOMAINS = {
    row["id"]: row
    for row in json.loads(
        (
            Path(__file__).parents[2]
            / "fixtures/historical-utc-domain-reference-v1.json"
        ).read_text()
    )["guolao_original_adjustment_source_domain"]["rows"]
}


def chart(
    **overrides: str | int | float | bool | datetime | None,
) -> dict[str, JsonValue]:
    return calculate_core_chart_analysis(
        **{**astro_payload(), "chart_variant": "guolao_chart", **overrides}
    )


def epoch_for(julian_day_tt: float) -> PhysicalEpoch:
    return PhysicalEpoch.from_ut1(ut1_from_tt(julian_day_tt))


@pytest.fixture(autouse=True)
def fixed_moshier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    previous = ephemeris_runtime.configured_ephemeris_path()
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path))
    ephemeris_runtime.swe.close()
    ephemeris_runtime.configure_ephemeris_path(str(tmp_path))
    try:
        yield
    finally:
        monkeypatch.undo()
        ephemeris_runtime.swe.close()
        ephemeris_runtime.configure_ephemeris_path(
            previous if previous is not None else ""
        )
