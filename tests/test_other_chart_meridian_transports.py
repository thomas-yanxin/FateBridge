"""Selected Meridian cusps and samples across actual REST, MCP and CLI."""

import pytest

from fatebridge.application.examples import evidence_views
from fatebridge.services.tool_catalog import CATALOG
from tests.test_other_chart_schools_transports import (
    test_specialized_facts_across_three_real_surfaces as check_surfaces,
)


@pytest.mark.parametrize(
    "key,variant", [("astro_germany", None), ("astro_chart", "germany")]
)
@pytest.mark.parametrize("zodiacal", [0, 1])
def test_native_meridian_cusps_across_three_surfaces(
    monkeypatch, capsys, tmp_path, key, variant, zodiacal
):
    spec = next(row for row in CATALOG if row.key == "astro_germany")
    card = evidence_views(spec)["meridian_houses"]
    check_surfaces(
        monkeypatch,
        capsys,
        tmp_path,
        key,
        variant,
        card["fields"],
        {"zodiacal": zodiacal, "birth_time_uncertainty_minutes": 1},
    )
