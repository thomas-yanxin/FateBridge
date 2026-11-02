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
from tests.canping_reading_fixture_compat import rewind_reading_context_checked
from tests.numerology_clock_input_fixture_compat import (
    rewind_clock_from_original_first_row_request,
)

FIXTURE = Path(__file__).parent / "fixtures/numerology_solar_providers_v1"
REFERENCE = json.loads((FIXTURE / "reference.json").read_bytes())
TRACE_ID = "numerology_consumed_solar_sources_v1"
CLOCK_FIXTURE = Path(__file__).parent / "fixtures/numerology_clock_metadata_v1"


def preserve_original_native_clock_metadata_checked(current, expected):
    """Qualify three added labels and their exact receipt hashes, then compare old facts."""
    reference = json.loads((CLOCK_FIXTURE / "reference.json").read_bytes())
    data = (
        Path(almanac.__file__).resolve().parents[1]
        / "data/knowledge/western-leap-seconds.json"
    )
    assert (
        hashlib.sha256(data.read_bytes()).hexdigest() == reference["leap_table_sha256"]
    )
    assert (
        hashlib.sha256(
            (
                Path(__file__).parent
                / "fixtures/canping_first_row_v1/reference.json.gz"
            ).read_bytes()
        ).hexdigest()
        == reference["original_reference_sha256"]
    )
    expiry = datetime.fromisoformat(reference["leap_table_expires_at"])
    lower = datetime.fromisoformat(reference["minimum_supported_reference_instant"])
    result = deepcopy(current)

    def receipts_hash(rows):
        return hashlib.sha256(
            json.dumps(
                rows,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()

    def contexts(output):
        return [
            output["canping_timing"]["solar_year_context"],
            output["liunian_series"]["solar_context"],
            next(
                t["facts"]
                for t in output["numerology_evidence"]["rule_trace"]
                if t["rule_id"] == "canping_actual_lichun_dependencies"
            ),
        ]

    has_boundaries = "year_boundaries" in result.get("liunian_series", {})
    if has_boundaries:
        before_hash = receipts_hash(result["liunian_series"]["year_boundaries"])
        assert all(
            c["boundary_receipts_sha256"] == before_hash for c in contexts(result)
        )
    else:
        assert result["canping_timing"]["profile_id"] == "legacy_minggong_v1"

    qualified_details = {}

    def qualify_and_remove(new, old):
        if isinstance(new, dict) and isinstance(old, dict):
            if "solar_model_details" in new and "solar_model_details" in old:
                details, prior = new["solar_model_details"], old["solar_model_details"]
                moment = datetime.fromisoformat(old["datetime_with_offset"])
                assert moment.tzinfo is not None and moment >= lower
                assert new["ephemeris_model"] == old["ephemeris_model"] == "moshier"
                assert not (set(reference["three_added_fields"]) & prior.keys())
                assert details["civil_time_policy"] == reference["policy"]
                assert details["historical_ut1_convention"] is False
                assert details["future_leap_seconds_assumed_unchanged"] is (
                    moment >= expiry
                )
                qualified_details[id(details)] = details
            for key in new.keys() & old.keys():
                qualify_and_remove(new[key], old[key])
        elif isinstance(new, list) and isinstance(old, list):
            assert len(new) == len(old)
            for a, b in zip(new, old):
                qualify_and_remove(a, b)

    qualify_and_remove(result, expected)
    # deepcopy preserves aliases between actual receipts and their rule traces.
    # Validate every occurrence first, then remove fields once per shared object.
    for details in qualified_details.values():
        for key in reference["three_added_fields"]:
            del details[key]
    if has_boundaries:
        after_hash = receipts_hash(result["liunian_series"]["year_boundaries"])
        old_hash = receipts_hash(expected["liunian_series"]["year_boundaries"])
        assert after_hash == old_hash
        assert all(
            c["boundary_receipts_sha256"] == old_hash for c in contexts(expected)
        )
        for context in contexts(result):
            context["boundary_receipts_sha256"] = old_hash
    return result


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


def preserve_original_canping_snapshot_with_source_changes_checked(current, expected):
    """Verify the new source facts before comparing every retained old fact."""
    result = rewind_reading_context_checked(
        rewind_clock_from_original_first_row_request(current, expected)
    )
    if current["canping_timing"]["profile_id"] == "legacy_minggong_v1":
        assert not any(
            t["rule_id"] == TRACE_ID
            for t in current["numerology_evidence"]["rule_trace"]
        )
        return preserve_original_native_clock_metadata_checked(result, expected)
    facts = assert_actual_source(current, "canping", "native")
    encoded = json.dumps(
        facts["source_profiles"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    assert hashlib.sha256(encoded).hexdigest() == facts["source_profiles_sha256"]
    boundaries = current["liunian_series"]["year_boundaries"]
    matched = []
    for profile in facts["source_profiles"]:
        rows = [
            (i, b)
            for i, b in enumerate(boundaries)
            if b["record"]["ephemeris_model"] == profile["ephemeris_model"]
            and b["record"]["resolution_provider"] == profile["resolution_provider"]
            and b["ephemeris_library_version"] == profile["ephemeris_library_version"]
            and b["ephemeris_retflags"] == profile["ephemeris_retflags"]
        ]
        assert len(rows) == profile["boundary_count"]
        for i, row in rows:
            details = row["record"]["solar_model_details"]
            assert all(details[k] == v for k, v in profile["model_metadata"].items())
            matched.append(i)
    assert sorted(matched) == list(range(len(boundaries)))
    policy = "canping_lichun_projection_context_v1"
    new_rule = next(
        r
        for r in result["numerology_evidence"]["rulesets"]
        if r["ruleset_id"] == policy
    )
    old_rule = next(
        r
        for r in expected["numerology_evidence"]["rulesets"]
        if r["ruleset_id"] == policy
    )
    assert old_rule["source_url"] == "https://ssd.jpl.nasa.gov/doc/de440_de441.html"
    assert new_rule["source_url"] == REFERENCE["native_documentation_url"]
    # The old snapshot's wrong citation is retained, never treated as the new truth.
    new_rule["source_url"] = old_rule["source_url"]
    result["numerology_evidence"]["rule_trace"] = [
        t
        for t in result["numerology_evidence"]["rule_trace"]
        if t["rule_id"] != TRACE_ID
    ]
    return preserve_original_native_clock_metadata_checked(result, expected)


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
