"""Independent minute-resolution HKO instants and month-boundary probes."""

import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from fatebridge.core.almanac import (
    get_bazi_month_context,
    get_bazi_year,
    get_solar_terms_for_year,
    localize_datetime,
)

ROOT = Path(__file__).parent / "fixtures/calendar_hko_v1"
REFERENCE = json.loads((ROOT / "reference.json").read_text(encoding="utf-8"))
CASES = REFERENCE["cases"]
JIE_BRANCH = dict(
    zip(
        "小寒 立春 惊蛰 清明 立夏 芒种 小暑 立秋 白露 寒露 立冬 大雪".split(),
        "丑寅卯辰巳午未申酉戌亥子",
    )
)
ZHONGQI_BRANCH = dict(
    zip(
        "大寒 雨水 春分 谷雨 小满 夏至 大暑 处暑 秋分 霜降 小雪 冬至".split(),
        "丑寅卯辰巳午未申酉戌亥子",
    )
)
MONTH_ORDER = "寅卯辰巳午未申酉戌亥子丑"


def test_official_xml_sources_remain_frozen_and_complete():
    assert len(CASES) == 72
    for source in REFERENCE["sources"]:
        assert (
            hashlib.sha256((ROOT / source["file"]).read_bytes()).hexdigest()
            == source["sha256"]
        )
        tree = ET.fromstring((ROOT / source["file"]).read_bytes())
        year = int(tree.tag.removeprefix("SolarTerms_"))
        expected = [row for row in CASES if row["year"] == year]
        published = tree.findall("Data")
        assert len(expected) == len(published) == 24
        for row, xml_row in zip(expected, published):
            at = datetime.fromisoformat(row["at"])
            assert at.month == int(xml_row.findtext("M"))
            assert at.day == int(xml_row.findtext("D"))
            assert at.strftime("%H:%M") == xml_row.findtext("hm")


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['year']}-{c['term']}")
def test_actual_solar_crossing_agrees_with_published_hko_minute(case):
    expected = datetime.fromisoformat(case["at"])
    terms = {
        t.name: t for t in get_solar_terms_for_year(case["year"], "Asia/Hong_Kong")
    }
    delta = abs((terms[case["term"]].moment - expected).total_seconds())
    assert delta <= REFERENCE["tolerance_seconds"]


@pytest.mark.parametrize("zone", ["Asia/Shanghai", "America/New_York"])
@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['year']}-{c['term']}")
def test_month_changes_at_jie_and_not_zhongqi_in_every_zone(case, zone):
    reference = datetime.fromisoformat(case["at"])
    before = localize_datetime(reference - timedelta(minutes=2), zone)
    after = localize_datetime(reference + timedelta(minutes=2), zone)
    a = get_bazi_month_context(before, zone)
    b = get_bazi_month_context(after, zone)
    if case["term"] in JIE_BRANCH:
        current = JIE_BRANCH[case["term"]]
        previous = MONTH_ORDER[(MONTH_ORDER.index(current) - 1) % 12]
        assert (a["branch"], b["branch"]) == (previous, current)
    else:
        assert a["branch"] == b["branch"] == ZHONGQI_BRANCH[case["term"]]
    if case["term"] == "立春":
        assert get_bazi_year(before, zone) == case["year"] - 1
        assert get_bazi_year(after, zone) == case["year"]
