"""Coverage, independent geographic bounds and ambiguous-name regressions."""

import importlib.util
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest
from pytz import timezone as lookup_timezone

from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.utils.places import (
    KNOWN_BIRTH_PLACE_ENTRIES,
    resolve_birth_place_context,
)
from fatebridge.utils.timezones import parse_timezone_name

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "src/fatebridge/data/places"
BY_ID = {r["id"]: r for r in KNOWN_BIRTH_PLACE_ENTRIES}


def _qualified(row):
    parent = BY_ID.get(row["parent"])
    return (_qualified(parent) if parent else "中国") + row["full_name"]


def test_published_sources_checksums_conversion_and_coverage():
    spec = importlib.util.spec_from_file_location(
        "place_builder", ROOT / "scripts/catalogs/build_place_catalog.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.audit()
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["counts"]["mainland_county_cities"] == 397
    assert manifest["counts"]["mainland_prefecture_cities"] == 293
    assert manifest["counts"]["mainland"]["city"] == 333
    assert manifest["counts"]["taiwan_admin_units"] == 390


def test_every_chinese_admin_point_resolves_with_its_complete_hierarchy():
    for row in BY_ID.values():
        if row["country"] != "CN":
            continue
        address = _qualified(row)
        result = resolve_birth_place_context(address)
        assert (result.longitude, result.latitude, result.level) == (
            row["longitude"],
            row["latitude"],
            row["level"],
        ), address


def test_world_coverage_is_separate_from_chinese_administrative_units():
    rows = [r for r in BY_ID.values() if r["country"] != "CN"]
    assert len(rows) >= 500
    counts = Counter(
        "AM" if r["continent"] in {"NA", "SA"} else r["continent"] for r in rows
    )
    assert set(counts) == {"AS", "EU", "AF", "AM", "OC"}
    assert min(counts.values()) >= 30
    for row in rows:
        assert row["coordinate_system"] == "WGS84"
        assert row["latitude"] is not None and row["longitude"] is not None
        lookup_timezone(row["timezone"])
        parse_timezone_name(row["timezone"])


def test_qualified_overseas_names_resolve_or_retain_ambiguity_without_wrong_points():
    hits = Counter()
    for row in BY_ID.values():
        if row["country"] == "CN":
            continue
        regions = [a for a in row["admin1_aliases"] if len(a) > 3 and not a.isdigit()]
        region = max(regions, key=len) if regions else ""
        address = ", ".join((row["full_name"], region, row["country"]))
        result = resolve_birth_place_context(address)
        if result.longitude is None:
            continue  # Same country/state can still contain namesakes.
        assert (result.longitude, result.latitude) == (
            row["longitude"],
            row["latitude"],
        ), address
        hits["AM" if row["continent"] in {"NA", "SA"} else row["continent"]] += 1
    assert sum(hits.values()) >= 500
    assert set(hits) == {"AS", "EU", "AF", "AM", "OC"}
    assert min(hits.values()) >= 30


@pytest.mark.parametrize(
    "place,longitude,latitude,timezone",
    [
        ("黑龙江省漠河市", 122.54, 52.97, "Asia/Shanghai"),
        ("新疆阿拉尔市", 81.28, 40.55, "Asia/Shanghai"),
        ("新疆可克达拉市", 81.04, 43.94, "Asia/Shanghai"),
        ("青海省格尔木市", 94.90, 36.41, "Asia/Shanghai"),
        ("云南省景洪市", 100.79, 22.01, "Asia/Shanghai"),
        ("广东省台山市", 112.79, 22.25, "Asia/Shanghai"),
        ("山东省海阳市", 121.16, 36.78, "Asia/Shanghai"),
        ("湖北省仙桃市", 113.45, 30.36, "Asia/Shanghai"),
        ("河南省济源市", 112.59, 35.07, "Asia/Shanghai"),
        ("海南省文昌市", 110.80, 19.54, "Asia/Shanghai"),
        ("中國臺灣彰化縣員林市", 120.58, 23.95, "Asia/Taipei"),
        ("Kathmandu, Nepal", 85.32, 27.70, "Asia/Kathmandu"),
        ("孟买, 印度", 72.88, 19.07, "Asia/Kolkata"),
        ("巴黎, 法国", 2.35, 48.85, "Europe/Paris"),
        ("Berlin, Germany", 13.41, 52.52, "Europe/Berlin"),
        ("Nairobi, Kenya", 36.82, -1.28, "Africa/Nairobi"),
        ("Cape Town, South Africa", 18.42, -33.93, "Africa/Johannesburg"),
        ("New York", -74.01, 40.71, "America/New_York"),
        ("São Paulo, Brazil", -46.64, -23.55, "America/Sao_Paulo"),
        ("悉尼, 澳大利亚", 151.21, -33.87, "Australia/Sydney"),
        ("Auckland, New Zealand", 174.76, -36.85, "Pacific/Auckland"),
    ],
)
def test_independent_geographic_bounds(place, longitude, latitude, timezone):
    result = resolve_birth_place_context(place)
    assert result.longitude == pytest.approx(longitude, abs=0.12), place
    assert result.latitude == pytest.approx(latitude, abs=0.12), place
    assert result.timezone == timezone


@pytest.mark.parametrize(
    "place,longitude,latitude",
    [
        ("北京市通州区", 116.72, 39.92),
        ("江苏省南通市通州区", 121.07, 32.07),
        ("北京市朝阳区", 116.44, 39.92),
        ("吉林省长春市朝阳区", 125.28, 43.83),
        ("河北省石家庄市长安区", 114.53, 38.04),
        ("陕西省西安市长安区", 108.90, 34.15),
        ("London, Canada", -81.23, 42.98),
        ("London, United Kingdom", -0.13, 51.51),
        ("Sydney, Nova Scotia, Canada", -60.18, 46.14),
    ],
)
def test_parent_context_disambiguates_namesakes(place, longitude, latitude):
    result = resolve_birth_place_context(place)
    assert result.longitude == pytest.approx(longitude, abs=0.08)
    assert result.latitude == pytest.approx(latitude, abs=0.08)


@pytest.mark.parametrize(
    "place", ["通州区", "朝阳区", "和平区", "江苏省广州市", "Comparison", "Readington"]
)
def test_ambiguous_conflicting_or_embedded_names_do_not_produce_coordinates(place):
    result = resolve_birth_place_context(place)
    assert result.longitude is None and result.latitude is None


@pytest.mark.parametrize(
    "place,canonical",
    [
        ("上海安亭", "上海"),
        ("河南开封", "开封"),
        ("黑龙江省齐齐哈尔市", "齐齐哈尔"),
        ("连云港市", "连云港"),
        ("南昌", "南昌"),
        ("南昌县", "南昌县"),
        ("吉林", "吉林"),
        ("北京", "北京"),
        ("peking", "北京"),
        ("suzhou", "苏州"),
        ("nanjing", "南京"),
        ("xian", "西安"),
        ("xi'an", "西安"),
        ("changzhou", "常州"),
        ("jinan", "济南"),
        ("London", "伦敦"),
        ("臺灣臺北市", "台北"),
        ("重庆开县", "开州区"),
    ],
)
def test_prefix_boundaries_and_established_aliases(place, canonical):
    assert resolve_birth_place_context(place).canonical_name == canonical


def test_city_timezone_and_explicit_coordinates_reach_the_astrology_engine():
    inferred = build_astro_birth_info(
        birth_year=2000,
        birth_month=7,
        birth_day=1,
        birth_hour=12,
        birth_place="New York",
    )
    assert inferred.timezone == "America/New_York"
    assert inferred.local_datetime.utcoffset().total_seconds() == -4 * 3600
    explicit = build_astro_birth_info(
        birth_year=2000,
        birth_month=7,
        birth_day=1,
        birth_hour=12,
        birth_place="New York",
        birth_longitude=85.324,
        birth_latitude=27.717,
        birth_timezone="Asia/Kathmandu",
    )
    assert (explicit.longitude, explicit.latitude, explicit.timezone) == (
        85.324,
        27.717,
        "Asia/Kathmandu",
    )


def test_new_catalog_zone_works_when_host_timezone_database_is_old(monkeypatch):
    import fatebridge.utils.timezones as timezones

    timezones._parse_timezone_name_cached.cache_clear()
    original = timezones.tz.gettz
    monkeypatch.setattr(
        timezones.tz,
        "gettz",
        lambda name: None if name == "America/Coyhaique" else original(name),
    )
    try:
        zone = parse_timezone_name("America/Coyhaique")
        assert (
            datetime(2026, 7, 1, tzinfo=zone).utcoffset().total_seconds() == -3 * 3600
        )
    finally:
        timezones._parse_timezone_name_cached.cache_clear()
