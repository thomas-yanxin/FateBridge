"""Second-round counterexamples: unequal sky mansions and source conflicts."""

import csv
import hashlib
import io
import json
import math
from datetime import datetime
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime, guolao
from fatebridge.core.astro import runtime
from fatebridge.core.astro.birth import build_astro_birth_info
from fatebridge.core.local_techniques.suzhan import _build_suzhan_snapshot_text
from fatebridge.core.sukuyo import calendar_mansion, day_evidence
from fatebridge.core.sukuyo_activities import source_bundle
from fatebridge.core.suzhan_astronomy import build_equatorial_mansions
from fatebridge.services.divination import calculate_suzhan_analysis

FIXTURES = Path(__file__).parents[1] / "data"


def test_all_42_physical_ra_dec_positions_against_external_jpl(monkeypatch):
    fixture = json.loads((FIXTURES / "sukuyo-equatorial-horizons.json").read_text())
    outputs = {}
    errors = []
    # Ensure tests exercise the guaranteed file-free ephemeris, not a local
    # repository installation of more accurate planetary files.
    monkeypatch.setattr(
        ephemeris_runtime, "_configured_path", "/tmp/fatebridge-sukuyo-no-se1"
    )
    monkeypatch.delenv("SE_EPHE_PATH", raising=False)
    for ref in fixture["references"]:
        assert (
            hashlib.sha256(ref["response"]["result"].encode()).hexdigest()
            == ref["response_sha256"]
        )
        assert ref["parameters"]["QUANTITIES"] == "'2,31,49'"
        table = ref["response"]["result"].split("$$SOE\n", 1)[1].split("$$EOE", 1)[0]
        raw_rows = list(csv.reader(io.StringIO(table)))
        assert len(raw_rows) == len(ref["rows"])
        for raw, parsed in zip(raw_rows, ref["rows"]):
            assert float(raw[3]) == parsed["right_ascension"]
            assert float(raw[4]) == parsed["declination"]
            assert datetime.strptime(
                raw[0].strip(), "%Y-%b-%d %H:%M:%S.%f"
            ) == datetime.fromisoformat(parsed["utc"]).replace(tzinfo=None)
        for row in ref["rows"]:
            d = datetime.fromisoformat(row["utc"])
            if row["utc"] not in outputs:
                outputs[row["utc"]] = build_equatorial_mansions(
                    build_astro_birth_info(
                        birth_year=d.year,
                        birth_month=d.month,
                        birth_day=d.day,
                        birth_hour=d.hour,
                        birth_minute=d.minute,
                        birth_second=d.second,
                        birth_timezone="UTC",
                        birth_longitude=0,
                        birth_latitude=0,
                    )
                )
            actual = next(
                p for p in outputs[row["utc"]]["bodies"] if p["id"] == ref["body"]
            )
            ra = (
                abs(
                    (actual["right_ascension"] - row["right_ascension"] + 180) % 360
                    - 180
                )
                * 3600
            )
            dec = abs(actual["declination"] - row["declination"]) * 3600
            assert max(ra, dec) <= fixture["tolerance_arcseconds"], (
                ref["body"],
                row["utc"],
                ra,
                dec,
            )
            errors.append(max(ra, dec))
    assert len(errors) == 42


def test_default_sky_mansion_is_not_the_calendrical_natal_mansion():
    r = calculate_suzhan_analysis(date="2025-03-04", time="12:00:00", zone="+08:00")
    moon = next(p for p in r["chart"]["objects"] if p["id"] == "Moon")
    assert r["sukuyo"]["day_mansion"] == "毕"
    assert moon["su28"] == "娄" and r["astronomy"]["coordinate_frame"].startswith(
        "geocentric_apparent"
    )
    assert not r["astronomy"]["classical_boundary_acceptance"]
    assert len(r["astronomy"]["boundaries"]) == 28
    widths = [p["mansion"]["mansion_width"] for p in r["astronomy"]["bodies"]]
    assert max(widths) - min(widths) > 5  # Counterexample to 360/28.
    assert (
        next(p for p in r["chart"]["objects"] if p["id"] == "Uranus").get("su28")
        is None
    )


def test_houses_zodiac_and_location_cannot_shift_geocentric_mansions():
    a = calculate_suzhan_analysis(
        date="2025-03-04",
        time="12:00:00",
        zone="+08:00",
        hsys=8,
        zodiacal=0,
        gps_lat=31,
        gps_lon=121,
    )
    b = calculate_suzhan_analysis(
        date="2025-03-04",
        time="04:00:00",
        zone="UTC",
        hsys=0,
        zodiacal=1,
        gps_lat=-33,
        gps_lon=-70,
    )
    assert a["astronomy"] == b["astronomy"]
    assert a["chart"]["houses"] != b["chart"]["houses"]
    assert a["sukuyo"]["day_mansion"] == b["sukuyo"]["day_mansion"]


def test_declared_boundaries_use_exact_half_open_intervals():
    birth = build_astro_birth_info(
        birth_year=2025,
        birth_month=3,
        birth_day=4,
        birth_hour=4,
        birth_timezone="UTC",
        birth_latitude=0,
        birth_longitude=0,
    )
    a = build_equatorial_mansions(birth)
    edges = sorted(a["boundaries"], key=lambda b: b["right_ascension"])
    for index, edge in enumerate(edges):
        ra = edge["right_ascension"]
        assert guolao.mansion_at(ra, edges)["su28"] == edge["su28"]
        assert (
            guolao.mansion_at(math.nextafter(ra, -math.inf), edges)["su28"]
            == edges[index - 1]["su28"]
        )


def test_mansion_snapshot_can_display_more_than_30_degrees():
    payload = {"date": "2025-03-04", "time": "12:00:00", "zone": "+08:00"}
    result = {
        "chart": {
            "houses": [{"id": "House1"}],
            "objects": [
                {
                    "house": "House1",
                    "id": "Moon",
                    "lon": 123.0,
                    "su28": "井",
                    "su28_degree": 32.2,
                }
            ],
        },
        "params": {"su28Method": "modern_equatorial_research_anchors_v1"},
    }
    text = _build_suzhan_snapshot_text(payload, result)
    assert "32˚井" in text and "2˚井" not in text.replace("32˚井", "")


def test_legacy_diagram_requires_explicit_method_and_remains_labelled():
    r = calculate_suzhan_analysis(
        date="2025-03-04", time="12:00:00", mansion_method="legacy_equal28"
    )
    assert r["astronomy"] is None
    assert r["params"]["su28Method"] == "legacy_equal_ecliptic28_illustration"
    assert "旧版等分黄道示意" in r["snapshot_text"]


def test_missing_physical_engine_does_not_fabricate_equal_sky_mansions(monkeypatch):
    monkeypatch.setattr(runtime, "swe", None)
    r = calculate_suzhan_analysis(date="2025-03-04", time="12:00:00")
    assert r["error_code"] == "dependency_missing" and "astronomy" not in r


def test_danger_marriage_preserves_both_contradictory_lower_volume_clauses():
    r = day_evidence(calendar_mansion("2025-03-04"), "奎", "marriage")
    assert r["personal_day"]["relation"]["relation"] == "危"
    assert r["personal_day"]["textual_conflict"]
    assessment = r["activity_assessment"]
    assert assessment["evidence_status"] == "conflicted"
    assert (
        next(x for x in assessment["layers"] if x["layer"] == "sanjiu")["status"]
        == "conflicted"
    )
    lower = [
        x
        for x in assessment["matched_rules"]
        if x["volume"] == "lower" and x["layer"] == "sanjiu"
    ]
    assert {x["assessment"] for x in lower} == {"favorable", "caution"}
    assert {x["locator"] for x in lower} == {
        "T21n1299_p0398a02",
        "T21n1299_p0398a09-10",
    }
    assert any(
        x["locator"] == "T21n1299_p0394b03-05" and x["layer"] == "named_day"
        for x in assessment["matched_rules"]
    )


def test_day_nature_and_sanjiu_can_disagree_without_a_composite_score():
    r = day_evidence(calendar_mansion("2025-03-04"), "女", "study")
    assert r["personal_day"]["relation"]["relation"] == "業"
    assert r["activity_assessment"]["evidence_status"] == "conflicted"
    assert "score" not in r["activity_assessment"]
    assert "probability" not in r["activity_assessment"]


def test_unspecified_or_uncovered_rules_do_not_become_negative_evidence():
    r = day_evidence(
        {
            "natal_su27": "参",
            "calendar_date": "2025-03-04",
            "calendar_timezone": "UTC+08:00",
            "lunar_day": 5,
        },
        None,
        "study",
    )
    assert r["activity_assessment"]["evidence_status"] == "uncovered"
    assert (
        next(x for x in r["activity_assessment"]["layers"] if x["layer"] == "sanjiu")[
            "status"
        ]
        == "not_evaluated"
    )
    with pytest.raises(ValueError):
        day_evidence(calendar_mansion("2025-03-04"), None, "medical")


def test_activity_source_rows_have_unique_ids_and_precise_scope():
    bundle = source_bundle()
    rules = bundle["rules"]
    assert len(rules) == len({x["rule_id"] for x in rules}) == 31
    assert all(x["locator"].startswith("T21n1299_p") for x in rules)
    # 月曜's 私情出行 is not silently converted into all business travel.
    assert not any(
        "travel" in r["activities"]
        for r in rules
        if r["layer"] == "weekday" and r["selectors"] == ["月"]
    )


def test_activity_mapping_against_ten_independent_primary_source_clauses():
    fixture = json.loads(
        (FIXTURES / "sukuyo-activity-primary-excerpts.json").read_text()
    )
    assert fixture["source_sha256"] == source_bundle()["source_sha256"]

    def interval(locator):
        parts = locator.removeprefix("T21n1299_p").split("-")
        start = parts[0]
        end = parts[-1]
        if len(end) == 2:
            end = start[:-2] + end
        return start, end

    for case in fixture["cases"]:
        assert case["verified_excerpt"] in case["text"]
        a, b = interval(case["locator"])
        candidates = [
            r
            for r in source_bundle()["rules"]
            if case["activity"] in r["activities"]
            and r["assessment"] == case["assessment"]
            and interval(r["locator"])[0] <= a
            and interval(r["locator"])[1] >= b
        ]
        assert candidates, case
