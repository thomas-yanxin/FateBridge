"""Local-year guard roots and actually consumed Heluo solar dependencies."""

import copy
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fatebridge.core import almanac
from fatebridge.core import heluo_solar_context as source
from fatebridge.core.ephemeris_runtime import (
    configure_ephemeris_path,
    configured_ephemeris_path,
)
from fatebridge.core.heluo import solar_term
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.output_heluo_solar import HeluoSolarTermEvidence
from fatebridge.utils.errors import NumerologySourceError

ROOT = Path(__file__).parent / "fixtures"
REF = json.loads((ROOT / "heluo_solar_context_v1/reference.json").read_text())
TT = json.loads((ROOT / "ren_calendar_guard_v1/reference.json").read_text())["rows"]


@pytest.fixture(scope="module")
def empty_path(tmp_path_factory):
    return tmp_path_factory.mktemp("heluo-solar-empty")


@pytest.fixture
def model_environment(monkeypatch, empty_path):
    original = configured_ephemeris_path()
    monkeypatch.setenv("SE_EPHE_PATH", str(empty_path))
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.delenv("FATEBRIDGE_SOLAR_SPK_FILE", raising=False)
    try:
        yield
    finally:
        configure_ephemeris_path(original)


def context(at, zone):
    return solar_term(at.year, at.month, at.day, zone, birth_datetime=at)


@pytest.mark.parametrize("mode", ["auto", "de440", "analytic", "native"])
@pytest.mark.parametrize("probe", REF["civil_endpoint_probes"])
def test_endpoint_local_year_not_utc_year_and_exact_consumed_boundaries(
    mode, probe, monkeypatch, model_environment
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    at = almanac.localize_datetime(
        datetime.fromisoformat(probe["date"] + "T" + probe["time"]), probe["zone"]
    )
    actual = context(at, probe["zone"])
    c = actual["boundary_context"]
    assert at.astimezone(timezone.utc).year == probe["utc_year"]
    assert c["context_local_year"] == at.year
    assert actual["term"] == probe["term"] and actual["yang_ling"] is probe["yang_ling"]
    assert [r["role"] for r in c["dependencies"]] == [
        "current_term",
        "preceding_solstice",
        "next_four_li",
    ]
    shared = almanac.get_adjacent_solar_terms(at, probe["zone"])[0]
    assert c["dependencies"][0]["record"] == shared.as_dict()
    for row in c["dependencies"]:
        assert datetime.fromisoformat(
            row["record"]["datetime_with_offset"]
        ) == datetime.fromisoformat(row["instant_utc"])
        assert (
            row["record"]["resolution_provider"]
            == {
                "auto": "jpl_de440",
                "de440": "jpl_de440",
                "analytic": "fatebridge_analytic",
                "native": "swisseph",
            }[mode]
        )
    HeluoSolarTermEvidence.model_validate(actual)


@pytest.mark.parametrize("mode", ["auto", "de440", "analytic"])
def test_all96_preexisting_tt_roots_retained_without_selecting_by_residual(
    mode, monkeypatch, model_environment
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    expected = {(r["year"], r["index"]): r for r in TT}
    seen = set()
    for origin in [1800, 2200]:
        window = almanac._term_window(
            datetime(origin, 6, 1, tzinfo=timezone.utc), "UTC"
        )
        for t in window:
            key = (t.moment.year, almanac.SOLAR_TERM_NAMES.index(t.name))
            if key in expected:
                error = (
                    abs(
                        t.solar_model_details["selected_crossing_jd_tt"]
                        - expected[key]["jd_tt"]
                    )
                    * 86400
                )
                assert error <= REF["root_tolerance_seconds"] == 1.0
                seen.add(key)
    assert len(seen) == REF["reused_TT_roots"] == 96
    assert (
        REF["new_TT_roots"]
        == REF["new_observations"]
        == REF["new_original_horoscopes"]
        == 0
    )


@pytest.mark.parametrize("mode", ["de440", "analytic"])
@pytest.mark.parametrize("year,origin", [(1799, 1800), (2201, 2200)])
def test_guarded_cache_does_not_authorize_an_outside_public_input(
    mode, year, origin, monkeypatch, model_environment
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    context(datetime(origin, 6, 1, tzinfo=timezone.utc), "UTC")
    if mode == "de440":
        # These retained coordinates became public in the separately qualified
        # v42 profile. R68's original rejection predicates remain archived as
        # failures; positive qualification and new outside-range guards now
        # test the actual contract without rolling its coverage back.
        rules = json.loads(
            (
                ROOT / "canping_extended_projection_v1/range-expectations.json"
            ).read_bytes()
        )
        reference = ROOT / rules[
            "numeric_reference_for_retained_coordinates"
        ].removeprefix("../")
        assert (
            hashlib.sha256(reference.read_bytes()).hexdigest()
            == rules["numeric_reference_file_sha256"]
        )
        terms = almanac.get_solar_terms_for_year(year, "UTC")
        assert {t.ephemeris_model for t in terms} == {
            "fatebridge_de440_solar_extended_v1"
        }
        for r in json.loads(reference.read_bytes())["rows"]:
            if r["year"] == year:
                assert (
                    abs(
                        terms[r["index"]].solar_model_details["selected_crossing_jd_tt"]
                        - r["jd_tt"]
                    )
                    * 86400
                    <= 1.0
                )
        adjacent = almanac._solar_terms_for_context_year(year, "UTC", origin)
        assert {t.ephemeris_model for t in adjacent} == {"fatebridge_de440_solar_v1"}
        return
    with pytest.raises(ValueError, match="1800..2200"):
        almanac.get_solar_terms_for_year(year, "UTC")


@pytest.mark.parametrize("year,origin", [(1699, 1700), (2301, 2300)])
def test_current_de440_public_bounds_remain_strict_after_context_cache_warming(
    year, origin, monkeypatch, model_environment
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    context(datetime(origin, 6, 1, tzinfo=timezone.utc), "UTC")
    with pytest.raises(ValueError, match="1700..2300"):
        almanac.get_solar_terms_for_year(year, "UTC")


@pytest.mark.parametrize(
    "probe", [REF["civil_endpoint_probes"][0], REF["civil_endpoint_probes"][-1]]
)
def test_complete_birth_result_and_seasonal_consumers_share_civil_year(
    probe, monkeypatch, model_environment
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "de440")
    r = build_heluo_result(
        date=probe["date"],
        time=probe["time"],
        zone=probe["zone"],
        gender="男",
        use_true_solar_time=False,
    )
    c = r["solar_term"]["boundary_context"]
    s = r["judge"]["seasonal_numbers"]
    assert c["calendar_context_match"] is True
    assert (
        s["context_local_year"] == c["context_local_year"]
        and s["context_timezone"] == probe["zone"]
    )
    assert s["birth_instant_utc"] == c["birth_instant_utc"]
    for row in s["seasonal_windows"]:
        for edge in ["start", "end"]:
            record = row[edge + "_source"]
            assert record["ephemeris_model"] == "fatebridge_de440_solar_v1"
            assert datetime.fromisoformat(
                record["datetime_with_offset"]
            ) == datetime.fromisoformat(row[edge + "_at"])
    trace = next(
        t["facts"]
        for t in r["numerology_evidence"]["rule_trace"]
        if t["rule_id"] == source.POLICY_ID
    )
    assert trace == c
    assert "[所用节气与至点来源]" in r["snapshot_text"]


@pytest.mark.parametrize("fault", ["year", "yang", "birth", "current", "tuyong"])
def test_source_binding_rejects_known_context_or_classification_conflicts(
    fault, monkeypatch, model_environment
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    at = datetime(2026, 7, 1, tzinfo=timezone.utc)
    st = context(at, "UTC")
    calendar = {
        "timezone": "UTC",
        "current_solar_term": copy.deepcopy(
            st["boundary_context"]["dependencies"][0]["record"]
        ),
    }
    if fault == "year":
        st["boundary_context"]["context_local_year"] += 1
    elif fault == "yang":
        st["yang_ling"] = not st["yang_ling"]
    elif fault == "birth":
        st["anchor_utc"] = (at + timedelta(seconds=1)).isoformat()
    elif fault == "current":
        calendar["current_solar_term"]["name"] = "立春"
    else:
        st["tuyong"] = not st["tuyong"]
    with pytest.raises(NumerologySourceError) as err:
        source.bind_solar_context(st, calendar, at)
    assert err.value.reason == "runtime_heluo_solar_context_conflict"
    with pytest.raises(ValidationError):
        if fault == "current":
            HeluoSolarTermEvidence.model_validate(dict(st, term="立春"))
        else:
            HeluoSolarTermEvidence.model_validate(st)


def test_rough_selected_source_is_not_accepted_as_calculated(
    monkeypatch, model_environment
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    original = source._term_window
    monkeypatch.setattr(
        source,
        "_term_window",
        lambda a, z: [
            replace(
                t, resolution_provider="linear_1900_fallback", ephemeris_model="unknown"
            )
            for t in original(a, z)
        ],
    )
    with pytest.raises(NumerologySourceError):
        context(datetime(2026, 7, 1, tzinfo=timezone.utc), "UTC")


def test_reused_references_have_current_frozen_identity():
    for name, digest in REF["reused_fixture_sha256"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("fault", ["year", "birth", "source"])
def test_seasonal_and_huagong_cannot_report_different_contexts(
    fault, monkeypatch, model_environment
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "native")
    r = build_heluo_result(
        date="2000-03-07",
        time="15:33",
        zone="+08:00",
        gender="男",
        use_true_solar_time=False,
    )
    seasonal = copy.deepcopy(r["judge"]["seasonal_numbers"])
    if fault == "year":
        seasonal["context_local_year"] += 1
    elif fault == "birth":
        seasonal["birth_instant_utc"] = "2000-03-07T00:00:00+00:00"
    else:
        solstice = r["solar_term"]["boundary_context"]["dependencies"][1]["record"][
            "name"
        ]
        next(w for w in seasonal["seasonal_windows"] if w["start_term"] == solstice)[
            "start_source"
        ]["ephemeris_model"] = "unrelated_source"
    with pytest.raises(NumerologySourceError):
        source.bind_seasonal_context(r["solar_term"], seasonal)
