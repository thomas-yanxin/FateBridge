"""Actual Swiss file contexts, analytical fallback, and source-coherent grids."""

import copy
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from fatebridge.core import ephemeris_runtime as e
from fatebridge.core.astro import ephemeris, physical_sources
from fatebridge.core.astro.midpoints import PHYSICAL_BODIES, _native_factors
from fatebridge.core.astro.orbits import ORBITAL_MODEL, ApproximateEphemeris
from fatebridge.core.astro.physical_sources import (
    PhysicalEphemerisTrace,
    PhysicalSourceCohort,
)
from fatebridge.core.astro.sensitivity import time_sensitivity
from fatebridge.core.astro.time_scales import datetime_from_tt
from fatebridge.utils.errors import EphemerisSourceError
from tests.support.transports import rest as rest
from tests.support.transports import surface_calls as surface_calls
from tests.unit_test.fixtures.western_ephemeris import birth
from tests.unit_test.fixtures.western_ephemeris import (
    ephemeris_files as ephemeris_files,
)
from tests.unit_test.fixtures.western_ephemeris import (
    restore_configuration as restore_configuration,
)

pytestmark = pytest.mark.skipif(e.swe is None, reason="Swiss Ephemeris required")


def edge_birth(directory):
    e.configure_ephemeris_path(str(directory))
    e.ephemeris_call("calc", 2451545.0, e.swe.SUN, e.swe.FLG_SWIEPH)
    # This is a data-coverage regression, not an independent astronomical epoch.
    edge = e.swe.get_current_file_data(0)[2]
    return birth(datetime_from_tt(edge))


def test_actual_se1_headers_hashes_and_factor_references(ephemeris_files) -> None:
    _, directory = ephemeris_files
    e.configure_ephemeris_path(str(directory))
    result = _native_factors(birth(), False, include_hypothetical=False)
    source = result["physical_ephemeris_source"]
    assert set(source["by_factor"]) == set(PHYSICAL_BODIES)
    assert {f["filename"] for f in source["files"]} == {"sepl_18.se1", "semo_18.se1"}
    ids = {f["id"] for f in source["files"]}
    for row in source["files"]:
        path, start, end, de_number = e.swe.get_current_file_data(row["slot"])
        assert row["filename"] == Path(path).name
        assert row["sha256"] == hashlib.sha256(Path(path).read_bytes()).hexdigest()
        assert (
            row["start_julian_day_tt"],
            row["end_julian_day_tt"],
            row["de_number"],
        ) == (start, end, de_number)
        assert row["matches_packaged_manifest"] is True
        assert row["de_number"] > 0
    for row in source["by_factor"].values():
        assert row["model"] == "swieph"
        assert row["status"] == "se1_contexts_observed"
        assert row["file_ids"] and set(row["file_ids"]) <= ids
    assert str(directory) not in json.dumps(source)
    assert source["atomic_file_read_proven"] is False
    assert source["accuracy_certified"] is False


@pytest.mark.parametrize(
    "model,status",
    [("moshier", "library_builtin"), (ORBITAL_MODEL, "packaged_analytic_model")],
)
def test_analytical_fallback_never_claims_stale_file_contexts(
    ephemeris_files, model, status: str
) -> None:
    _, directory = ephemeris_files
    e.configure_ephemeris_path(str(directory))
    e.ephemeris_call("calc", 2451545.0, e.swe.SUN, e.swe.FLG_SWIEPH)
    assert e.swe.get_current_file_data(0)[0]
    if model == "moshier":
        e.ephemeris_call("calc", 2451545.0, e.swe.NEPTUNE, e.swe.FLG_MOSEPH)
    else:
        ApproximateEphemeris(2451545.0, 2451545.0).state("Neptune")
    trace = PhysicalEphemerisTrace()
    trace.observe("Neptune", model)
    result = trace.finish()
    assert result["files"] == []
    assert result["by_factor"]["Neptune"] == {
        "model": model,
        "status": status,
        "file_ids": [],
    }


def test_missing_file_introspection_is_unavailable_not_invented(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(e.swe, "get_current_file_data")
    trace = PhysicalEphemerisTrace()
    trace.observe("Sun", "swieph")
    source = trace.finish()
    assert source["files"] == []
    assert source["by_factor"]["Sun"]["status"] == "identity_unavailable"
    assert source["has_unidentified_sources"] is True


def test_file_mutation_after_first_observation_is_rejected(
    ephemeris_files, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, directory = ephemeris_files
    e.configure_ephemeris_path(str(directory))
    original = e.swe.calc

    def mutate_after_moon(*args, **kwargs):
        value = original(*args, **kwargs)
        if args[1] == e.swe.MOON:
            path = directory / "sepl_18.se1"
            path.write_bytes(path.read_bytes() + b"changed-after-first-observation")
        else:
            pass
        return value

    monkeypatch.setattr(e.swe, "calc", mutate_after_moon)
    with pytest.raises(ValueError, match="Physical ephemeris file changed during"):
        _native_factors(birth(), False, include_hypothetical=False)


def test_real_partial_coverage_cannot_be_called_pure_time_sensitivity(
    ephemeris_files,
) -> None:
    _, directory = ephemeris_files
    center = edge_birth(directory)
    with pytest.raises(
        EphemerisSourceError, match="Physical ephemeris model changed across"
    ):
        time_sensitivity(
            center, sidereal=False, uncertainty_minutes=1, include_hypothetical=False
        )


def test_complete_adjacent_segments_preserve_the_whole_declared_interval(
    ephemeris_files,
) -> None:
    source, directory = ephemeris_files
    center = edge_birth(directory)
    for name in ("sepl_24.se1", "semo_24.se1"):
        shutil.copy2(source / name, directory / name)
    result = time_sensitivity(
        center, sidereal=False, uncertainty_minutes=1, include_hypothetical=False
    )
    assert result["status"] == "sampled" and result["sample_count"] == 5
    assert result["physical_ephemeris_models_consistent"] is True
    assert result["represented_radius_seconds"] == 60
    contexts = result["physical_ephemeris_sources"]
    assert len(contexts) >= 2
    assert {r["filename"] for s in contexts for r in s["files"]} >= {
        "sepl_18.se1",
        "sepl_24.se1",
    }
    for sample in result["samples"]:
        assert all(
            r["model"] == "swieph"
            for r in contexts[sample["physical_source_index"]]["by_factor"].values()
        )


def sample_source():
    return {
        "by_factor": {"Sun": {"model": "swieph"}, "Moon": {"model": "moshier"}},
        "files": [
            {"slot": 0, "filename": "sepl_18.se1", "sha256": "a" * 64, "de_number": 441}
        ],
    }


def test_per_factor_model_swaps_are_detected_even_if_aggregate_set_is_equal() -> None:
    first = sample_source()
    second = copy.deepcopy(first)
    second["by_factor"] = {"Sun": {"model": "moshier"}, "Moon": {"model": "swieph"}}
    assert {r["model"] for r in first["by_factor"].values()} == {
        r["model"] for r in second["by_factor"].values()
    }
    cohort = PhysicalSourceCohort()
    cohort.add(first)
    with pytest.raises(ValueError, match="model changed across"):
        cohort.add(second)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("de_number", 431, "DE header editions"),
        ("sha256", "b" * 64, "file changed across"),
    ],
)
def test_same_model_label_cannot_hide_changed_data(
    field: str, value, message: str
) -> None:
    first = sample_source()
    second = copy.deepcopy(first)
    second["files"][0][field] = value
    cohort = PhysicalSourceCohort()
    cohort.add(first)
    with pytest.raises(ValueError, match=message):
        cohort.add(second)


def test_adjacent_segment_with_the_same_edition_is_allowed() -> None:
    first = sample_source()
    second = copy.deepcopy(first)
    second["files"][0].update(filename="sepl_24.se1", sha256="b" * 64)
    cohort = PhysicalSourceCohort()
    assert cohort.add(first) == 0
    assert cohort.add(second) == 1
    assert cohort.add(copy.deepcopy(second)) == 1


def test_nominal_and_sampled_models_must_also_agree(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fatebridge.core.astro import sensitivity

    first = sample_source()
    second = copy.deepcopy(first)
    second["by_factor"]["Sun"]["model"] = "moshier"
    monkeypatch.setattr(
        sensitivity,
        "time_sensitivity",
        lambda *args, **kwargs: {
            "status": "sampled",
            "hypothetical_element_source": {},
            "physical_ephemeris_sources": [second],
        },
    )
    payload = {
        "base_chart": {"chart_profile": {"zodiac": "tropical"}},
        "midpoint_analysis": {
            "profile": {
                "hypothetical_element_source": {},
                "physical_ephemeris_source": first,
            }
        },
    }
    with pytest.raises(ValueError, match="model changed across"):
        sensitivity.enrich_specialty_sensitivity(
            payload, birth(), kind="germany", uncertainty_minutes=1
        )


@pytest.mark.parametrize(
    "key,variant",
    [
        ("astro_germany", None),
        ("astro_chart", "germany"),
        ("astro_chart13", None),
        ("astro_chart", "chart13"),
    ],
)
def test_partial_data_error_and_complete_interval_across_three_surfaces(
    ephemeris_files,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    variant: str | None,
    surface_calls,
) -> None:
    from fatebridge.services.tool_catalog import CATALOG

    source, directory = ephemeris_files
    center = edge_birth(directory).utc_datetime
    monkeypatch.setenv("SE_EPHE_PATH", str(directory))
    payload = {
        "name": "虚构：星历覆盖边界",
        "birth_year": center.year,
        "birth_month": center.month,
        "birth_day": center.day,
        "birth_hour": center.hour,
        "birth_minute": center.minute,
        "birth_second": center.second,
        "birth_timezone": "UTC",
        "birth_longitude": 0.0,
        "birth_latitude": 0.0,
        "birth_time_uncertainty_minutes": 1.0,
    }
    if variant:
        payload["chart_variant"] = variant
    else:
        pass
    spec = next(s for s in CATALOG if s.key == key)
    path = (
        "midpoint_analysis.time_sensitivity"
        if key == "astro_germany" or variant == "germany"
        else "time_sensitivity"
    )
    options = {
        "fields": [path],
        "strict_fields": True,
        "include_snapshot_text": False,
        "response_char_limit": 0,
        "as_of": "2026-10-22T00:00:00Z",
    }

    rest, protocol, code, cli = surface_calls(
        spec, payload, projection=options, cli_first=False
    )
    assert rest.status_code == 503 and protocol.is_error and code == 1
    for error in (rest.json(), protocol.structured_content, cli):
        assert error["error_code"] == "ephemeris_source_inconsistent"
        assert "Physical ephemeris model changed across" in error["error"]
        assert error["issues"] == [
            {"path": "runtime.ephemeris_data", "code": "model_changed"}
        ]
        assert error["retryable"] is False
        assert str(directory) not in json.dumps(error)

    for name in ("sepl_24.se1", "semo_24.se1"):
        shutil.copy2(source / name, directory / name)
    e.configure_ephemeris_path(str(directory))
    rest, protocol, code, cli = surface_calls(
        spec, payload, projection=options, cli_first=False
    )
    assert rest.status_code == 200 and not protocol.is_error and code == 0
    bodies = [rest.json(), protocol.structured_content, cli]
    sensitivities = []
    for body in bodies:
        for component in path.split("."):
            body = body[component]
        sensitivities.append(body)
    assert sensitivities[0] == sensitivities[1] == sensitivities[2]
    assert sensitivities[0]["sample_count"] == 5
    assert sensitivities[0]["represented_radius_seconds"] == 60


@pytest.mark.parametrize("borrowed", [False, True])
def test_actual_batch_hashes_once_at_identity_and_once_at_its_owner_endpoint(
    ephemeris_files, monkeypatch: pytest.MonkeyPatch, borrowed: bool
) -> None:
    _, directory = ephemeris_files
    e.configure_ephemeris_path(str(directory))
    original = physical_sources._file_digest
    reads = Counter()

    def measured(path):
        reads[path.name] += 1
        return original(path)

    monkeypatch.setattr(physical_sources, "_file_digest", measured)
    trace = PhysicalEphemerisTrace() if borrowed else None
    batch = ephemeris._build_planet_states(
        "chart", 2460389.77, julian_day_tt=2460389.771, source_trace=trace
    )
    assert batch.fallback is None
    assert set(reads) == {"sepl_18.se1", "semo_18.se1"}
    if trace is not None:
        # The caller still has work to do; only it owns final verification.
        assert set(reads.values()) == {1}
        source = trace.finish()
        assert set(source["by_factor"]) == set(PHYSICAL_BODIES)
    else:
        pass
    assert set(reads.values()) == {2}


def test_borrowed_batch_owner_still_rejects_changed_file_before_delivery(
    ephemeris_files,
) -> None:
    _, directory = ephemeris_files
    e.configure_ephemeris_path(str(directory))
    trace = PhysicalEphemerisTrace()
    batch = ephemeris._build_planet_states(
        "chart", 2460389.77, julian_day_tt=2460389.771, source_trace=trace
    )
    assert batch.fallback is None
    # Mutate only this fixture's writable copy, after the borrowed batch returns.
    path = directory / "sepl_18.se1"
    path.write_bytes(path.read_bytes() + b"changed-before-final-owner-delivery")
    with pytest.raises(EphemerisSourceError) as caught:
        trace.finish()
    assert caught.value.reason == "changed_during"
