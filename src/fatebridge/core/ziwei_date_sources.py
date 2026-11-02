"""Date-table implementation provenance is distinct from a printed date witness."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast

from fatebridge.core.almanac import LUNAR_YEAR_INFO_CORRECTIONS

LIBRARY_ADAPTER = "fatebridge_lunardate_adapter_v1"


@lru_cache(maxsize=1)
def _references() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-calendar-references.json")
            .read_text(encoding="utf-8")
        )["references"],
    )


def date_conversion_provenance(
    labels: dict[str, str], contexts: dict[str, Any]
) -> dict[str, Any]:
    """Attribute each actual date label separately, including unsupported labels."""
    lookups: dict[str, Any] = {}
    sources: dict[str, Any] = {}
    witnesses: dict[str, Any] = {}
    for clock, label in labels.items():
        solar = date.fromisoformat(label)
        lunar = contexts[clock]
        reference_id = (
            "tam_1900"
            if solar.year == 1900
            else "hko_1901_2100" if 1901 <= solar.year <= 2100 else None
        )
        provider = None
        year_info_override = None
        if lunar:
            source = lunar.get("conversion_source")
            if source:
                provider = source.get("method_id") or "unidentified_supplement"
                sources[provider] = deepcopy(source)
            else:
                provider = LIBRARY_ADAPTER
                sources[provider] = dict(
                    method_id=provider,
                    publisher="FateBridge",
                    title="lunardate库表适配及已登记年信息修正",
                    implementation="fatebridge.core.almanac._lunar_date_from_solar",
                    upstream="lunardate",
                    correction_registry="fatebridge.core.almanac.LUNAR_YEAR_INFO_CORRECTIONS",
                )
                year = lunar.get("year")
                if year in LUNAR_YEAR_INFO_CORRECTIONS:
                    year_info_override = (
                        f"{year}:{LUNAR_YEAR_INFO_CORRECTIONS[year]:#x}"
                    )
        if reference_id:
            witnesses[reference_id] = deepcopy(_references()[reference_id])
        lookups[clock] = dict(
            solar_date=label,
            status="available" if lunar else "unavailable",
            implementation_provider=provider,
            printed_date_reference=reference_id,
            applied_year_info_correction=year_info_override,
        )
    return dict(
        method_id="ziwei_date_conversion_provenance_v1",
        lookups=lookups,
        implementation_sources=sources,
        printed_date_references=witnesses,
        implementation_data_is_independent_validation=False,
        historical_clock_policy_verified=False,
    )
