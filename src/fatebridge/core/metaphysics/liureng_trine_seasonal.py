"""Seasonal power of a nominal completed trine, never of its individual parts."""

from __future__ import annotations

from typing import Any

from fatebridge.core.metaphysics.liureng_seasonal import MONTH_PARTITION, POWERS
from fatebridge.core.metaphysics.ren_sources import (
    JINGWEI_SCAN_SHA256,
    JINGWEI_SOURCE,
    TANYUAN_SCAN_SHA256,
    TANYUAN_SOURCE,
)

COMPONENTS = {"旺": "得势", "相": "将来", "休": "既往", "囚": "失时", "死": "失时"}


def nominal_seasonal_metadata() -> dict[str, Any]:
    return dict(
        method_id="tanyuan_nominal_trine_seasonal_component_v1",
        source_url=TANYUAN_SOURCE,
        source_sha256=TANYUAN_SCAN_SHA256,
        original_pdf_pages=[113],
        corroborating_source_url=JINGWEI_SOURCE,
        corroborating_source_sha256=JINGWEI_SCAN_SHA256,
        corroborating_pdf_pages=[159],
        month_partition_profile="declared_seasonal_month_branches_v1",
        full_named_course_adjudicated=False,
        transformation_confirmed=None,
        scope="仅在三合三支齐全时核对名义局体在已声明月建季节配置下的五态；不改变三支本五行及各自五态，不确认实际合化。课体只列探原得势、失时、将来、既往的季态组件；干枝上之量化与完整成课未裁，不以粹言得时的旺相范围替换探原得势，也不据此给现实成败或应期。",
    )


def nominal_seasonal_evidence(
    month_branch: str, nominal_element: str
) -> dict[str, Any]:
    if month_branch not in MONTH_PARTITION or nominal_element not in (
        "木",
        "火",
        "金",
        "水",
    ):
        raise ValueError("名义三合局体季态需要明确月建支和五行")
    season = MONTH_PARTITION[month_branch]
    power = POWERS[season][nominal_element]
    return dict(
        **nominal_seasonal_metadata(),
        month_branch=month_branch,
        season_partition=season,
        nominal_element=nominal_element,
        nominal_power=power,
        course_component=COMPONENTS[power],
    )
