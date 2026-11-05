"""Consumed source identity and bounded AA1996 events, without relabelling stock."""

import hashlib
import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fatebridge.core import aa1996_solar, almanac
from fatebridge.core.local_techniques.canping import build_canping_result
from fatebridge.core.local_techniques.heluo import build_heluo_result
from fatebridge.fetch_aa1996 import build
from fatebridge.utils.errors import EphemerisSourceError

FIXTURE = Path(__file__).parents[1] / "fixtures/numerology_solar_providers_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_bytes())
TRACE_ID = "numerology_consumed_solar_sources_v1"


@pytest.fixture(scope="session")
def solar_aa1996_build(tmp_path_factory):
    if shutil.which("cc") is None:
        pytest.skip("A C compiler is required for this optional source build")
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
            p["model_metadata"]["binary_sha256"]
            == p["model_metadata"]["loaded_image_sha256"]
            for p in profiles
        )
        assert all(p["ephemeris_model"] != "moshier" for p in profiles)
    return trace


@pytest.mark.parametrize("mode", REFERENCE["provider_modes"])
@pytest.mark.parametrize("family", ["heluo", "canping"])
def test_actual_model_source_replaces_unconditional_jpl_attribution(
    mode, family, monkeypatch, solar_provider_environment
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", mode)
    fn = build_heluo_result if family == "heluo" else build_canping_result
    out = fn(**REFERENCE["valid_input"])
    assert_actual_source(out, family, mode)


def test_aa1996_keeps_all_original96_tt_rows_with_stock_control_retained(
    monkeypatch, solar_provider_environment
):
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
                        "moshier" if mode == "native" else aa1996_solar.MODEL_ID
                    )
        assert set(rows) == set(lookup)
        results[mode] = rows
    # A failure of the stock provider is preserved as negative evidence.
    assert sum(e > 1.0 for e in results["native"].values()) == 12
    assert (
        max(results["aa1996"].values()) <= REFERENCE["original_root_tolerance_seconds"]
    )


def test_aa1996_birth_at_lower_public_year_keeps_complete_existing_horizon(
    monkeypatch, solar_provider_environment
):
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
    assert_actual_source(out, "canping", "aa1996")
    with pytest.raises(ValueError, match="1800..2200"):
        almanac.get_solar_terms_for_year(1799, "UTC")


def test_unavailable_aa1996_projection_is_runtime503_without_partial_horizon(
    monkeypatch, solar_provider_environment
):
    monkeypatch.setenv("FATEBRIDGE_SOLAR_TERM_MODEL", "aa1996")
    with pytest.raises(EphemerisSourceError) as caught:
        build_canping_result(**{**REFERENCE["valid_input"], "date": "2200-05-15"})
    assert caught.value.reason == "solar_aa1996_range"
    assert caught.value.as_result()["status_code"] == 503
    assert caught.value.as_result()["retryable"] is False


def test_unknown_and_mixed_sources_are_not_relabelled_as_jpl():
    from fatebridge.core.numerology_solar_sources import solar_source_profiles

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
def test_malformed_internal_source_receipt_is_runtime503(fault):
    from fatebridge.core.numerology_solar_sources import solar_source_profiles
    from fatebridge.utils.errors import NumerologySourceError

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
