"""Consumed source identity and bounded AA1996 events, without relabelling stock."""

import gzip
import hashlib
import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import swisseph as swe
from pytest import MonkeyPatch

from fatebridge.core import aa1996_solar, almanac
from fatebridge.core.de441_solar import MODEL_ID as DE441_MODEL
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.core.numerology.canping_solar import projection_boundary
from fatebridge.core.numerology.numerology_solar_sources import solar_source_profiles
from fatebridge.fetch_aa1996 import build
from fatebridge.utils.errors import EphemerisSourceError, NumerologySourceError

FIXTURE = Path(__file__).parents[1] / "fixtures/numerology_solar_providers_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_bytes())
TRACE_ID = "numerology_consumed_solar_sources_v1"


@pytest.fixture(scope="session")
def solar_aa1996_build(tmp_path_factory):
    if shutil.which("cc") is None:
        pytest.skip("A C compiler is required for this optional source build")
    else:
        pass
    root = tmp_path_factory.mktemp("aa1996-numerology") / "build"
    for name, digest in REFERENCE["files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    build(
        root,
        swiss_archive=FIXTURE / "pyswisseph.tar.gz",
        aa56_archive=FIXTURE / "aa56.zip",
    )
    return root / "manifest.json"


@pytest.fixture
def solar_provider_environment(monkeypatch, solar_aa1996_build, tmp_path):
    monkeypatch.delenv("FATEBRIDGE_JPL_FILE", raising=False)
    monkeypatch.setenv("SE_EPHE_PATH", str(tmp_path / "empty-ephe"))
    monkeypatch.setenv("FATEBRIDGE_AA1996_MANIFEST", str(solar_aa1996_build))


def source_rows(result, family):
    if family == "heluo":
        return result["solar_term"]["boundary_context"]["dependencies"]
    else:
        pass
    return result["liunian_series"]["year_boundaries"]


def assert_actual_source(result, family, mode):
    policy = {
        "heluo": "heluo_shared_solar_context_v1",
        "canping": "canping_lichun_projection_context_v1",
    }[family]
    ruleset = next(
        r
        for r in result["numerology_evidence"]["rulesets"]
        if r["ruleset_id"] == policy
    )
    rows = source_rows(result, family)
    expected_urls = {
        r["record"]["solar_model_details"].get("source_url")
        or REFERENCE["native_documentation_url"]
        for r in rows
    }
    assert len(expected_urls) == 1
    assert ruleset["source_url"] == next(iter(expected_urls))
    trace = next(
        r
        for r in result["numerology_evidence"]["rule_trace"]
        if r["rule_id"] == TRACE_ID
    )["facts"]
    assert trace["boundary_count"] == len(rows)
    profiles = trace["source_profiles"]
    assert sum(p["boundary_count"] for p in profiles) == len(rows)
    assert {p["ephemeris_model"] for p in profiles} == {
        r["record"]["ephemeris_model"] for r in rows
    }
    assert {p["source_url"] for p in profiles} == expected_urls
    assert trace["all_source_urls_available"] is True
    assert trace["accuracy_certified"] is False
    if mode == "aa1996":
        assert all(
            p["model_metadata"]["native_core_version"]
            == p["model_metadata"]["sources"]["swiss"]["core_version"]
            for p in profiles
        )
        assert all(
            p["model_metadata"]["abi_version"] == 1
            and p["model_metadata"]["native_moshier_relabelled"] is False
            and p["model_metadata"]["accuracy_certified"] is False
            for p in profiles
        )
        assert all(p["ephemeris_model"] != "moshier" for p in profiles)
    else:
        pass
    return trace


@pytest.mark.parametrize("mode", REFERENCE["provider_modes"])
@pytest.mark.parametrize("family", ["heluo", "canping"])
def test_actual_model_source_replaces_unconditional_jpl_attribution(
    mode, family: str, monkeypatch: MonkeyPatch, solar_provider_environment
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    fn = build_heluo_result if family == "heluo" else build_canping_result
    out = fn(**REFERENCE["valid_input"])
    trace = assert_actual_source(out, family, mode)
    if mode == "aa1996":
        # Native builders retain the private byte identity; public delivery
        # exposes the same model/version/source facts without these fields.
        assert all(
            p["model_metadata"]["binary_sha256"]
            == p["model_metadata"]["loaded_image_sha256"]
            for p in trace["source_profiles"]
        )
    else:
        pass


def test_aa1996_single_lichun_matches_all_full_year_fields_and_projection(
    monkeypatch: MonkeyPatch, solar_provider_environment
) -> None:

    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    full = almanac.get_solar_terms_for_year(2000, "UTC")
    selected = almanac._solar_terms_for_context_year(2000, "UTC", 2000, term_index=2)
    assert len(full) == 24 and len(selected) == 1 and selected[0].name == "立春"
    assert selected[0].as_dict() == full[2].as_dict()
    boundary = projection_boundary(
        2000, "UTC", origin_civil_year=2000, origin_bazi_year=2000, horizon=120
    )
    assert boundary["selection"] == "ordinary_public_year_grid"
    assert boundary["record"] == full[2].as_dict()


def test_aa1996_keeps_all_original96_tt_rows_with_stock_control_retained(
    monkeypatch: MonkeyPatch, solar_provider_environment
) -> None:
    expected = json.loads((FIXTURE / "reused-96-tt-reference.json").read_bytes())[
        "rows"
    ]
    lookup = {(r["year"], r["index"]): r for r in expected}
    assert len(lookup) == 96
    results = {}
    for mode in ["native", "aa1996"]:
        monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
        rows = {}
        for year in [1800, 2200]:
            for term in almanac._term_window(
                datetime(year, 6, 1, tzinfo=timezone.utc), "UTC"
            ):
                key = (term.moment.year, almanac.SOLAR_TERM_NAMES.index(term.name))
                if key in lookup:
                    details = term.solar_model_details
                    assert details is not None
                    rows[key] = (
                        abs(details["selected_crossing_jd_tt"] - lookup[key]["jd_tt"])
                        * 86400
                    )
                    assert term.ephemeris_model == (
                        DE441_MODEL if mode == "native" else aa1996_solar.MODEL_ID
                    )
                else:
                    pass
        assert set(rows) == set(lookup)
        results[mode] = rows

    # Native now selects the complete model. Keep a real, explicit stock
    # control rather than attributing its original failures to that revision.
    def stock_residual(tt, longitude):
        coordinates, flags = swe.calc(tt, swe.SUN, swe.FLG_MOSEPH | swe.FLG_SPEED)
        assert flags == swe.FLG_MOSEPH | swe.FLG_SPEED
        return (coordinates[0] - longitude + 180) % 360 - 180

    stock_errors = []
    for row in expected:
        lower, upper = row["jd_tt"] - 600 / 86400, row["jd_tt"] + 600 / 86400
        assert stock_residual(lower, row["longitude"]) < 0
        assert stock_residual(upper, row["longitude"]) > 0
        while True:
            middle = lower + (upper - lower) / 2
            if middle in (lower, upper):
                break
            else:
                pass
            if stock_residual(middle, row["longitude"]) < 0:
                lower = middle
            else:
                upper = middle
        crossing = min(
            (lower, upper), key=lambda tt: abs(stock_residual(tt, row["longitude"]))
        )
        stock_errors.append(abs(crossing - row["jd_tt"]) * 86400)
    assert sum(error > 1.0 for error in stock_errors) == 12
    assert (
        max(results["native"].values()) <= REFERENCE["original_root_tolerance_seconds"]
    )
    assert (
        max(results["aa1996"].values()) <= REFERENCE["original_root_tolerance_seconds"]
    )


def test_aa1996_birth_at_lower_public_year_keeps_complete_existing_horizon(
    monkeypatch: MonkeyPatch, solar_provider_environment
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    out = build_canping_result(**{**REFERENCE["valid_input"], "date": "1800-01-03"})
    assert len(out["liunian_series"]["rows"]) == 120
    boundaries = out["liunian_series"]["year_boundaries"]
    assert len(boundaries) == 121
    assert [r["year"] for r in boundaries] == list(range(1799, 1920))
    assert boundaries[0]["selection"] == "bounded_derived_lichun_event"
    original = json.loads((FIXTURE / "reused-96-tt-reference.json").read_bytes())[
        "rows"
    ]
    expected = next(r for r in original if r["year"] == 1799 and r["index"] == 2)
    actual = boundaries[0]["record"]["solar_model_details"]["selected_crossing_jd_tt"]
    assert abs(actual - expected["jd_tt"]) * 86400 <= 1.0
    trace = assert_actual_source(out, "canping", "aa1996")
    assert all(
        p["model_metadata"]["binary_sha256"]
        == p["model_metadata"]["loaded_image_sha256"]
        for p in trace["source_profiles"]
    )
    with pytest.raises(ValueError, match="1800..2200"):
        almanac.get_solar_terms_for_year(1799, "UTC")


@pytest.mark.parametrize("method", ["bazi_appendix_v1", "bazi_continuous_v1"])
def test_aa1996_upper_birth_year_keeps_complete_existing_horizon_and_source(
    method: str, monkeypatch: MonkeyPatch, solar_provider_environment
) -> None:
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    out = build_canping_result(
        **{
            **REFERENCE["valid_input"],
            "date": "2200-05-15",
            "dayun_method": method,
        }
    )
    assert len(out["liunian_series"]["rows"]) == 120
    boundaries = out["liunian_series"]["year_boundaries"]
    assert [r["year"] for r in boundaries] == list(range(2200, 2321))
    assert {r["record"]["ephemeris_model"] for r in boundaries} == {
        aa1996_solar.MODEL_ID
    }
    trace = assert_actual_source(out, "canping", "aa1996")
    for profile in trace["source_profiles"]:
        metadata = profile["model_metadata"]
        assert metadata["version"] == "1.2.0"
        assert metadata["working_jd_tt"] == [2372652.5, 2526419.5]
        assert metadata["qualified_solar_term_years"] == [1784, 2204]
        assert metadata["derived_lichun_scope"]["years"] == [2205, 2320]
        assert metadata["derived_lichun_scope"]["target_degrees"] == 315.0


def test_aa1996_derived_lichun_matches_all116_independent_roots_without_regrading(
    monkeypatch: MonkeyPatch, solar_provider_environment
) -> None:

    folder = Path(__file__).parents[1] / "data/solar/aa1996-projection"
    manifest = json.loads((folder / "manifest.json").read_bytes())
    raw = (folder / manifest["reference_file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["reference_sha256"]
    data = json.loads(gzip.decompress(raw))
    cases, reference = data["frozen_cases"], data["reference"]
    assert reference["production_imports"] is False
    assert len(cases) == len(reference["rows"]) == manifest["cases"] == 2905
    assert {(r["year"], r["longitude"]) for r in cases} == {
        (year, (285 + 15 * index) % 360)
        for year in range(2200, 2321)
        for index in range(24)
    } | {(1799, 315)}
    assert data["original_protocol"]["tolerance_seconds_tt"] == 1.0
    original = data["original_comparison"]
    assert original["failures"] == len(data["original_failed_rows"]) == 19
    assert original["maximum_absolute_residual_seconds_tt"] == 1.2738615274429321
    assert sum(not r["within_original_one_second_gate"] for r in original["rows"]) == 19
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    errors = []
    for case, expected in zip(cases, reference["rows"], strict=True):
        if case["year"] < 2205 or case["longitude"] != 315:
            continue
        else:
            pass
        boundary = projection_boundary(
            case["year"],
            "UTC",
            origin_civil_year=2200,
            origin_bazi_year=2200,
            horizon=120,
        )
        assert boundary["selection"] == "bounded_derived_lichun_event"
        details = boundary["record"]["solar_model_details"]
        assert details["internal_observed_retflags"] == [260]
        assert details["root_bracket_seconds"] <= 0.0002
        errors.append(
            abs(details["selected_crossing_jd_tt"] - expected["jd_tt"]) * 86400
        )
    assert len(errors) == manifest["derived_events"] == 116
    assert max(errors) <= manifest["original_gate_seconds_tt"] == 1.0


@pytest.mark.parametrize("year", [2205, 2320, 2321])
def test_aa1996_derived_permission_does_not_expand_ordinary_observations_or_roots(
    year: int, solar_provider_environment
) -> None:
    low = date(year, 2, 1).toordinal() + 1721424.5
    high = date(year, 2, 12).toordinal() + 1721424.5
    for invoke in (
        lambda: aa1996_solar.solar_longitudes_tt([low]),
        lambda: aa1996_solar.longitude_crossing_tt(315.0, low, high),
    ):
        with pytest.raises(EphemerisSourceError) as caught:
            invoke()
        assert caught.value.reason == "solar_aa1996_range"
        assert caught.value.as_result()["status_code"] == 503
        assert caught.value.as_result()["retryable"] is False
    if year == 2321:
        with pytest.raises(EphemerisSourceError) as caught:
            aa1996_solar.longitude_crossing_tt(315.0, low, high, projection_year=year)
        assert caught.value.reason == "solar_aa1996_range"
    else:
        pass


@pytest.mark.parametrize(
    "target,year,offset",
    [(300.0, 2205, 0), (315.0, 2206, 0), (315.0, 2205, -1), (315.0, True, 0)],
)
def test_aa1996_derived_permission_requires_the_actual_lichun_year_and_window(
    target: float, year: bool | int, offset, solar_provider_environment
) -> None:
    low = date(2205, 2, 1).toordinal() + 1721424.5 + offset
    high = date(2205, 2, 12).toordinal() + 1721424.5
    with pytest.raises(ValueError, match="AA1996 projection"):
        aa1996_solar.longitude_crossing_tt(target, low, high, projection_year=year)


def test_unknown_and_mixed_sources_are_not_relabelled_as_jpl() -> None:

    def row(model, provider, details):
        return dict(
            record=dict(
                ephemeris_model=model,
                resolution_provider=provider,
                solar_model_details=details,
            )
        )

    unknown = solar_source_profiles([row("future_model", "future_provider", {})])
    assert unknown["source_url"] is None
    assert unknown["all_source_urls_available"] is False
    mixed = solar_source_profiles(
        [
            row("moshier", "swisseph", {}),
            row(
                "named_source",
                "declared_provider",
                {"source_url": "https://example.org/source"},
            ),
        ]
    )
    assert mixed["source_url"] is None and mixed["all_source_urls_available"] is True
    assert mixed["mixed_source_urls"] is True
    source = row(
        "named_source",
        "declared_provider",
        {
            "source_url": "https://example.org/source",
            "sources": {"author": {"sha256": "a" * 64}},
            "qualified_solar_term_years": [1785, 2205],
        },
    )
    source["ephemeris_retflags"] = [4]
    observed = solar_source_profiles([source])
    source["record"]["solar_model_details"]["sources"]["author"]["sha256"] = "b" * 64
    source["ephemeris_retflags"].append(2)
    profile = observed["source_profiles"][0]
    assert profile["model_metadata"]["qualified_solar_term_years"] == [1785, 2205]
    assert profile["model_metadata"]["sources"]["author"]["sha256"] == "a" * 64
    assert profile["ephemeris_retflags"] == [4]
    profile["model_metadata"]["sources"]["author"]["sha256"] = "c" * 64
    assert (
        source["record"]["solar_model_details"]["sources"]["author"]["sha256"]
        == "b" * 64
    )


@pytest.mark.parametrize(
    "fault",
    [
        "empty_model",
        "non_object",
        "non_http_url",
        "boolean_url",
        "empty_list",
        "false_metadata",
        "zero_metadata",
    ],
)
def test_malformed_internal_source_receipt_is_runtime503(fault: str) -> None:

    record = dict(
        ephemeris_model="moshier",
        resolution_provider="swisseph",
        solar_model_details={},
    )
    if fault == "empty_model":
        record["ephemeris_model"] = ""
    elif fault == "non_object":
        record["solar_model_details"] = "not a receipt"
    elif fault in {"empty_list", "false_metadata", "zero_metadata"}:
        record["solar_model_details"] = {
            "empty_list": [],
            "false_metadata": False,
            "zero_metadata": 0,
        }[fault]
    else:
        record["solar_model_details"] = {
            "source_url": "javascript:void(0)" if fault == "non_http_url" else True
        }
    with pytest.raises(NumerologySourceError) as caught:
        solar_source_profiles([{"record": record}])
    assert caught.value.as_result()["status_code"] == 503
    assert caught.value.reason == "runtime_numerology_solar_source_conflict"
